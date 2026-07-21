from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", )
    
    UPLOAD_DIR: Path #= Path("app/uploads")
    LLM_API_KEY: str
    LLM_MODEL: str = "gemini/gemini-3.1-flash-lite"   
    LLM_RATE_LIMIT_COOLDOWN_SECONDS: int = 5  
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10
    DATABASE_URL: str
    DATABASE_URL_LOCAL: str = ""   # host-side override for standalone scripts run outside Docker
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    AGENT_MAX_INSPECT_CALLS: int = 3
    AGENT_MAX_ITERATIONS: int = 12
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

settings = Settings()