from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
import re
import textwrap
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
import copy
import httpx
import replicate

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Open WebUI internal imports for file management
from open_webui.models.files import FileForm, Files
from open_webui.utils.auth import get_verified_user
from open_webui.config import UPLOAD_DIR as OPENWEBUI_UPLOAD_DIR

# R2V Services (Only LLM is needed now)
from open_tutorai.services.r2v_llm_service import LLMClient
from open_tutorai.r2v_config.r2v_config import get_r2v_config

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parents[2] / "data")))
UPLOAD_DIR = Path(OPENWEBUI_UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
log.info("[R2V] Using Open WebUI UPLOAD_DIR: %s", UPLOAD_DIR)

router = APIRouter()

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================
class R2VGenerateRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Student question")
    chat_id: Optional[str] = Field(default=None)
    language: str = Field(default="fr")
    duration_sec: int = Field(default=35, ge=10, le=180)
    model_id: str = Field(default="llama-3.3-70b-versatile", description="ID of the model selected in the UI")

def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Event (SSE) message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

# =============================================================================
# SYSTEM PROMPTS
# =============================================================================
def _build_module_1_system_prompt() -> str:
    return """You are Module-1 of a Reasoning-to-Video (R2V) educational AI pipeline.
Role: produce a rigorous, pedagogical, machine-usable reasoning trace from a student question.

Hard constraints:
1) Output ONLY valid JSON (UTF-8).
2) Keep it concise and logical. Do not overcomplicate.
3) CRITICAL FOR JSON VALIDITY: Properly escape all quotes.
4) Maintain temporal coherence - each step must logically follow from previous steps.

Required JSON schema:
{
  "subject": "Nom du concept",
  "total_steps": 3,
  "reasoning_chain":[
    {
      "step": 1,
      "concept": "Nom de l'étape",
      "logic": "Explication pédagogique",
      "equations": "Formules si applicables"
    }
  ]
}
"""

def _build_module_2_system_prompt() -> str:
    return """You are Module-2 of a Reasoning-to-Video educational AI pipeline.
Role: You are an Expert Film Director. Your job is to translate a pedagogical concept into a highly detailed visual prompt for the CogVideoX-3 diffusion model.

CRITICAL CONSTRAINTS:
1) OUTPUT ONLY VALID JSON.
2) NO TEXT ON SCREEN: Diffusion models cannot spell words correctly. DO NOT ask the model to write text, formulas, or labels. Describe ONLY visual physics, shapes, movements, and nature.
3) CINEMATIC DETAILS: A good CogVideoX prompt is highly descriptive. Include camera movement (pan, zoom), lighting, colors, and the exact physical action.

Required JSON schema:
{
  "narration": "Texte explicatif à lire en français...",
  "video_prompt": "A highly detailed cinematic description in English. E.g., 'A hyper-realistic 3D animation of a red apple falling from a green tree branch. Slow motion. Soft cinematic lighting, clear blue sky background. The camera tracks the apple as it falls downwards to the ground.'"
}
"""

# =============================================================================
# FILE REGISTRATION UTILITIES
# =============================================================================
async def _register_video_in_openwebui(
    user_id: str,
    video_path: Path,
    video_filename: str,
    original_filename: str,
    chat_id: Optional[str] = None,
) -> Optional[str]:
    try:
        file_id = str(uuid.uuid4())
        file_hash = None
        if video_path.exists():
            with open(video_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        file_size = video_path.stat().st_size if video_path.exists() else 0
        
        file_form = FileForm(
            id=file_id,
            hash=file_hash,
            filename=original_filename,
            path=str(video_path),
            data={"source": "r2v_pipeline", "pipeline_version": "2.0.0"},
            meta={
                "name": original_filename,
                "content_type": "video/mp4",
                "size": file_size,
                "chat_id": chat_id,
                "generated_at": int(time.time()),
            },
        )
        result = Files.insert_new_file(user_id=user_id, form_data=file_form)
        if result:
            return file_id
        return None
    except Exception as e:
        log.exception("[R2V] Error registering video in OpenWebUI: %s", e)
        return None

# =============================================================================
# MAIN ENDPOINT
# =============================================================================
@router.post("/generate")
async def generate_reasoning_video(
    payload: R2VGenerateRequest,
    request: Request,
    user=Depends(get_verified_user),
):
    log.info("[R2V] /generate called | user=%s | chat_id=%s | model_id=%s", getattr(user, "id", "anonymous"), payload.chat_id, payload.model_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        request_id = str(uuid.uuid4())
        user_id = getattr(user, "id", "anonymous")
        config = get_r2v_config()
        llm_client: Optional[LLMClient] = None
        
        try:
            # ================================================================
            # STAGE 0: INITIALIZATION (ROUTAGE DYNAMIQUE)
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "init",
                "progress_pct": 0,
                "message": "🎬 Initialisation du pipeline Reasoning-to-Video...",
                "detail": f"Préparation du modèle sélectionné : {payload.model_id}",
            })
            
            local_llm_config = copy.deepcopy(config.llm)
            local_llm_config.module1_model = payload.model_id
            local_llm_config.module2_model = payload.model_id
            
            auth_header = request.headers.get("Authorization", "")
            user_token = auth_header.replace("Bearer ", "").strip()
            internal_api_url = f"{request.base_url.scheme}://{request.base_url.netloc}/api"

            local_llm_config.provider = "openai"
            local_llm_config.api_key = user_token
            local_llm_config.base_url = internal_api_url
            
            os.environ["OPENAI_API_KEY"] = local_llm_config.api_key
            os.environ["OPENAI_BASE_URL"] = local_llm_config.base_url
            
            llm_client = LLMClient(local_llm_config)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "init",
                "progress_pct": 5,
                "message": "✅ Services initialisés",
                "detail": f"Modèle IA: {payload.model_id} | Moteur de rendu: Manim Local",
            })

            # ================================================================
            # STAGE 1: MODULE 1 - REASONING EXTRACTION
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_1_reasoning",
                "progress_pct": 10,
                "message": "🧠 Module 1 : Extraction du raisonnement logique...",
            })
            
            try:
                reasoning_json = await llm_client.generate_reasoning_chain(
                    question=payload.question,
                    system_prompt=_build_module_1_system_prompt(),
                )
                yield _sse("artifact", {"artifact_type": "reasoning_chain", "data": reasoning_json})
            except Exception as e:
                yield _sse("error", {"message": "❌ Erreur Extraction (Module 1)", "detail": str(e)})
                yield "data: [DONE]\n\n"
                return

            await asyncio.sleep(1) # Protection API Limit

            # ================================================================
            # STAGE 2: MODULE 2 - STORYBOARD STRUCTURATION
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_2_storyboard",
                "progress_pct": 30,
                "message": "🎬 Module 2 : Génération du code mathématique (IA)...",
            })
            
            try:
                storyboard_json = await llm_client.generate_storyboard(
                    reasoning_chain=reasoning_json,
                    duration_sec=payload.duration_sec,
                    system_prompt=_build_module_2_system_prompt(),
                )
                yield _sse("artifact", {"artifact_type": "storyboard", "data": storyboard_json})
            except Exception as e:
                yield _sse("error", {"message": "❌ Erreur Génération Code (Module 2)", "detail": str(e)})
                yield "data: [DONE]\n\n"
                return

            # ================================================================
            # STAGE 3: MODULE 3 - DIFFUSION RENDERING (ZHIPUAI / COGVIDEOX-3)
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_3_generation",
                "progress_pct": 50,
                "message": "🎨 Module 3 : Préparation du prompt visuel...",
            })
            
            video_filename = f"r2v_{request_id}.mp4"
            video_path = UPLOAD_DIR / video_filename
            
            try:                
                # 1. On récupère le Prompt Visuel généré par l'IA (ou on prend la narration par défaut)
                video_prompt = storyboard_json.get("video_prompt", storyboard_json.get("narration", "Vidéo explicative détaillée."))
                
                yield _sse("progress", {
                    "request_id": request_id,
                    "stage": "module_3_cogvideo",
                    "progress_pct": 60,
                    "message": "🎥 Envoi à ZhipuAI (CogVideoX-3)... Génération en cours.",
                    "detail": f"Prompt visuel : {video_prompt[:100]}..."
                })

                # 2. Clé API ZhipuAI (REMPLACEZ PAR VOTRE CLÉ EXACTE)
                zhipu_api_key = "210f033dd0ae4764a9798ca7dc41ca61.woqDYCLgUlWSMY0d"
                
                headers = {
                    "Authorization": f"Bearer {zhipu_api_key}",
                    "Content-Type": "application/json"
                }

                # 3. Communication Asynchrone (Non-Bloquante)
                async with httpx.AsyncClient(timeout=120.0) as client:
                    
                    # ÉTAPE A : Création de la tâche
                    submit_url = "https://open.bigmodel.cn/api/paas/v4/videos/generations"
                    api_payload = {
                        "model": "cogvideox-3",
                        "prompt": video_prompt,
                        "size": "1280x720",
                        "fps": 30,
                        "duration": 12,
                        "quality": "quality"
                    }
                    
                    submit_response = await client.post(submit_url, json=api_payload, headers=headers)
                    submit_response.raise_for_status()
                    
                    task_id = submit_response.json().get("id")
                    if not task_id:
                        raise RuntimeError(f"Échec de la création de tâche ZhipuAI: {submit_response.text}")

                    # ÉTAPE B : Polling (On boucle toutes les 5 secondes sans bloquer le serveur)
                    status_url = f"https://open.bigmodel.cn/api/paas/v4/async-result/{task_id}"
                    video_url = None
                    
                    for i in range(60): # Attente maximum de 5 minutes (60 * 5s)
                        await asyncio.sleep(5) # Libère l'Event Loop pendant 5 secondes
                        
                        status_resp = await client.get(status_url, headers=headers)
                        status_resp.raise_for_status()
                        status_data = status_resp.json()
                        
                        task_status = status_data.get("task_status")
                        
                        if task_status == "SUCCESS":
                            video_url = status_data.get("video_result")[0].get("url")
                            break # C'est prêt, on sort de la boucle !
                        elif task_status == "FAILED":
                            raise RuntimeError(f"Échec ZhipuAI: {status_data.get('error', 'Erreur inconnue')}")
                        elif task_status == "PROCESSING":
                            # Animation de la barre de chargement SvelteKit
                            yield _sse("progress", {
                                "request_id": request_id,
                                "progress_pct": 65 + (i * 0.5), 
                                "message": f"⏳ Génération vidéo en cours sur les serveurs... ({(i+1)*5}s écoulées)",
                            })
                    
                    if not video_url:
                        raise TimeoutError("Le temps d'attente (5 minutes) a été dépassé pour ZhipuAI.")

                    # ÉTAPE C : Téléchargement de la vidéo sur votre PC
                    yield _sse("progress", {
                        "request_id": request_id,
                        "progress_pct": 90,
                        "message": "📥 Vidéo générée ! Téléchargement vers votre interface...",
                    })
                    
                    dl_response = await client.get(video_url, timeout=300.0)
                    dl_response.raise_for_status()
                    
                    with open(video_path, "wb") as f:
                        f.write(dl_response.content)

                yield _sse("progress", {
                    "request_id": request_id,
                    "progress_pct": 95,
                    "message": "✅ Téléchargement vidéo terminé.",
                })

            except Exception as e:
                log.error("[R2V] Module 3 failed: %s", str(e))
                yield _sse("error", {"message": f"❌ ERREUR CLOUD ZHIPUAI : {str(e)}"})
                raise e

            # ================================================================
            # STAGE 4: FILE REGISTRATION & FINALIZATION
            # ================================================================
            yield _sse("progress", {"progress_pct": 95, "message": "📁 Enregistrement du fichier vidéo..."})
            
            file_id = await _register_video_in_openwebui(
                user_id=user_id, video_path=video_path, video_filename=video_filename,
                original_filename=f"R2V_Video.mp4", chat_id=payload.chat_id,
            )
            file_id = file_id or request_id
            
            final_markdown = (
                f"### Vidéo Explicative Générée\n\n"
                f"{{{{VIDEO_FILE_ID_{file_id}}}}}\n\n"
                f"---\n\n"
                f"**Moteur de Rendu :** Neuro-Symbolique (Manim)\n"
                f"**Modèle Utilisé :** `{payload.model_id}`\n"
            )
            
            yield _sse("final", {
                "request_id": request_id,
                "stage": "complete",
                "progress_pct": 100,
                "message": "🎉 Vidéo R2V générée avec succès !",
                "markdown": final_markdown,
            })
            
            yield "data: [DONE]\n\n"

        except Exception as exc:
            log.exception("[R2V:%s] Pipeline failed: %s", request_id, exc)
            yield _sse("error", {"message": "❌ Erreur dans le pipeline R2V", "detail": str(exc)})
            yield "data: [DONE]\n\n"
        
        finally:
            if llm_client:
                await llm_client.close()
            # Nettoyage des fichiers temporaires pour économiser le disque
            if 'temp_dir' in locals() and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

# =============================================================================
# HEALTH / CONFIG ENDPOINTS
# =============================================================================
@router.get("/health")
async def r2v_health_check():
    return {
        "status": "healthy",
        "service": "r2v_pipeline",
        "mode": "neuro-symbolic (manim)",
    }

@router.get("/config")
async def get_r2v_configuration(user=Depends(get_verified_user)):
    config = get_r2v_config()
    return {
        "llm_provider": config.llm.provider,
        "engine": "manim local"
    }