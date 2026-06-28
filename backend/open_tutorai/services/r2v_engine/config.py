import os
from dotenv import load_dotenv

# Load environment variables from .env (if present)
load_dotenv()

# ==================== LLM PROVIDER CONFIGURATION ====================
# Using OpenAI GPT models
LLM_PROVIDER = "openai"

# OpenAI API Key
# Set in environment: export OPENAI_API_KEY=your_key_here
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Model Configuration
# Available models: 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-5-mini', 'o1-preview', 'o1-mini'
# Set in environment: export MODEL_NAME=gpt-5-mini
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5-mini")

# Manim Configuration
MANIM_QUALITY = "high_quality"  # Options: low_quality, medium_quality, high_quality
MANIM_OUTPUT_DIR = "media"

# TTS Configuration
TTS_ENGINE = "gTTS"  # Options: gTTS, etc.

# Kokoro TTS Configuration
KOKORO_MODEL_PATH = os.getenv('KOKORO_MODEL_PATH')
KOKORO_VOICES_PATH = os.getenv('KOKORO_VOICES_PATH')
KOKORO_DEFAULT_VOICE = os.getenv('KOKORO_DEFAULT_VOICE', 'af_bella')
KOKORO_DEFAULT_SPEED = float(os.getenv('KOKORO_DEFAULT_SPEED', '1.0'))
KOKORO_DEFAULT_LANG = os.getenv('KOKORO_DEFAULT_LANG', 'en-us')

# Logging Configuration
LOG_LEVEL = "INFO"