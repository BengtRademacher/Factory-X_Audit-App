# Overview: Audit Assistant

Diese Overview beschreibt die zentrale Logik der Factory-X Audit-App nach der Neuausrichtung auf den **Audit Assistant**. Die App ist nicht mehr als Sammlung gleichwertiger Tabs gedacht, sondern als gefuehrter Audit-Prozess: Messdaten hinein, nachvollziehbare Auswertung heraus.

## Zielbild

Der Audit Assistant soll aus realen Maschinenmessdaten einen belastbaren Energie-Audit-Draft erzeugen. Er verbindet klassische Datenanalyse mit kontrollierter KI-Unterstuetzung:

- Daten werden zuerst technisch profiliert.
- Messkanaele werden strukturiert und mit Konfidenz begruendet.
- Der Mensch prueft und bestaetigt das Mapping.
- Erst danach werden Energie-KPIs berechnet.
- Lokale Literatur wird als Evidence Layer eingebunden.
- Das Ergebnis wird als editierbarer Managementbericht exportiert.

Damit ist die App auf einen Audit-Workflow ausgerichtet, nicht auf isolierte Datei-Konverter.

## Workflow

```text
Messdatei
  -> Measurement Profile
  -> AI-/Heuristik-Mapping
  -> manuelle Freigabe
  -> KPI-Berechnung
  -> Literature Evidence
  -> Audit Draft
  -> Management PDF
```

## 1. Maschinen- und Messkontext

Der Prozess beginnt mit Audit-Metadaten:

- Maschinenname
- Bediener
- Betriebszustand
- Material
- Messdatei

Diese Informationen werden nicht nur fuer Dateinamen verwendet. Sie fliessen auch in Bewertung, Evidence-Auswahl und Berichtstext ein.

## 2. Measurement Profile

Nach dem Upload erstellt die App ein Profil der Messdatei. Dabei werden unter anderem erkannt:

- Zeilenanzahl
- potenzielle Zeitspalte
- geschaetzte Abtastrate
- numerische und nicht numerische Spalten
- fehlende Werte
- Minimum, Maximum, Mittelwert und Standardabweichung
- Einheitshinweise wie `W`, `kW` oder `s`

Dieses Profil ist die Grundlage fuer alle weiteren Automatisierungen. Die LLM-Komponente bekommt also nicht die rohe Datei als unstrukturierte Black Box, sondern ein kompaktes, pruefbares Datenprofil.

## 3. Channel Mapping

Das Channel Mapping uebersetzt Rohspalten in auditfaehige Verbraucher. Jeder erkannte Kanal wird mit folgenden Feldern beschrieben:

| Feld | Bedeutung |
| --- | --- |
| `source_column` | Originalspalte aus der Messdatei |
| `canonical_name` | lesbarer, auditfaehiger Verbrauchername |
| `medium` | `electric`, `pneumatic` oder `other` |
| `unit` | angenommene Einheit, z. B. `W` oder `kW` |
| `scale_to_watts` | Umrechnungsfaktor auf Watt |
| `sampling_rate_hz` | verwendete Abtastrate |
| `confidence` | Konfidenz des Mapping-Vorschlags |
| `rationale` | kurze Begruendung |

Das Mapping kann lokal heuristisch erzeugt oder per LLM vorgeschlagen werden. Anwender koennen zusaetzliche Hinweise geben, etwa dass bestimmte Spalten pneumatische Verbraucher darstellen oder bereits in Kilowatt vorliegen.

Wichtig: Das Mapping wird nicht blind uebernommen. Es wird im Editor angezeigt und muss freigegeben werden, bevor die Audit-Berechnung startet.

## 4. KPI-Berechnung

Nach der Freigabe normalisiert die App alle relevanten Kanaele auf Watt und berechnet elektrische sowie pneumatische Kennzahlen. Die Energie wird ueber die Zeitachse integriert, nicht nur aus Mittelwerten geschaetzt.

Berechnet werden unter anderem:

- Energie je Kanal in kWh
- Mittelwert, Median, Minimum, Maximum und Standardabweichung
- Zeitpunkt der Spitzenleistung
- elektrische Gesamtsumme
- pneumatische Gesamtsumme
- Duty Cycle fuer elektrische und pneumatische Verbraucher
- Gesamtenergie
- mittlere Leistung
- Energierate in kWh pro Stunde
- Top-Verbraucher nach Energieanteil

Das Ergebnis wird als Audit JSON im Working Store gespeichert und steht fuer weitere Auswertungen bereit.

## 5. Literature Evidence

Die Literaturdatenbank wird als lokaler Evidence Layer genutzt. Aus vorhandenen Literatur-JSONs erzeugt die App Evidence Cards, die einzelne Aussagen, Kennzahlen oder Kontextinformationen enthalten.

Die Auswahl relevanter Evidence Cards beruecksichtigt aktuell:

- Materialbezug
- Maschinen- oder Prozessbezug
- Energie-, Leistungs- und Effizienzbegriffe
- vorhandene verwertbare Werte

Die Evidence Cards sind keine externe Live-Recherche. Sie bilden nur das ab, was zuvor lokal ueber den Document-Import in die Literaturdatenbank gebracht wurde.

## 6. Audit Draft

Aus Audit-Ergebnis, Evidence Cards und manuellen Notizen erzeugt die App einen editierbaren Audit-Draft. Er besteht aus:

- Executive Summary
- Ampelbewertung fuer Datenqualitaet, Energieniveau und Benchmark-Fit
- Key Metrics
- Top-Verbrauchern
- empfohlenen Massnahmen
- manuellen Annahmen und Notizen
- referenzierter Literatur-Evidenz

Die Ampeln sind bewusst einfach gehalten:

| Bereich | Bewertungslogik |
| --- | --- |
| Datenqualitaet | abhaengig von Mapping-Konfidenz und erkannter Zeitspalte |
| Energieniveau | abhaengig von der Energierate |
| Benchmark-Fit | abhaengig von Anzahl und Passung lokaler Evidence Cards |

Der Draft ist ein Arbeitsstand, kein unveraenderliches KI-Ergebnis. Die fachliche Redaktion bleibt Teil des Workflows.

## 7. Management Report

Am Ende erzeugt der Audit Assistant einen PDF-Bericht fuer Management- und Projektkommunikation. Der Report fasst zusammen:

- Executive Summary
- Ampelbewertung
- Kernkennzahlen
- Energieverteilung
- empfohlene Massnahmen
- Literatur-Evidenz
- manuelle Notizen
- Mapping-Zusammenfassung

Damit wird aus Messdaten ein nachvollziehbares Audit-Artefakt, das weitergegeben und diskutiert werden kann.

## Rolle der bisherigen Tabs

Die bestehenden Tabs bleiben im aktuellen Stand nutzbar, werden aber perspektivisch anders eingeordnet:

| Tab | Zukuenftige Rolle |
| --- | --- |
| `Document -> JSON` | Datenzufuhr fuer die Literaturdatenbank und Evidence Cards |
| `Data -> JSON` | technischer Baustein fuer Messdatenauswertung, langfristig im Audit Assistant |
| `JSON Comparison` | Vergleichslogik fuer Benchmarks, langfristig als Audit-Erweiterung |
| `Ask about data` | Chat- und Rueckfragefunktion, langfristig kontextuell im Audit Assistant |

Der zentrale Nutzerpfad soll im ersten Tab liegen. Alles andere wird Zuarbeit, Seitenfunktion oder entfaellt.

## Leitprinzipien

- **Daten zuerst**: Jede Bewertung startet mit Messprofil und berechneten Kennzahlen.
- **Automatisierung mit Kontrolle**: KI darf vorschlagen, aber kritische Mappings werden geprueft.
- **Nachvollziehbarkeit**: Mapping, Konfidenzen, Annahmen und Evidence bleiben sichtbar.
- **Lokale Evidenz**: Literaturbezug entsteht aus der gepflegten lokalen Datenbasis.
- **Bericht statt Demo**: Ziel ist ein verwertbarer Audit-Draft mit Management-PDF.

## Nicht-Ziele

- Kein vollautomatisches Zertifikat ohne fachliche Pruefung.
- Keine reine Chat-App fuer Energiedaten.
- Keine dauerhafte Tab-Sammlung gleichwertiger Einzeltools.
- Keine Live-Literaturrecherche ohne lokale Evidenzbasis.

## Naechste Entwicklungsrichtung

Die naechsten Schritte sollten den Audit Assistant weiter verdichten:

- alte Tab-Funktionen in Sidebar oder Audit-Workflow integrieren
- Audit-Projekte persistenter speichern
- Evidence-Auswahl fachlich feiner gewichten
- Draft-Bewertungen konfigurierbar machen
- PDF-Bericht um projektspezifische Templates erweitern
- Chat-Funktion direkt auf aktuellem Audit-Kontext aufsetzen
