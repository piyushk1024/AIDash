from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")
    
    UPLOAD_DIR: Path #= Path("app/uploads")
    GEMINI_API_KEY: str
    DATABASE_URL: str
    METABASE_URL: str
    METABASE_USERNAME: str
    METABASE_PASSWORD: str

settings = Settings()


