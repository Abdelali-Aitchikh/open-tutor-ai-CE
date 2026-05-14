from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from openai import AsyncOpenAI
from open_tutorai.r2v_config.r2v_config import get_r2v_config, LLMConfig

log = logging.getLogger(__name__)


# =============================================================================
# JSON EXTRACTION UTILITIES
# =============================================================================

def extract_json_from_response(text: str) -> dict[str, Any]:
    """
    Extrait un objet JSON depuis une réponse textuelle brute du LLM.
    Gère les formats avec ou sans balises markdown (```json ... ```).
    """
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(code_block_pattern, text)
    
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, text)
    matches.sort(key=len, reverse=True)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    raise ValueError(f"Impossible d'extraire un JSON valide de la réponse: {text[:500]}...")


# =============================================================================
# LLM CLIENT CLASS
# =============================================================================

class LLMClient:
    """
    Client asynchrone universel (Compatible API OpenAI).
    S'adapte dynamiquement à la configuration fournie par l'orchestrateur (OpenWebUI Proxy).
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_r2v_config().llm
        
        if not self.config.base_url or not self.config.api_key:
            log.warning("[LLMClient] Initialisation avec une configuration incomplète (base_url ou api_key manquant).")

        self._client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            max_retries=self.config.max_retries,
            timeout=self.config.timeout
        )
    
    async def close(self):
        """Ferme proprement le client asynchrone."""
        if self._client:
            await self._client.close()
            log.info("[LLMClient] AsyncOpenAI client closed")
    
    async def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
        force_json: bool = False,
    ) -> str:
        """
        Exécute l'appel asynchrone vers l'API LLM (via le proxy OpenWebUI).
        """
        actual_model = model or self.config.module1_model
        actual_temp = temperature if temperature is not None else self.config.temperature
        
        prompt_chars = len(system_prompt) + len(user_message)
        estimated_prompt_tokens = prompt_chars // 4
        estimated_total_tokens = estimated_prompt_tokens + max_tokens
        
        log.info(
            "[LLMClient] Calling LLM API | model=%s | temp=%.2f | force_json=%s | max_tokens=%d | est_total_tokens=%d",
            actual_model, actual_temp, force_json, max_tokens, estimated_total_tokens
        )
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            
            kwargs = {
                "model": actual_model,
                "messages": messages,
                "temperature": actual_temp,
                "max_tokens": max_tokens, 
            }
            
            if force_json:
                kwargs["response_format"] = {"type": "json_object"}
                log.info("[LLMClient] JSON mode enabled")
            
            completion = await self._client.chat.completions.create(**kwargs)
            content = completion.choices[0].message.content
            
            usage = completion.usage
            log.info(
                "[LLMClient] Success | model=%s | response_len=%d | prompt_tokens=%d | total_tokens=%d",
                actual_model, len(content), 
                usage.prompt_tokens if usage else 0,
                usage.total_tokens if usage else 0
            )
            
            return content
            
        except Exception as e:
            error_str = str(e)
            log.error("[LLMClient] API call failed | model=%s | error=%s", actual_model, error_str)
            
            if "413" in error_str or "rate_limit" in error_str.lower():
                log.error("[LLMClient] 🚨 RATE LIMIT EXCEEDED | La taille de la requête dépasse la limite du modèle ou de l'API.")
                
            raise ValueError(f"LLM API error: {error_str}")
    
    async def generate_reasoning_chain(self, question: str, system_prompt: str) -> dict[str, Any]:
        """
        Module 1 : Génère la chaîne de raisonnement causale.
        """
        log.info("[LLMClient] MODULE 1 - Generating reasoning chain for: %s", question[:100])
        
        user_message = f"""Question de l'étudiant:
{question}

Génère la chaîne de raisonnement JSON complète selon le schéma spécifié dans le system prompt.
IMPORTANT: Réponds UNIQUEMENT avec du JSON valide."""
        
        # max_tokens limité à 1500 pour optimiser la latence d'orchestration
        response = await self.call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            model=self.config.module1_model,
            temperature=0.7,
            max_tokens=1500,  
            force_json=True,  
        )
        
        try:
            reasoning_json = json.loads(response)
        except json.JSONDecodeError:
            log.warning("[LLMClient] JSON loads failed, attempting Regex extraction")
            reasoning_json = extract_json_from_response(response)
        
        # Validation sommaire
        if "steps" not in reasoning_json:
            log.warning("[LLMClient] Missing required field 'steps' in reasoning chain")
            
        return reasoning_json
    
    async def generate_storyboard(
        self,
        reasoning_chain: dict[str, Any],
        duration_sec: int,
        system_prompt: str,
    ) -> dict[str, Any]:
        """
        Module 2 : Génère le script Python (Manim) basé sur le raisonnement.
        """
        log.info("[LLMClient] MODULE 2 - Generating Manim code | duration=%ds", duration_sec)
        
        # Extraction stricte alignée avec le nouveau format du Module 1
        essential_reasoning = {
            "subject": reasoning_chain.get("subject", "Concept Pédagogique"),
            "steps": reasoning_chain.get("reasoning_chain", [])[:5]
        }
        
        user_message = f"""Reasoning chain summary:
{json.dumps(essential_reasoning, ensure_ascii=False)}

Target duration: {duration_sec}s

Génère le script Manim et la narration en format JSON. Pas de texte en dehors du JSON."""
        
        # max_tokens limité à 2500 pour laisser l'espace au code Python
        response = await self.call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            model=self.config.module2_model,
            temperature=0.4, # Plus bas pour favoriser la rigueur de la syntaxe Python
            max_tokens=2500,  
            force_json=True,  
        )
        
        try:
            storyboard_json = json.loads(response)
        except json.JSONDecodeError:
            log.warning("[LLMClient] JSON loads failed, attempting Regex extraction")
            storyboard_json = extract_json_from_response(response)
        
        # Validation de la présence du code Manim
        if "manim_code" not in storyboard_json:
            log.warning("[LLMClient] Attention: Clé 'manim_code' absente du JSON.")
            
        return storyboard_json

# =============================================================================
# WRAPPER FUNCTIONS (Convenience API)
# =============================================================================

async def call_module1_reasoning(question: str, system_prompt: str, config: Optional[LLMConfig] = None) -> dict[str, Any]:
    client = LLMClient(config)
    try:
        return await client.generate_reasoning_chain(question, system_prompt)
    finally:
        await client.close()

async def call_module2_storyboard(reasoning_chain: dict[str, Any], duration_sec: int, system_prompt: str, config: Optional[LLMConfig] = None) -> dict[str, Any]:
    client = LLMClient(config)
    try:
        return await client.generate_storyboard(reasoning_chain, duration_sec, system_prompt)
    finally:
        await client.close()