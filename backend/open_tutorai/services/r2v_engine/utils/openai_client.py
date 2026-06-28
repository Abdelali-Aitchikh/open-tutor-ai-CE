import logging
import time
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# 1. On charge STATIQUEMENT le .env du moteur R2V
env_path = Path(__file__).parents[1] / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key: str = None, model_name: str = None, timeout: int = 5400):
        # On récupère TA VRAIE clé API (sk-proj...)
        key = os.getenv("OPENAI_API_KEY")
        
        if not key or not key.startswith("sk-"):
            logger.error("ERREUR CRITIQUE : La clé API statique n'est pas trouvée ou invalide. Vérifiez le fichier .env")

        # Connexion DIRECTE à OpenAI (Aucune base_url, donc 128k tokens par défaut !)
        self.client = OpenAI(api_key=key, timeout=timeout)
            
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o")
        self.timeout = timeout
        logger.info(f"Initialized STATIC DIRECT OpenAI client with model: {self.model_name}")

    def generate_response(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.7, retries: int = 3, retry_delay: int = 5):
        for attempt in range(retries):
            try:
                # 🚨 AUCUNE RESTRICTION DE TOKENS ! 
                # L'IA peut générer le code le plus long possible.
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                if response.choices:
                    return response.choices[0].message.content
                return None
            except Exception as e:
                logger.error(f"API error (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None

    def generate_response_with_image(self, prompt: str, image_base64: str, max_tokens: int = 4000, temperature: float = 0.7, retries: int = 3, retry_delay: int = 5):
        for attempt in range(retries):
            try:
                # 🚨 AUCUNE RESTRICTION DE TOKENS NON PLUS
                response = self.client.chat.completions.create(
                    model=os.getenv("VISION_MODEL", "gpt-4o"),
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                        ]
                    }],
                    temperature=temperature
                )
                if response.choices:
                    return response.choices[0].message.content
                return None
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None