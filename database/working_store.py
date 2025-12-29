import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import streamlit as st

class WorkingStore:
    """Verwaltet die aktuellen Messdaten (Working JSONs)."""
    
    def __init__(self, base_dir: str = "data/working"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def save_audit(self, audit_json: Dict[str, Any], filename: str):
        """Speichert ein Audit-Ergebnis."""
        if not filename.endswith(".json"):
            filename += ".json"
            
        file_path = self.base_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(audit_json, f, indent=2, ensure_ascii=False)
        return file_path

    def load_audit(self, filename: str) -> Optional[Dict[str, Any]]:
        """Lädt ein Audit-Ergebnis."""
        file_path = self.base_dir / filename
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_audits(self) -> List[str]:
        """Listet alle verfügbaren Audits auf."""
        return [f.name for f in self.base_dir.glob("*.json")]

    def delete_audit(self, filename: str):
        """Löscht ein Audit-Ergebnis."""
        file_path = self.base_dir / filename
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def get_latest_audit(self) -> Optional[Dict[str, Any]]:
        """Holt das zeitlich neueste Audit."""
        files = list(self.base_dir.glob("*.json"))
        if not files:
            return None
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        return self.load_audit(latest_file.name)

