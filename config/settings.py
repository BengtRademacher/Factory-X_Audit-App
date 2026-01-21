from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Dict, List

class Settings(BaseSettings):
    """Central configuration for the Audit App."""
    
    APP_NAME: str = "Audit App v1.3"
    
    # Paths
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
    "Violett": "#4B5BA9",
    "Blau": "#006DB9",
    "Hellblau": "#007CC5",
    "Dunkelgrün": "#01A579",
    "Hellgrün": "#B1CB21",
    "Gelb": "#F9B31A",
    "Orange": "#EF7100",
    "Rot": "#E50037",
}

# Funktionale Zuweisungen für die App-Logik
COLORS.update({
    "primary": COLORS["Hellblau"],   # Hellblau als Primary
    "secondary": COLORS["Hellgrün"],     # Hellgrün als Secondary
    "success": COLORS["Dunkelgrün"],
    "warning": COLORS["Gelb"],
    "error": COLORS["Rot"]
})

# Vollstaendige Palette fuer sequentielle Charts
COLORS_SEQUENCE: List[str] = [
    COLORS["Violett"], COLORS["Blau"], COLORS["Hellblau"], COLORS["Dunkelgrün"],
    COLORS["Hellgrün"], COLORS["Gelb"], COLORS["Orange"], COLORS["Rot"]
]

settings = Settings()

