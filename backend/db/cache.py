import redis
import json
import logging
from config.settings import settings
from typing import Any, Optional

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.enabled = settings.enable_caching
        self.redis_client = None
        
        if self.enabled:
            try:
                self.redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                logger.info(f"Connected to Redis cache at {settings.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}. Caching will be disabled.")
                self.enabled = False

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled or not self.redis_client:
            return None
        try:
            val = self.redis_client.get(key)
            if val:
                return json.loads(val)
            return None
        except Exception as e:
            logger.warning(f"Cache get error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, expire_seconds: int = 3600) -> bool:
        if not self.enabled or not self.redis_client:
            return False
        try:
            self.redis_client.setex(key, expire_seconds, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Cache set error for {key}: {e}")
            return False

cache_service = CacheService()
