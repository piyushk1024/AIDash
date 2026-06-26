from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")
    
    UPLOAD_DIR: Path #= Path("app/uploads")
    LLM_API_KEY: str
    LLM_MODEL: str = "gemini/gemini-3.1-flash-lite"    
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10
    METABASE_SYNC_TIMEOUT: int = 60
    DATABASE_URL: str
    METABASE_URL: str
    METABASE_PUBLIC_URL: str = "http://localhost:3000"
    METABASE_USERNAME: str
    METABASE_PASSWORD: str
    METABASE_DB_NAME: str 
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    AGENT_MAX_INSPECT_CALLS: int = 3
    AGENT_MAX_ITERATIONS: int = 12

settings = Settings()


