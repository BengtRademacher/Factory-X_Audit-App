<p align="center">
  <img src="assets/FX_logo_top_left.png" alt="Factory-X Logo" width="300">
</p>

# Factory-X Audit-App

*Stand: 15. April 2026*

Die **Factory-X Audit-App** ist eine Streamlit-Anwendung fuer datenbasierte Energie-Audits in Fertigungsprozessen. Im Mittelpunkt steht der **Audit Assistant**: ein gefuehrter Workflow, der Messdaten profiliert, Messkanaele strukturiert, Energie-KPIs berechnet, lokale Literatur-Evidenz einbindet und daraus einen editierbaren Managementbericht erzeugt.

Die bisherigen Einzeltabs bleiben als Werkzeuge vorhanden, sind aber nicht mehr das Zielbild der App. Langfristig werden sie in den Audit Assistant, die Sidebar oder eine kompaktere Arbeitsflaeche ueberfuehrt.

## Zentrale Funktion

Der Audit Assistant fuehrt durch den kompletten Auswertungsprozess:

1. **Messdaten laden**: Upload von Excel- oder CSV-Dateien mit Maschinenmessdaten.
2. **Messprofil erstellen**: Automatische Erkennung von Zeitspalte, Abtastrate, numerischen Kanaelen, Wertebereichen und Einheitenhinweisen.
3. **Kanaele zuordnen**: KI-gestuetztes oder heuristisches Mapping von Rohspalten auf elektrische, pneumatische oder sonstige Verbraucher.
4. **Mapping pruefen**: Menschliche Freigabe ueber einen editierbaren Mapping-Table mit Konfidenz und Begruendung.
5. **Audit berechnen**: Ermittlung von Energie, Leistung, Duty Cycles, Top-Verbrauchern und elektrischen/pneumatischen Summen.
6. **Evidenz einbinden**: Auswahl passender Evidence Cards aus der lokalen Literaturdatenbank.
7. **Audit-Draft erzeugen**: Managementorientierte Zusammenfassung mit Ampelbewertung, Massnahmen und manuellen Annahmen.
8. **PDF exportieren**: Download eines Management Audit Reports.

## Unterstuetzende Bereiche

| Bereich | Rolle im aktuellen Stand |
| --- | --- |
| **Audit Assistant** | Primaerer Workflow fuer automatisierte, datenbasierte Audit-Auswertung. |
| **Document -> JSON** | Importiert Papers, Tabellen oder JSON-Dateien in die lokale Literaturdatenbank. Diese Daten dienen spaeter als Benchmark-/Evidence-Basis. |
| **Data -> JSON** | Klassischer Messdatenrechner fuer bekannte Spaltennamen. Funktional nuetzlich, aber perspektivisch Teil des Audit Assistant. |
| **JSON Comparison** | Vergleich gespeicherter Audits mit Literatur-Benchmarks. Perspektivisch eher Analysebaustein als eigener Haupttab. |
| **Ask about data** | Explorative Rueckfragen zu Audit-Daten. Perspektivisch Assistenzfunktion innerhalb des Audit-Flows. |

## Datenanforderungen

- Messdateien als `.xlsx`, `.xls` oder `.csv`
- Eine Zeitachse, idealerweise als `elapsedTime`, `time`, `timestamp` oder vergleichbarer Spaltenname
- Leistungs- oder Energieverbrauchskanaele in Watt oder Kilowatt
- Optional: Maschinenname, Betriebszustand, Material und Bediener als Audit-Kontext

Der Audit Assistant kann unbekannte Spaltennamen vorschlagen und Einheiten schaetzen. Kritische Entscheidungen bleiben bewusst editierbar, bevor eine Audit-Berechnung gespeichert wird.

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/Factory-X_Audit-App.git
cd Factory-X_Audit-App
pip install -r requirements.txt
streamlit run app.py
```

Fuer LLM-Funktionen wird ein OpenRouter API-Key benoetigt. Lokal kann er in `.streamlit/secrets.toml` hinterlegt werden:

```toml
[openrouter]
api_key = "sk-or-v1-DEIN_OPENROUTER_API_KEY"
```

## Projektstruktur

```text
Factory-X_Audit-App/
|-- app.py                    # Streamlit-Einstieg und Tab-Layout
|-- config/                   # Einstellungen, Prompts, Maschinenvariablen
|-- core/                     # Datenparser, JSON-Extraktion, LLM-Anbindung
|-- database/                 # Lokale Literaturdatenbank und Audit-Speicher
|-- services/                 # Visualisierung und PDF-/Excel-Export
|-- ui/                       # Streamlit-Oberflaeche, Sidebar und Tabs
|-- workflows/                # Audit-, Mapping-, Evidence- und Vergleichslogik
|-- tests/                    # Kernlogik-Tests
|-- assets/                   # Factory-X Logo und Layout-Grafiken
`-- data/                     # Lokale Arbeitsdaten, Literatur und Audits
```

## Technologie-Stack

| Kategorie | Technologie |
| --- | --- |
| App-Framework | Streamlit |
| Datenanalyse | Pandas, NumPy |
| Visualisierung | Plotly |
| LLM-Anbindung | OpenRouter |
| Berichtsexport | ReportLab |
| Validierung / Settings | Pydantic Settings |

---

<p align="center">
  <i>Factory-X Audit-App: von Maschinenmessdaten zu nachvollziehbarer Audit-Entscheidung.</i>
</p>
