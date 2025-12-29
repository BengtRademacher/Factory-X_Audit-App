from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """Zentrale Konfiguration für die Audit App."""
    
    APP_NAME: str = "Audit App V02"
    
    # Pfade
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LITERATURE_DIR: Path = DATA_DIR / "literature"
    WORKING_DIR: Path = DATA_DIR / "working"
    EXPORT_DIR: Path = DATA_DIR / "exports"
    
    # LLM Defaults
    DEFAULT_MODEL_GEMINI: str = "gemini-2.0-flash"
    DEFAULT_MODEL_OPENAI: str = "gpt-4-turbo"
    
    class Config:
        env_file = ".env"

settings = Settings()

