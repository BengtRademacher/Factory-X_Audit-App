# Styling Guide: Factory-X Energy Data Visualizer

Diese Dokumentation beschreibt das visuelle Design und die Styling-Konventionen der App, um sie in anderen Projekten konsistent wiederverwenden zu können.

---

## 1. Haupttitel (Main Title)
Der Titel wird über ein benutzerdefiniertes HTML-Snippet gerendert.

- **Schriftart:** Standard-Streamlit-Schrift (Sans-Serif) + *Material Symbols Rounded*.
- **Schriftgröße:** `48px`
- **Schriftgewicht:** `700` (Bold)
- **Zeichenabstand (Letter Spacing):** `0.8px`
- **Layout:**
    - `display: flex`
    - `align-items: center`
    - `gap: 24px`
    - `margin-bottom: 1rem`

---

## 2. Sidebar-Styling
Die Sidebar wird durch globales CSS angepasst, um Platz für ein markantes Logo zu schaffen.

### Header & Logo
- **Container-Höhe (`stSidebarHeader`):** `120px !important`
- **Padding:** `1rem` vertikal.
- **Logo-Dimensionen:**
    - Höhe: `100px !important`
    - Breite: `auto !important`

### Struktur
- **Expanders:** Nutzung von `st.expander` für funktionale Gruppierung (z.B. "📊 Datenverarbeitung").
- **Captions:** Kleine graue Hilfstexte via `st.caption`.
- **Interaktion:** Buttons nutzen `use_container_width=True` für ein flächiges Design.

---

## 3. UI-Komponenten (Fonts & Icons)

### Icons
- **Bibliothek:** [Material Symbols Rounded](https://fonts.google.com/icons?icon_style=Rounded)
- **CSS-Klasse:** `.material-symbols-rounded`
- **Styling:** `vertical-align: middle`, `margin-right: 8px`, Font-Variation auf `opsz 24`.

---

## 4. Globales Layout & Hintergrund

- **Main Block Container:** `padding-top: 2rem !important` (Kompensiert den Streamlit-Standardabstand).
- **Transparenz:** Header und Toolbar (`stHeader`, `stToolbar`) sind transparent gesetzt, um Hintergrundgrafiken nicht zu überlagern.
- **Hintergrund-Grafik:** Ein SVG wird oben rechts fixiert:
    - Position: `fixed`, `top: -5px`, `right: -5px`.
    - Größe: `400px x 400px`.
    - Opacity: `0.4`.
    - Rotation: `180deg`.

---

---

*Hinweis: Dieses Dokument dient als Referenz für die konsistente Gestaltung der Factory-X Audit-App.*
