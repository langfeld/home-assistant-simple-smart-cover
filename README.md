# Simple Smart Cover

Eine Home Assistant Integration zur automatischen Steuerung von Rollläden basierend auf Wettervorhersage und Sonnenstand.

## Features

- **Automatische Hochfahrt** morgens zu einer festen Uhrzeit
- **Wetterabhängige Positionierung** tagsüber mit regelmäßiger Neubewertung
- **Sonnenschutz** basierend auf Azimuth, Elevation und Temperatur
- **Automatisches Schließen** bei Sonnenuntergang
- **Ruhemodus** mit konfigurierbarem Zeitraum
- **Pause nach manueller Bedienung**, damit der Intervall-Check nicht sofort überschreibt
- **Testmodus**, um das Verhalten zu beobachten, ohne die Rollläden zu bewegen
- Pro Rollladen-Gruppe ein eigenes **Cover-Entity** plus **Sensoren** für Zielposition und Entscheidungsgrund

## Installation

1. Kopiere den Ordner `custom_components/simple_smart_cover` in dein Home Assistant `custom_components`-Verzeichnis.
2. Starte Home Assistant neu.
3. Gehe zu **Einstellungen → Geräte & Dienste → Integrationen → Hinzufügen**.
4. Suche nach **Simple Smart Cover** und folge dem Einrichtungsdialog.

## Entitäten pro Gruppe

Für jede konfigurierte Rollladen-Gruppe werden folgende Entitäten erstellt:

- **`cover.<name>`** – Virtuelles Cover mit der berechneten Zielposition
- **`sensor.<name>_zielposition`** – Zeigt die berechnete Zielposition in %
- **`sensor.<name>_entscheidung`** – Zeigt den Grund für die Entscheidung

Mögliche Werte für den Entscheidungs-Sensor:

- `cloudy` – bewölktes Wetter
- `sunny_in_angle` – Sonne im Winkel und warm genug
- `sunny_outside_angle` – Sonne außerhalb des Winkels oder zu kalt
- `evening` – abendliches Schließen
- `quiet_time` – Ruhemodus aktiv
- `manual_activity_pause` – Pause nach manueller Bedienung

## Hinweis

Dies ist eine erste Version. Feedback und Verbesserungsvorschläge sind willkommen.
