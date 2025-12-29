# Audit App V01

Eine Streamlit-basierte Anwendung zur automatisierten Extraktion, Verarbeitung und zum Vergleich von Forschungsdaten und Messdaten im Bereich Maschinen-Energieeffizienz.

## Struktur

Das Projekt ist in drei Kern-Capabilities unterteilt:

1.  **📄 Paper to JSON**: Extrahiert strukturierte JSON-Daten aus wissenschaftlichen PDFs mittels LLMs (Gemini, OpenAI, etc.).
2.  **📊 Data to JSON**: Verarbeitet Excel- oder CSV-Messdaten zu standardisierten Energie-KPIs.
3.  **🔍 JSON Comparison**: Ermöglicht den Vergleich zwischen eigenen Messdaten und Literatur-Benchmarks mit KI-gestützter Analyse.

## Installation

1.  Repository klonen oder herunterladen.
2.  Abhängigkeiten installieren:
    ```bash
    pip install -r requirements.txt
    ```

3.  API-Schlüssel in `.streamlit/secrets.toml` konfigurieren:
    ```toml
    [gemini]
    api_key = "DEIN_GEMINI_API_KEY"
    ```

## Nutzung

Starten Sie die App mit:
```bash
streamlit run app.py
```

## Projektstruktur

- `core/`: Kernlogik für LLMs, PDF und Datenverarbeitung.
- `database/`: Verwaltung der Literaturdatenbank und Messdaten.
- `services/`: Export- und Visualisierungsdienste.
- `config/`: Zentrale Einstellungen und Prompts.
- `pages/`: Die einzelnen Seiten der Multi-Page App.
- `data/`: Lokale Speicherung von JSONs, PDFs und Exporten.

## Technologie-Stack

- **Frontend**: Streamlit
- **KI/LLM**: Google Gemini, OpenAI, Ollama
- **Datenverarbeitung**: Pandas, NumPy
- **Extraktion**: PyPDF2
- **Visualisierung**: Plotly
- **Reports**: ReportLab

