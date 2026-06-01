from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")
    
    UPLOAD_DIR: Path #= Path("app/uploads")
    LLM_API_KEY: str
    LLM_MODEL: str = "gemini/gemini-3.1-flash-lite"
    # GEMINI_API_KEY: str
    DATABASE_URL: str
    METABASE_URL: str
    METABASE_USERNAME: str
    METABASE_PASSWORD: str
    METABASE_DB_NAME: str 

settings = Settings()


