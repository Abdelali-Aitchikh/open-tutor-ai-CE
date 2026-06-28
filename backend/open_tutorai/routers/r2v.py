from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import uuid
import queue
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Open WebUI internal imports for file management
from open_webui.models.files import FileForm, Files
from open_webui.utils.auth import get_verified_user
from open_webui.config import UPLOAD_DIR as OPENWEBUI_UPLOAD_DIR

# R2V Services (Configuration LLM)
from open_tutorai.services.r2v_llm_service import LLMClient
from open_tutorai.r2v_config.r2v_config import get_r2v_config

# 📦 IMPORT DE LA NOUVELLE ARCHITECTURE MANIM (Le dossier r2v_engine)
from open_tutorai.services.r2v_engine.orchestrator import ManimPipelineOrchestrator
from dotenv import load_dotenv
load_dotenv()

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
            data={"source": "r2v_pipeline", "pipeline_version": "3.0.0-multi-agent"},
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
        
        # Initialisation des dossiers
        video_filename = f"r2v_{request_id}.mp4"
        video_path = UPLOAD_DIR / video_filename
        temp_dir = config.temp_dir / request_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # ================================================================
            # STAGE 0: INITIALIZATION (ROUTAGE DYNAMIQUE)
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "init",
                "progress_pct": 5,
                "message": "🎬 Initialisation du Super-Pipeline Reasoning-to-Video...",
                "detail": f"Préparation du modèle : {payload.model_id}",
            })
            
            # Injection sécurisée des identifiants (Deep Copy)
            import copy
            local_llm_config = copy.deepcopy(config.llm)
            local_llm_config.module1_model = payload.model_id # Rétrocompatibilité 
            local_llm_config.module2_model = payload.model_id
            
            auth_header = request.headers.get("Authorization", "")
            user_token = auth_header.replace("Bearer ", "").strip()
            internal_api_url = f"{request.base_url.scheme}://{request.base_url.netloc}/api"

            local_llm_config.provider = "openai"
            local_llm_config.api_key = user_token
            local_llm_config.base_url = internal_api_url
            
            # Injection dans l'environnement pour les agents MANIM autonomes
            os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
            
            if "OPENAI_BASE_URL" in os.environ:
                del os.environ["OPENAI_BASE_URL"]
                
            os.environ["MODEL_NAME"] = os.getenv("MODEL_NAME", "gpt-4o")
            
            # llm_client peut être passé à l'orchestrateur si besoin
            llm_client = LLMClient(local_llm_config)
            
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "init",
                "progress_pct": 10,
                "message": "✅ Agents IA instanciés. Démarrage de la réflexion...",
                "detail": "Mode: Multi-Agents + Rendu Neuro-Symbolique Manim Local",
            })

            # ================================================================
            # STAGE 1: EXECUTION DU PIPELINE MANIM (THREAD ARRIÈRE-PLAN)
            # ================================================================
            
            # 1. Instanciation de ton nouvel orchestrateur
            orchestrator = ManimPipelineOrchestrator(
                temp_dir=temp_dir, 
                llm_client=llm_client
            )
            
            # 2. Création d'une queue thread-safe pour la communication synchrone -> asynchrone
            msg_queue = queue.Queue()
            
            def sse_callback(progress: int, message: str):
                """Fonction passée à l'orchestrateur pour qu'il pousse ses logs ici."""
                msg_queue.put({"progress_pct": progress, "message": message})
            
            # 3. Exécution de la tâche lourde dans un thread séparé
            loop = asyncio.get_running_loop()
            task = loop.run_in_executor(
                None, 
                orchestrator.run_pipeline, 
                payload.question, 
                sse_callback
            )
            
            # 4. Lecture de la queue en temps réel pour envoyer les SSE au frontend SvelteKit
            while not task.done():
                while not msg_queue.empty():
                    msg = msg_queue.get()
                    yield _sse("progress", {
                        "request_id": request_id,
                        "stage": "manim_pipeline",
                        "progress_pct": msg["progress_pct"],
                        "message": msg["message"]
                    })
                # Pause légère pour ne pas saturer le thread async
                await asyncio.sleep(0.5)
            
            # 5. Vider les derniers messages restants dans la queue une fois la tâche terminée
            while not msg_queue.empty():
                msg = msg_queue.get()
                yield _sse("progress", {
                    "request_id": request_id,
                    "stage": "manim_pipeline",
                    "progress_pct": msg["progress_pct"],
                    "message": msg["message"]
                })
            
            # 6. Récupération du résultat (Lève une exception si l'orchestrateur a planté)
            generated_video_filepath = task.result()
            
            if not generated_video_filepath or not os.path.exists(generated_video_filepath):
                raise FileNotFoundError("L'orchestrateur a terminé mais n'a retourné aucun fichier vidéo valide.")

            # Copier la vidéo finale vers le dossier UPLOAD_DIR public d'OpenWebUI
            shutil.copy(generated_video_filepath, video_path)

            # ================================================================
            # STAGE 2: FILE REGISTRATION & FINALIZATION
            # ================================================================
            yield _sse("progress", {"progress_pct": 95, "message": "📁 Enregistrement du fichier vidéo sécurisé..."})
            
            file_id = await _register_video_in_openwebui(
                user_id=user_id, video_path=video_path, video_filename=video_filename,
                original_filename=f"R2V_Video_Advanced.mp4", chat_id=payload.chat_id,
            )
            file_id = file_id or request_id
            
            # Markdown rendu de façon sécurisée par le parseur de SvelteKit
            final_markdown = (
                f"### 🎥 Vidéo Explicative Générée\n\n"
                f"{{{{VIDEO_FILE_ID_{file_id}}}}}\n\n"
                f"---\n\n"
                f"**🧠 Moteur de Raisonnement :** Pipeline Multi-Agents\n"
                f"**📐 Moteur de Rendu :** Neuro-Symbolique (Manim)\n"
                f"**🤖 Modèle Utilisé :** `{payload.model_id}`\n"
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
            # Nettoyage strict des fichiers temporaires (Scripts générés, frames RAG)
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
        "architecture": "multi-agent + manim_orchestrator",
        "mode": "neuro-symbolic",
    }

@router.get("/config")
async def get_r2v_configuration(user=Depends(get_verified_user)):
    config = get_r2v_config()
    return {
        "llm_provider": config.llm.provider,
        "engine": "manim advanced orchestrator"
    }