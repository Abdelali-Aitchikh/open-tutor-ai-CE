"""Unified LLM client factory.

Initializes OpenAI client based on configuration.
"""
import logging
from config import OPENAI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)


def get_llm_client(api_key: str = None, model_name: str = None, timeout: int = 5400):
    """Factory function to get the OpenAI LLM client.

    Args:
        api_key: Optional API key (uses config default if not provided)
        model_name: Optional model name (uses config default if not provided)
        timeout: Request timeout in seconds

    Returns:
        An OpenAI client instance with a unified interface
    """
    from utils.openai_client import OpenAIClient
    
    api_key = api_key or OPENAI_API_KEY
    model_name = model_name or MODEL_NAME
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in config or environment")
    
    logger.info(f"Creating OpenAI client with model: {model_name}")
    return OpenAIClient(api_key=api_key, model_name=model_name, timeout=timeout)


# Convenience function for getting a client with custom settings
def get_evaluation_client(temperature: float = 0.0):
    """Get an LLM client optimized for evaluation (deterministic).
    
    Args:
        temperature: Temperature setting (default 0.0 for deterministic evaluation)
    
    Returns:
        LLM client instance
    """
    # Note: Temperature is passed during generate_response() call, not initialization
    return get_llm_client()


def get_generation_client(temperature: float = 0.7):
    """Get an LLM client optimized for creative generation.
    
    Args:
        temperature: Temperature setting (default 0.7 for creative output)
    
    Returns:
        LLM client instance
    """
    # Note: Temperature is passed during generate_response() call, not initialization
    return get_llm_client()