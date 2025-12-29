# Projekt-Übersicht: Audit App V01

Dieses Projekt dient der automatisierten Extraktion, Verarbeitung und dem Vergleich von Forschungsdaten aus wissenschaftlichen Publikationen (PDFs) und Excel-Dateien (XLSX) in das JSON-Format, unterstützt durch KI (Google Gemini).

## Projektstruktur

### 1. [paper_2_json/](paper_2_json/) & [Teil 1 (paper_2_json_app)/](Teil%201%20(paper_2_json_app)/)
- **Zweck:** Streamlit-Anwendungen zur Extraktion strukturierter Daten aus PDF-Dokumenten.
- **Kerntechnologie:** `PyPDF2` zur Textextraktion und `google-generativeai` (Gemini 2.0 Flash) zur Datenstrukturierung.
- **Inhalt:** Enthält Test-PDFs zu Zerspanungsprozessen (Milling, Grinding, Turning) und die daraus resultierenden JSON-Dateien.

### 2. [xlsx_2_json/](xlsx_2_json/)
- **Zweck:** Konvertierung von Excel-Daten in das JSON-Format, vermutlich mit ähnlicher KI-Unterstützung für unstrukturierte Tabellen.
- **Kerntechnologie:** Streamlit und Gemini API.

### 3. [2_json_comparator/](2_json_comparator/)
- **Zweck:** Vergleich von extrahierten JSON-Daten mit Benchmark-Werten.
- **Inhalt:** Enthält Benchmark-Dateien (`MillingX_benchmark.json`) und ein Vergleichstool (`app.py`).

### 4. [combine_test/](combine_test/)
- **Zweck:** Testumgebung für das Kombinieren oder Verarbeiten mehrerer JSON-Datensätze gegen Benchmarks.

### 5. Archivierte Anwendungen
- **2025_08_08 Plotting_App.zip:** Tool zur Visualisierung von Daten.
- **audit_app_zip.zip:** Eine komprimierte Version der Audit-Anwendung.

## Workflow
1. **Extraktion:** PDFs/Excel-Dateien werden via `paper_2_json` oder `xlsx_2_json` hochgeladen.
2. **KI-Verarbeitung:** Gemini extrahiert Metadaten, Maschineninfos, Energiedaten und KPIs nach einem festen Schema.
3. **Validierung:** Die resultierenden JSONs können im `2_json_comparator` gegen Benchmarks geprüft werden.

