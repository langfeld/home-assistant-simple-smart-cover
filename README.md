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
- **`binary_sensor.<name>_pause_aktiv`** – Zeigt an, ob die Pause nach manueller Bedienung aktiv ist
- **`sensor.<name>_pause_verbleibend`** – Zeigt die verbleibende Pausenzeit in Minuten
- **`button.<name>_pause_zuruecksetzen`** – Setzt die manuelle Pause sofort zurück

Mögliche Werte für den Entscheidungs-Sensor:

- `cloudy` – bewölktes Wetter
- `sunny_in_angle` – Sonne im Winkel und warm genug
- `sunny_outside_angle` – Sonne außerhalb des Winkels oder zu kalt
- `evening` – abendliches Schließen
- `quiet_time` – Ruhemodus aktiv
- `manual_activity_pause` – Pause nach manueller Bedienung

### Diagnose-Attribute

Der Entscheidungs-Sensor liefert zusätzlich zum State das Attribut `decision_details`. Darin findest du alle aktuellen Mess- und Grenzwerte, die zur Entscheidung geführt haben:

```yaml
decision_details:
  is_evening: false
  is_cloudy: false
  weather_condition: sunny
  sun_azimuth: 210.5
  sun_elevation: 45.2
  window_orientation: 180
  angle_diff: 30.5
  temperature: 22.3
  thresholds:
    sun_angle_tolerance: 25
    min_sun_elevation: 10
    temp_threshold: 20
  checks:
    angle_in_range: false
    elevation_high_enough: true
    temp_high_enough: true
```

Das ist besonders hilfreich, wenn der State `sunny_outside_angle` lautet: Anhand von `checks` siehst du sofort, ob die Sonne außerhalb des Winkels steht, zu tief steht oder es zu kalt ist.

## Hinweis

Dies ist eine erste Version. Feedback und Verbesserungsvorschläge sind willkommen.
