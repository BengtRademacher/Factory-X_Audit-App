# Factory-X Audit App

Streamlit-App zur Extraktion, Verarbeitung und Bewertung von Energiedaten aus Fertigungsprozessen.

## Funktionen

1. **Paper to JSON** – API-Call zur Extraktion strukturierter Daten aus PDFs (Gemini)
2. **Data to JSON** – Berechnung von Energie-KPIs aus Maschinen-Messdaten (XLSX/CSV)
3. **JSON Comparison** – LLM-basierter Vergleich von Audit-Daten mit Literatur-Benchmarks

## Struktur

```
app.py                  # Hauptanwendung (Streamlit)
config/
  prompts.py            # LLM-Prompts
  settings.py           # Zentrale Konfiguration
core/
  llm_service.py        # LLM-Provider (Gemini, OpenAI, Ollama)
  data_parser.py        # Metriken-Berechnung
  json_schema.py        # Datenvalidierung
database/
  literature_db.py      # Literatur-Index (JSON-basiert)
  working_store.py      # Audit-Speicher
services/
  visualization.py      # Plotly-Charts
  export_service.py     # PDF-Export
data/
  literature/           # PDFs + extrahierte JSONs
  working/              # Gespeicherte Audits
```

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

API-Keys in `.streamlit/secrets.toml` konfigurieren.
