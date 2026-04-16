# Layout und Assets

Diese Datei beschreibt die benoetigten Layout-Assets der Factory-X Audit-App.

## Asset-Verzeichnis

Alle visuellen Basisdateien liegen in `assets/`.

| Datei | Zweck |
| --- | --- |
| `FX_logo_top_left.png` | Factory-X Logo fuer `st.logo()` und Sidebar-Branding |
| `FX_style_top_right.svg` | Dekoratives Hintergrundelement oben rechts |

## Einbindung

Die Assets werden in `ui.common.inject_custom_styles()` und `app.py` genutzt:

- `st.logo("assets/FX_logo_top_left.png")`
- Hintergrund-SVG als Base64 eingebettet
- Sidebar-Header wird auf das Logo abgestimmt

## Layout-Regeln

- Das Logo darf die Sidebar dominieren, aber nicht die Einstellungsflaeche verdraengen.
- Das Hintergrundelement bleibt dekorativ und darf Inhalte nicht ueberlagern.
- Audit-Tabellen, Mapping-Editoren und Kennzahlen haben Vorrang vor Branding-Flaechen.
- Neue Assets sollten im gleichen Ordner liegen und mit sprechendem Dateinamen dokumentiert werden.
