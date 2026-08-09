from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", )
    
    LLM_API_KEY: str
    LLM_MODEL: str = "gemini/gemini-3.1-flash-lite"   
    LLM_RATE_LIMIT_COOLDOWN_SECONDS: int = 5  
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10
    DATABASE_URL: str
    DATABASE_URL_LOCAL: str = ""   # host-side override for standalone scripts run outside Docker
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 4
    AGENT_MAX_INSPECT_CALLS: int = 3
    AGENT_MAX_ITERATIONS: int = 12
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    MAX_UPLOAD_MB: int = 30
    MAX_ROWS: int = 100_000
    MAX_COLUMNS: int = 50
    ENVIRONMENT: str = "development"   # "development" | "production" — gates /docs, /redoc, and default CORS origin
    ALLOWED_ORIGINS: str = "http://localhost:5173"   # comma-separated list; set real prod origin via env at Day 4 hosting
    DAILY_CALL_LIMIT: int = 10

settings = Settings()