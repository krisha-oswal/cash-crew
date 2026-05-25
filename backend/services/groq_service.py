"""
Groq API integration for ultra-fast LLM inference.
"""
import os
import json
from typing import Optional, Dict, Any
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from .llm_service import BaseLLMService, LLMProvider
from config.settings import settings

logger = logging.getLogger(__name__)


class GroqService(BaseLLMService):
    """Groq API service for fast LLM inference."""
    
    def __init__(self, model: str = "llama-3.1-70b-versatile"):
        self.model = model
        self.api_key = settings.groq_api_key
        self.client = None
        
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                logger.info(f"Groq service initialized with model: {model}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Groq service is available."""
        return self.client is not None and bool(self.api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text using Groq."""
        if not self.is_available():
            raise Exception("Groq service not available")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Groq generation failed: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured output using Groq."""
        if not self.is_available():
            raise Exception("Groq service not available")
        
        # Add schema to prompt
        schema_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": schema_prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for structured output
                response_format={"type": "json_object"},
                **kwargs
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Groq structured generation failed: {str(e)}")
            raise


# Service instances
groq_llama3_70b = GroqService(model="llama-3.1-70b-versatile")
groq_mixtral = GroqService(model="mixtral-8x7b-32768")
