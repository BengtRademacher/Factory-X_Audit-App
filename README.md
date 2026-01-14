# Factory-X Audit-App v1.2

*Stand: 14. Januar 2026*

Die Factory-X Audit-App ist eine Streamlit-basierte Anwendung zur automatisierten Extraktion, Verarbeitung und Bewertung von Energiedaten aus Fertigungsprozessen. Sie kombiniert moderne LLM-Technologie mit klassischer Datenanalyse, um wissenschaftliche Publikationen und reale Maschinendaten vergleichbar zu machen.

## Kernfunktionen

1.  **Paper to JSON**: Extraktion strukturierter Daten aus wissenschaftlichen PDFs mittels LLMs. Die Ergebnisse werden in einer lokalen Literaturdatenbank gespeichert.
2.  **Data to JSON**: Verarbeitung von Maschinen-Messdaten (Excel/CSV). Automatische Berechnung von Energie-KPIs, Duty Cycles und Leistungswerten für elektrische und pneumatische Komponenten.
3.  **JSON Comparison**: KI-gestützter Vergleich zwischen Audit-Ergebnissen und Literatur-Benchmarks inklusive PDF-Export der Analyseergebnisse.

## Design und Styling

Die Anwendung folgt dem Factory-X Design-Guide für eine konsistente Benutzeroberfläche:
- **Material Design**: Nutzung von Material Symbols Rounded für intuitive Navigation.
- **Responsive Layout**: Optimierte Darstellung für verschiedene Bildschirmgrößen im Wide-Mode.
- **Branding**: Integration des Factory-X Logos und spezialisierter UI-Komponenten.

Details zur Gestaltung finden sich im `STYLING_GUIDE.md` und der `layout_assets.md`.

## Installation und Setup

1.  **Repository vorbereiten**: Klonen oder laden Sie das Projekt herunter.
2.  **Abhängigkeiten installieren**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Konfiguration**: Erstellen Sie eine `.streamlit/secrets.toml` im Hauptverzeichnis und hinterlegen Sie Ihre API-Schlüssel:
    ```toml
    [gemini]
    api_key = "DEIN_GEMINI_API_KEY"

    [openai]
    api_key = "DEIN_OPENAI_API_KEY"
    ```

## Nutzung

Starten Sie die Anwendung über die Kommandozeile:
```bash
streamlit run app.py
```

## Projektstruktur

- `app.py`: Hauptanwendung und UI-Logik.
- `config/`: Zentrale Einstellungen und LLM-Prompts.
- `core/`: Logik für LLM-Provider, Datenverarbeitung und Parsing.
- `database/`: Management der Literaturdatenbank und des Audit-Stores.
- `services/`: Dienste für Visualisierung (Plotly) und PDF-Export.
- `data/`: Lokale Ablage für PDFs, extrahierte JSON-Daten und Audits.

## Technologie-Stack

- **Backend/Frontend**: Streamlit
- **KI/LLM Integration**: Google Gemini, OpenAI, Ollama
- **Datenanalyse**: Pandas, NumPy
- **Datenvisualisierung**: Plotly
- **PDF-Verarbeitung**: PyPDF2, ReportLab

---
*Hinweis: Diese Anwendung wurde im Rahmen des Factory-X Projekts zur Steigerung der Energieeffizienz in der Produktion entwickelt.*
