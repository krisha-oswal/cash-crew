"""
HuggingFace Inference API integration for sentiment analysis.
"""
import json
from typing import Optional, Dict, Any
from huggingface_hub import InferenceClient
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from .llm_service import BaseLLMService
from config.settings import settings

logger = logging.getLogger(__name__)


class HuggingFaceService(BaseLLMService):
    """HuggingFace Inference API service."""
    
    def __init__(self, model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"):
        self.model = model
        self.api_key = settings.huggingface_api_key
        self.client = None
        
        if self.api_key:
            try:
                self.client = InferenceClient(token=self.api_key)
                logger.info(f"HuggingFace service initialized with model: {model}")
            except Exception as e:
                logger.error(f"Failed to initialize HuggingFace client: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if HuggingFace service is available."""
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
        """Generate text using HuggingFace."""
        if not self.is_available():
            raise Exception("HuggingFace service not available")
        
        # Format prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
        else:
            full_prompt = f"<s>[INST] {prompt} [/INST]"
        
        try:
            response = self.client.text_generation(
                full_prompt,
                model=self.model,
                max_new_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            return response
            
        except Exception as e:
            logger.error(f"HuggingFace generation failed: {str(e)}")
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
        """Generate structured output using HuggingFace."""
        if not self.is_available():
            raise Exception("HuggingFace service not available")
        
        # Add schema to prompt
        schema_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        
        if system_prompt:
            full_prompt = f"<s>[INST] {system_prompt}\n\n{schema_prompt} [/INST]"
        else:
            full_prompt = f"<s>[INST] {schema_prompt} [/INST]"
        
        try:
            response = self.client.text_generation(
                full_prompt,
                model=self.model,
                max_new_tokens=2000,
                temperature=0.3,  # Lower temperature for structured output
                **kwargs
            )
            
            # Extract JSON from response
            # Try to find JSON in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: try to parse entire response
                return json.loads(response)
            
        except Exception as e:
            logger.error(f"HuggingFace structured generation failed: {str(e)}")
            raise


# Service instance
huggingface_mixtral = HuggingFaceService(model="mistralai/Mixtral-8x7B-Instruct-v0.1")
