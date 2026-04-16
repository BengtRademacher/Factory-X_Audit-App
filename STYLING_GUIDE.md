# Styling Guide: Factory-X Audit-App

Diese Datei dokumentiert die visuellen Konventionen der Streamlit-App. Der Fokus liegt auf einer ruhigen Audit-Oberflaeche: Daten, Mapping, Evidenz und Bericht sollen schnell erfassbar bleiben.

## Grundhaltung

- Die App wirkt wie ein Arbeitswerkzeug, nicht wie eine Landingpage.
- Der erste Tab ist der operative Audit Assistant.
- Visuelle Elemente unterstuetzen Orientierung, ohne Messdaten oder Tabellen zu ueberdecken.
- Factory-X Branding bleibt sichtbar, aber die Datenflaeche bleibt priorisiert.

## Layout

| Bereich | Konvention |
| --- | --- |
| Page Config | `layout="wide"` fuer breite Tabellen, Dateneditoren und Charts |
| Haupttitel | Icon plus Titel `Factory-X Audit-App` |
| Sidebar | API-Key, Modellwahl und globale Einstellungen |
| Tabs | Aktuell vorhanden, langfristig Konsolidierung in Audit Assistant und Sidebar |
| Content | Prozessabschnitte mit Subheadern, Dividern und klaren Handlungsbuttons |

## Haupttitel

Der Titel wird in `ui.common.render_main_title()` als HTML-Snippet gerendert.

- Icon: `analytics`
- Schriftgroesse: `48px`
- Schriftgewicht: `700`
- Abstand zwischen Icon und Text: `24px`
- Letter Spacing: `0.8px`

## Tab Header

Tab-Ueberschriften werden ueber `ui.common.render_tab_header()` erzeugt.

- Material Symbol links
- Titel als `h2`
- kurze Caption zur fachlichen Funktion
- Divider als Abschnittsgrenze

## Sidebar

Die Sidebar ist Steuerzentrum, nicht Hauptarbeitsflaeche.

- Logo im Streamlit-Sidebar-Header
- API-Key-Auswahl ueber Pills
- Modellwahl ueber Selectbox
- kurze Hinweise zu kostenlosen Modellen und Rate Limits
- Version/Fussnote am Ende

## Farben

Die zentrale Palette liegt in `config/settings.py`.

| Name | Hex | Nutzung |
| --- | --- | --- |
| Violett | `#4B5BA9` | Chart-Farbe |
| Blau | `#006DB9` | Grundfarbe / Hintergrundakzent |
| Hellblau | `#007CC5` | Primary-Aktion und Charts |
| Dunkelgruen | `#01A579` | Erfolg / positive Ampel |
| Hellgruen | `#B1CB21` | Secondary-Akzent |
| Gelb | `#F9B31A` | Warnung / mittlere Ampel |
| Orange | `#EF7100` | Zusatzakzent |
| Rot | `#E50037` | Fehler / kritische Ampel |

## Icons

Die App nutzt Google **Material Symbols Rounded**.

- CSS-Klasse: `.material-symbols-rounded`
- Standardausrichtung: `vertical-align: middle`
- Abstand rechts: `8px`
- Font Variation: `opsz 24`

Typische Icons:

| Funktion | Icon |
| --- | --- |
| Audit Assistant | `assignment` |
| Document Import | `description` |
| Messdaten | `query_stats` |
| Vergleich | `compare_arrows` |
| Haupttitel | `analytics` |

## Hintergrund und Assets

Das Hintergrundelement wird in `ui.common.inject_custom_styles()` eingebunden.

- Datei: `assets/FX_style_top_right.svg`
- Position: oben rechts, fixiert
- Groesse: `400px x 400px`
- Opacity: `0.4`
- Rotation: `180deg`

Zusaetzlich erzeugt die App einen dezenten radialen Hintergrundakzent aus der Factory-X Blaupalette.

## Komponenten

- Primaere Aktionen verwenden `type="primary"` und `use_container_width=True`, wenn sie den naechsten Workflow-Schritt ausloesen.
- Tabellen und Editoren verwenden `use_container_width=True`.
- Expander werden fuer Details genutzt, z. B. Measurement Profile, Mapping Chat, Evidence Cards oder JSON-Details.
- Metriken stehen in Spalten, damit Gesamtenergie, Leistung, Energierate und Dauer schnell vergleichbar sind.

## Audit-Assistant-spezifische UI

Der zentrale Workflow ist nummeriert:

1. Machine and Measurement Data
2. AI-assisted Channel Mapping
3. Metrics and Local Literature Evidence
4. Editable Audit Draft
5. Management Report

Diese Reihenfolge sollte in kuenftigen UI-Aenderungen erhalten bleiben, auch wenn alte Tabs in die Sidebar oder in den ersten Tab verschoben werden.
