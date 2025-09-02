import structlog
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

logger = structlog.get_logger()

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    # Ensure api_keys is always a list
    valid_keys = settings.api_keys if isinstance(settings.api_keys, list) else [settings.api_keys]

    if api_key not in valid_keys:
        logger.warning(f"Invalid API key: {api_key[:8]}...")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    return api_key
