import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import shutil

class LiteratureDB:
    """Verwaltet die dateibasierte Literaturdatenbank."""
    
    def __init__(self, base_dir: str = "data/literature"):
        self.base_dir = Path(base_dir)
        self.json_dir = self.base_dir / "json"
        self.paper_dir = self.base_dir / "papers"
        self.index_path = self.base_dir / "index.json"
        
        # Verzeichnisse sicherstellen
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.paper_dir.mkdir(parents=True, exist_ok=True)
        
        self.index = self._load_index()

    def _load_index(self) -> List[Dict[str, Any]]:
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)

    def add_entry(self, paper_json: Dict[str, Any], pdf_file=None, filename: Optional[str] = None):
        """Fügt einen neuen Eintrag zur Datenbank hinzu."""
        if not filename:
            # Generiere Dateiname aus Titel, falls vorhanden
            title = paper_json.get("paper_metadata", {}).get("title", "unknown_paper")
            filename = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
            
        json_filename = f"{filename}.json"
        json_path = self.json_dir / json_filename
        
        # JSON speichern
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(paper_json, f, indent=2, ensure_ascii=False)
            
        # PDF speichern, falls vorhanden
        pdf_path = None
        if pdf_file:
            pdf_filename = f"{filename}.pdf"
            pdf_path = self.paper_dir / pdf_filename
            with open(pdf_path, "wb") as f:
                if hasattr(pdf_file, 'read'):
                    f.write(pdf_file.read())
                else:
                    f.write(pdf_file)
        
        # Index aktualisieren
        entry = {
            "id": filename,
            "title": paper_json.get("paper_metadata", {}).get("title"),
            "authors": paper_json.get("paper_metadata", {}).get("authors", []),
            "date": paper_json.get("paper_metadata", {}).get("publication_date"),
            "json_path": str(json_path),
            "pdf_path": str(pdf_path) if pdf_path else None
        }
        
        # Existierenden Eintrag ersetzen oder neu hinzufügen
        self.index = [e for e in self.index if e["id"] != filename]
        self.index.append(entry)
        self._save_index()
        
        return entry

    def get_all_entries(self) -> List[Dict[str, Any]]:
        return self.index

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.index:
            if entry["id"] == entry_id:
                with open(entry["json_path"], "r", encoding="utf-8") as f:
                    return json.load(f)
        return None

    def search(self, query: str) -> List[Dict[str, Any]]:
        query = query.lower()
        results = []
        for entry in self.index:
            if query in entry["title"].lower() or any(query in a.lower() for a in entry["authors"]):
                results.append(entry)
        return results

    def delete_entry(self, entry_id: str):
        entry = next((e for e in self.index if e["id"] == entry_id), None)
        if entry:
            if os.path.exists(entry["json_path"]):
                os.remove(entry["json_path"])
            if entry["pdf_path"] and os.path.exists(entry["pdf_path"]):
                os.remove(entry["pdf_path"])
            self.index = [e for e in self.index if e["id"] != entry_id]
            self._save_index()
            return True
        return False

