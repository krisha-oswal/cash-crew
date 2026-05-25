"""
Ollama local LLM integration for offline demo mode.
"""
import json
from typing import Optional, Dict, Any
import ollama
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from .llm_service import BaseLLMService
from config.settings import settings

logger = logging.getLogger(__name__)


class OllamaService(BaseLLMService):
    """Ollama local LLM service for offline operation."""
    
    def __init__(self, model: str = "llama3"):
        self.model = model
        self.base_url = settings.ollama_base_url
        self.client = None
        
        try:
            # Test connection to Ollama
            self.client = ollama.Client(host=self.base_url)
            # Try to list models to verify connection
            self.client.list()
            logger.info(f"Ollama service initialized with model: {model}")
        except Exception as e:
            logger.warning(f"Ollama not available: {str(e)}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Ollama service is available."""
        if self.client is None:
            return False
        
        try:
            # Quick health check
            self.client.list()
            return True
        except:
            return False
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text using Ollama."""
        if not self.is_available():
            raise Exception("Ollama service not available")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            
            return response['message']['content']
            
        except Exception as e:
            logger.error(f"Ollama generation failed: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured output using Ollama."""
        if not self.is_available():
            raise Exception("Ollama service not available")
        
        # Add schema to prompt
        schema_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}\n\nIMPORTANT: Respond ONLY with valid JSON, no additional text."
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": schema_prompt})
        
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                format="json",  # Request JSON format
                options={
                    "temperature": 0.3,  # Lower temperature for structured output
                }
            )
            
            content = response['message']['content']
            
            # Try to parse JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Extract JSON if wrapped in markdown or other text
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    return json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found in response")
            
        except Exception as e:
            logger.error(f"Ollama structured generation failed: {str(e)}")
            raise


# Service instances
ollama_llama3 = OllamaService(model="llama3")
ollama_mixtral = OllamaService(model="mixtral")
ollama_mistral = OllamaService(model="mistral")
