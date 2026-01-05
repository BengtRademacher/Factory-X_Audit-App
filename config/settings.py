from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Dict, List

class Settings(BaseSettings):
    """Zentrale Konfiguration fuer die Audit App."""
    
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


# Farbpalette (ausserhalb der Settings-Klasse fuer einfachen Import)
COLORS: Dict[str, str] = {
    "primary": "#006DB9",      # Blau (neue Primary)
    "secondary": "#007CC5",    # Hellblau (neue Secondary)
    "success": "#01A579",      # Gruen
    # Reserve
    "warning": "#F9B31A",
    "error": "#E50037",
}

# Vollstaendige Palette fuer sequentielle Charts (ohne das erste Dunkelblau)
COLORS_SEQUENCE: List[str] = [
    '#006DB9', '#007CC5', '#01A579',             # Aktiv
    '#B1CB21', '#F9B31A', '#EF7100', '#E50037'   # Reserve
]

settings = Settings()

