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
Role: You are an expert Manim animator and a highly creative STEM teacher. Your task is to translate the provided reasoning chain into a dynamic Manim animation.

CRITICAL HARD CONSTRAINTS FOR JSON VALIDITY AND ANIMATION:
1) JSON ONLY: You MUST output EXACTLY ONE valid JSON object. No conversational text.
2) NO LATEX: You are on Windows without LaTeX. NEVER use `MathTex` or `Tex`. Use ONLY `Text('''...''')` with triple single quotes to prevent escaping errors.
3) NO OVERLAPPING TEXT: Before moving to a new step or clearing the whiteboard, you MUST wipe the screen using: `self.play(*[FadeOut(m) for m in self.mobjects])`
4) DOMAIN-ADAPTIVE VISUALS (MANDATORY): You MUST draw geometric shapes or visual representations adapted to the specific subject! 
   - For Mathematics: Use Polygon, Line, Angle, Graph.
   - For Physics: Use Circle (for masses/planets), Arrow (for forces/vectors), Dot.
   - For Computer Science: Use Rectangle (for memory/arrays), Text, Arrows (for pointers).
   Do NOT just write text. You are an ANIMATOR.
5) FIT ON SCREEN: Formulas or arrays must be scaled down using `.scale(0.65)`. Long text definitions must be split into multiple `Text` objects grouped with `VGroup().arrange(DOWN)`.
6) LANGUAGE: All visible Text() and narration MUST be in French.

Required JSON schema (Use this exact structural template, but REPLACE the bracketed placeholders [ ] with dynamic code adapted to the user's specific concept!):
{
  "narration": "Texte explicatif complet de la vidéo en français...",
  "manim_code": "from manim import *\\n\\nclass PedagogicalScene(Scene):\\n    def construct(self):\\n        # ACT 1: TITLE\\n        t1 = Text('''[INSERT CONCEPT TITLE HERE]''', color=BLUE).to_edge(UP)\\n        self.play(Write(t1))\\n        self.wait(2)\\n        self.play(*[FadeOut(m) for m in self.mobjects])\\n\\n        # ACT 2: VISUALIZATION (ADAPT SHAPES TO DOMAIN)\\n        # [GENERATE MANIM SHAPES HERE: Circle, Rectangle, Arrow, etc. based on the concept]\\n        shape_example = Circle(color=WHITE) # Replace this with appropriate shapes\\n        label = Text('''[INSERT SHORT DEFINITION]''', color=GREEN).scale(0.6).next_to(shape_example, DOWN)\\n        self.play(Create(shape_example), Write(label))\\n        self.wait(3)\\n        self.play(*[FadeOut(m) for m in self.mobjects])\\n\\n        # ACT 3: FORMULA OR KEY RULE\\n        f1 = Text('''[INSERT FORMULA, ALGORITHM RULE OR CONCLUSION]''', color=YELLOW).scale(0.8)\\n        self.play(Write(f1))\\n        self.wait(3)"
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
            
            import copy
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

            # EXTRACTEUR BLINDÉ
            manim_code = ""
            if isinstance(storyboard_json, list) and len(storyboard_json) > 0:
                storyboard_json = storyboard_json[0]

            if isinstance(storyboard_json, dict):
                manim_code = storyboard_json.get("manim_code", storyboard_json.get("code", storyboard_json.get("python_code", "")))

            if not manim_code:
                raw_response = str(storyboard_json)
                match = re.search(r"(from\s+manim\s+import.*?)(?:```|$|'\s*})", raw_response, re.DOTALL)
                if match:
                    manim_code = match.group(1).replace('\\n', '\n')

            if not manim_code or "class PedagogicalScene" not in manim_code:
                raise ValueError(f"Code Manim invalide. Réponse brute : {str(storyboard_json)[:150]}...")

            manim_code = textwrap.dedent(manim_code).strip()

            # ================================================================
            # STAGE 3: MODULE 3 - NEURO-SYMBOLIC RENDERING (MANIM)
            # ================================================================
            yield _sse("progress", {
                "request_id": request_id,
                "stage": "module_3_generation",
                "progress_pct": 60,
                "message": "📐 Génération de l'animation géométrique (Manim)...",
            })
            
            video_filename = f"r2v_{request_id}.mp4"
            video_path = UPLOAD_DIR / video_filename
            temp_dir = config.temp_dir / request_id
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                temp_script_path = temp_dir / "temp_scene.py"
                with open(temp_script_path, "w", encoding="utf-8") as f:
                    f.write(manim_code)

                # Exécution locale de Manim
                result = subprocess.run([sys.executable, "-m", "manim", "-ql", "--media_dir", str(temp_dir), str(temp_script_path), "PedagogicalScene"],
                    capture_output=True, text=True
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"Planté !\nLog:\n{result.stderr}")

                mp4_files = list(temp_dir.rglob("*.mp4"))
                if not mp4_files:
                    raise FileNotFoundError(f"Vidéo introuvable. Logs:\n{result.stdout}")

                shutil.copy(mp4_files[0], video_path)

                yield _sse("progress", {
                    "request_id": request_id,
                    "progress_pct": 88,
                    "message": "✅ Rendu visuel terminé avec succès",
                })

            except Exception as e:
                yield _sse("error", {"message": f"❌ ERREUR FATALE MANIM : {str(e)}"})
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