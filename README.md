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

### Variante 1: Über HACS (empfohlen)

1. Stelle sicher, dass [HACS](https://hacs.xyz/) installiert ist.
2. Öffne HACS und gehe zu **Integrationen**.
3. Klicke oben rechts auf die drei Punkte und wähle **Benutzerdefiniertes Repository**.
4. Füge die URL deines GitHub-Repositorys ein, z. B.:
   ```
   https://github.com/langfeld/home-assistant-simple-smart-cover
   ```
5. Wähle als Kategorie **Integration** aus und bestätige.
6. Suche nach **Simple Smart Cover** in HACS und installiere es.
7. Starte Home Assistant neu.
8. Gehe zu **Einstellungen → Geräte & Dienste → Integrationen → Hinzufügen**.
9. Suche nach **Simple Smart Cover** und folge dem Einrichtungsdialog.

### Variante 2: Manuell

1. Lade die Dateien aus dem Repository herunter.
2. Kopiere den Ordner `custom_components/simple_smart_cover` in dein Home Assistant `custom_components`-Verzeichnis:
   ```
   config/custom_components/simple_smart_cover/
   ```
3. Starte Home Assistant neu.
4. Gehe zu **Einstellungen → Geräte & Dienste → Integrationen → Hinzufügen**.
5. Suche nach **Simple Smart Cover** und folge dem Einrichtungsdialog.

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
