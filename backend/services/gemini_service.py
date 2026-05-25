"""
Google Gemini API integration for long-context analysis.
"""
import json
from typing import Optional, Dict, Any
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from .llm_service import BaseLLMService
from config.settings import settings

logger = logging.getLogger(__name__)


class GeminiService(BaseLLMService):
    """Google Gemini API service for long-context analysis."""
    
    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model_name = model
        self.api_key = settings.google_api_key
        self.model = None
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(model)
                logger.info(f"Gemini service initialized with model: {model}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Gemini service is available."""
        return self.model is not None and bool(self.api_key)
    
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
        """Generate text using Gemini."""
        if not self.is_available():
            raise Exception("Gemini service not available")
        
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini generation failed: {str(e)}")
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
        """Generate structured output using Gemini."""
        if not self.is_available():
            raise Exception("Gemini service not available")
        
        # Add schema to prompt
        schema_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        
        if system_prompt:
            schema_prompt = f"{system_prompt}\n\n{schema_prompt}"
        
        try:
            generation_config = genai.GenerationConfig(
                temperature=0.3,  # Lower temperature for structured output
                response_mime_type="application/json",
            )
            
            response = self.model.generate_content(
                schema_prompt,
                generation_config=generation_config
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            logger.error(f"Gemini structured generation failed: {str(e)}")
            raise


# Service instance
gemini_1_5_pro = GeminiService(model="gemini-1.5-pro")
