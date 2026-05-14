import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

class LLMConfig(BaseModel):
    """Configuration de base pour les appels LLM. (Les clés sont écrasées dynamiquement par r2v.py)"""
    
    # Placeholders nécessaires pour la Deep Copy dans r2v.py
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    module1_model: str = ""
    module2_model: str = ""
    
    # Paramètres d'inférence par défaut
    timeout: int = Field(
        default_factory=lambda: int(os.environ.get("R2V_LLM_TIMEOUT", "120"))
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.environ.get("R2V_LLM_MAX_RETRIES", "3"))
    )
    temperature: float = Field(
        default_factory=lambda: float(os.environ.get("R2V_LLM_TEMPERATURE", "0.7"))
    )


class R2VConfig(BaseModel):
    """Configuration principale du pipeline R2V."""
    
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    debug_mode: bool = Field(
        default_factory=lambda: os.environ.get("R2V_DEBUG", "false").lower() == "true"
    )
    
    # Dossier temporaire pour la compilation locale de Manim
    temp_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("R2V_TEMP_DIR", "/tmp/r2v"))
    )


# Instance globale
_config: Optional[R2VConfig] = None

def get_r2v_config() -> R2VConfig:
    """Récupère l'instance globale de configuration R2V."""
    global _config
    if _config is None:
        _config = R2VConfig()
    return _config