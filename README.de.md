# Simple Smart Cover

Eine Home Assistant Integration zur automatischen Steuerung von Rollläden basierend auf Wettervorhersage und Sonnenstand.

> English version: [README.md](README.md)

## Features

- **Automatische Hochfahrt** morgens zu einer festen Uhrzeit
- **Wetterabhängige Positionierung** tagsüber mit regelmäßiger Neubewertung
- **Sonnenschutz** basierend auf Azimuth, Elevation und Temperatur
- **Automatisches Schließen** bei Sonnenuntergang
- **Ruhemodus** mit konfigurierbarem Zeitraum (die morgendliche Hochfahrzeit wird automatisch hinter das Ende der Ruhezeit verschoben, falls sie in diese fällt)
- **Pause nach manueller Bedienung**, damit der Intervall-Check nicht sofort überschreibt
- **Anwesenheits-basierte Pause-Verlängerung**, damit die Automatik nicht gegen den Nutzer arbeitet, während ein Raum belegt ist (optional, pro Gruppe)
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
- **`sensor.<name>_target_position`** – Zeigt die berechnete Zielposition in %
- **`sensor.<name>_decision`** – Zeigt den Grund für die Entscheidung
- **`binary_sensor.<name>_pause_active`** – Zeigt an, ob die Pause nach manueller Bedienung aktiv ist
- **`sensor.<name>_pause_remaining`** – Zeigt die verbleibende Pausenzeit in Minuten
- **`binary_sensor.<name>_presence_lock`** – Zeigt an, ob die Pause aktuell durch Anwesenheit gehalten wird (sticky oder Nachlauf)
- **`button.<name>_reset_pause`** – Setzt die manuelle Pause sofort zurück

Mögliche Werte für den Entscheidungs-Sensor:

- `cloudy` – bewölktes Wetter
- `sunny_in_angle` – Sonne im Winkel und warm genug
- `sunny_outside_angle` – Sonne außerhalb des Winkels oder zu kalt
- `evening` – abendliches Schließen
- `quiet_time` – Ruhemodus aktiv
- `manual_activity_pause` – Pause nach manueller Bedienung
- `weather_unavailable` – Wetter-Entity nicht verfügbar

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

### Anwesenheits-basierte Pause-Verlängerung

Pro Rollladen-Gruppe kann optional ein Binary-Sensor für Anwesenheit/Bewegung konfiguriert werden. Anwesenheit **alleine startet keine Pause** – sie verlängert nur eine bestehende manuelle Pause, damit die Automatik die Rollläden nicht bewegt, während ein Raum belegt ist.

Verhalten, sobald eine manuelle Pause ausgelöst wurde (z. B. jemand öffnet einen Rollladen per Hand):

- Solange der konfigurierte Anwesenheits-Sensor `on` meldet, bleibt die Pause **sticky** und läuft nicht ab – unabhängig von der eingestellten manuellen Pausendauer.
- Nachdem der Sensor `off` meldet, läuft die Pause noch für den konfigurierten **Nachlauf** (Verlängerung bei Anwesenheit, in Minuten) weiter. Das verhindert, dass die Automatik bei kurzen Abwesenheiten (z. B. etwas aus der Küche holen) eingreift.
- Wenn der Nachlauf abgelaufen ist (oder kein Sensor konfiguriert ist), läuft die manuelle Pause wie gewohnt weiter.
- Der Reset-Button hebt die manuelle Pause und den Nachlauf sofort auf – auch solange Anwesenheit noch `on` ist.

Konfigurationsfelder:

- **`presence_sensor`** – Optionaler Binary-Sensor (z. B. Bewegungs-, Anwesenheits- oder Belegungsmelder).
- **`presence_pause_extension`** – Nachlauf in Minuten nach dem Ausschalten des Sensors. `0` bedeutet nur sticky, kein Nachlauf.

Der Sensor `pause_remaining` zeigt während des sticky-Zustands den konfigurierten Nachlauf-Wert an (die Zeit, die die Pause noch laufen würde, wenn man jetzt den Raum verlässt), und zählt während des Nachlaufs ab dem Abschaltzeitpunkt herunter.

### Morgendliche Hochfahrzeit und Ruhemodus

Fällt die eingestellte morgendliche Hochfahrzeit in das Ruhezeit-Fenster, wird der Morgen-Trigger automatisch auf eine Sekunde nach Ende der Ruhezeit verschoben. Ohne diese Verschiebung würde die morgendliche Auswertung `quiet_time` zurückgeben und keine Bewegung auslösen, sodass die Rollläden den ganzen Tag auf der Abend-Position blieben (insbesondere, wenn die regelmäßige Neubewertung deaktiviert ist). Die Verschiebung wird im Home Assistant-Log protokolliert, damit die effektive Trigger-Zeit sichtbar ist.

### Vorausschauender Forecast-Modus (Tageshöchsttemperatur verwenden)

Wenn **Tageshöchsttemperatur verwenden** aktiviert ist, wechselt die Integration von einer reaktiven zu einer vorausschauenden Entscheidung:

1. **Sonnenstand-Berechnung**: zum Evaluationszeitpunkt (z. B. morgens) berechnet die Integration, wann die Sonne heute in das konfigurierte Fenster fällt (Azimuth innerhalb der Toleranz, Elevation über dem Minimum). Dazu wird die `astral`-Bibliothek (HA-Abhängigkeit) mit den HA-Standorteinstellungen genutzt.
2. **Forecast-Lookup**: wenn die Sonne heute ans Fenster kommt, wird der stündliche Wetter-Forecast abgerufen und die Temperatur sowie Wetterbedingung zum berechneten Sonnenstand-Zeitpunkt extrahiert.
3. **Entscheidung**: die Entscheidung nutzt die vorhergesagte Temperatur und Wetterbedingung zu diesem Zeitpunkt — nicht die aktuelle Sonnenposition oder aktuelle Temperatur. Das bedeutet, dass die Rollläden bei der morgendlichen Auswertung für den ganzen Tag positioniert werden können, selbst wenn die Sonne erst nachmittags ans Fenster kommt.
4. **Fallback**: falls der stündliche Forecast nicht ermittelbar ist (z. B. die Wetter-Entity keinen liefert), fällt die Integration auf den konfigurierten Tageshöchsttemperatur-Sensor und die aktuelle Wetterbedingung zurück.

Dieser Modus ist besonders nützlich, wenn die regelmäßige Neubewertung deaktiviert ist: die morgendliche Auswertung trifft eine einzelne, informierte Entscheidung für den gesamten Tag basierend auf dem Forecast zum relevanten Sonnenstand-Zeitpunkt.

Das Attribut `decision_details` zeigt `forecast_mode: true` und `sun_in_window_time` (ISO-Zeitstempel), wenn dieser Modus aktiv ist, sodass die berechnete Zeit und die Forecast-Werte im Diagnose-Sensor nachvollziehbar sind.

## Sprache

Die Integration liefert englische und deutsche Übersetzungen mit. Home Assistant wählt die Sprache automatisch anhand der HA-Oberflächensprache. Entity-Namen sind auf Englisch, damit sie über alle Spracheinstellungen hinweg stabil bleiben.

## Hinweis

Dies ist eine erste Version. Feedback und Verbesserungsvorschläge sind willkommen.
