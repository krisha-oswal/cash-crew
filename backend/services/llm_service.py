"""
Base LLM service interface with provider routing and fallback logic.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    GROQ_LLAMA3_70B = "groq_llama3_70b"
    GROQ_MIXTRAL = "groq_mixtral"
    GEMINI_1_5_PRO = "gemini_1.5_pro"
    HUGGINGFACE_MIXTRAL = "huggingface_mixtral"
    OLLAMA_LLAMA3 = "ollama_llama3"
    OLLAMA_MIXTRAL = "ollama_mixtral"
    OLLAMA_MISTRAL = "ollama_mistral"


class BaseLLMService(ABC):
    """Abstract base class for LLM services."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured output matching schema."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the service is available."""
        pass


class LLMRouter:
    """Routes LLM requests to appropriate providers with fallback logic."""
    
    def __init__(self):
        self.providers: Dict[LLMProvider, BaseLLMService] = {}
        self.usage_stats: Dict[LLMProvider, Dict[str, int]] = {}
        
    def register_provider(self, provider: LLMProvider, service: BaseLLMService):
        """Register an LLM provider."""
        self.providers[provider] = service
        self.usage_stats[provider] = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "fallbacks": 0
        }
        logger.info(f"Registered LLM provider: {provider}")
    
    async def generate(
        self,
        prompt: str,
        provider_priority: List[LLMProvider],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> tuple[str, LLMProvider]:
        """
        Generate text with automatic fallback.
        
        Returns:
            Tuple of (generated_text, provider_used)
        """
        last_error = None
        
        for provider in provider_priority:
            if provider not in self.providers:
                logger.warning(f"Provider {provider} not registered, skipping")
                continue
            
            service = self.providers[provider]
            
            if not service.is_available():
                logger.warning(f"Provider {provider} not available, trying next")
                continue
            
            try:
                self.usage_stats[provider]["requests"] += 1
                
                result = await service.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                self.usage_stats[provider]["successes"] += 1
                logger.info(f"Successfully generated text using {provider}")
                
                return result, provider
                
            except Exception as e:
                self.usage_stats[provider]["failures"] += 1
                last_error = e
                logger.error(f"Provider {provider} failed: {str(e)}, trying next")
                
                # Track fallback if not the last provider
                if provider != provider_priority[-1]:
                    self.usage_stats[provider]["fallbacks"] += 1
        
        # All providers failed
        error_msg = f"All LLM providers failed. Last error: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        provider_priority: List[LLMProvider],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> tuple[Dict[str, Any], LLMProvider]:
        """
        Generate structured output with automatic fallback.
        
        Returns:
            Tuple of (structured_output, provider_used)
        """
        last_error = None
        
        for provider in provider_priority:
            if provider not in self.providers:
                logger.warning(f"Provider {provider} not registered, skipping")
                continue
            
            service = self.providers[provider]
            
            if not service.is_available():
                logger.warning(f"Provider {provider} not available, trying next")
                continue
            
            try:
                self.usage_stats[provider]["requests"] += 1
                
                result = await service.generate_structured(
                    prompt=prompt,
                    schema=schema,
                    system_prompt=system_prompt,
                    **kwargs
                )
                
                self.usage_stats[provider]["successes"] += 1
                logger.info(f"Successfully generated structured output using {provider}")
                
                return result, provider
                
            except Exception as e:
                self.usage_stats[provider]["failures"] += 1
                last_error = e
                logger.error(f"Provider {provider} failed: {str(e)}, trying next")
                
                if provider != provider_priority[-1]:
                    self.usage_stats[provider]["fallbacks"] += 1
        
        error_msg = f"All LLM providers failed. Last error: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get usage statistics for all providers."""
        return {
            provider.value: stats 
            for provider, stats in self.usage_stats.items()
        }


# Global LLM router instance
llm_router = LLMRouter()
