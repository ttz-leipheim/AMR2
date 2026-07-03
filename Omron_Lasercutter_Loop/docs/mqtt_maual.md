MQTT-Steuerungshandbuch – OMRON AMR

Dieses Handbuch beschreibt die Konfiguration, den Start und die Steuerung des
OMRON AMR über den HiveMQ Cloud-Broker.

1. Voraussetzungen & Konfiguration

Tragen Sie die Zugangsdaten für Ihren HiveMQ Cloud-Broker in die
Konfigurationsdatei config/robot_config.yaml ein:

# ============================================================================
# MQTT CONNECTION - 100% Config-gesteuert
# ============================================================================
mqtt:
  broker: "6cb0dc4093f24795858c66688fbff7a0.s1.eu.hivemq.cloud"
  port: 8883                         # Port 8883 für verschlüsseltes SSL/TLS
  tls: true                          # TLS aktivieren
  client_id: "Robot02_MQTT_Client"
  username: "Ihr_HiveMQ_Benutzer"    # In HiveMQ erstellter Benutzername
  password: "Ihr_HiveMQ_Passwort"    # In HiveMQ erstelltes Passwort
  topics:
    command: "robot/Robot02/command"
    status: "robot/Robot02/status"

2. Programm starten

Führen Sie das Hauptprogramm in Ihrem Terminal im Projektverzeichnis aus:

python main.py

  - Systemverhalten beim Start:
      - Das Programm baut eine verschlüsselte Verbindung zu HiveMQ Cloud auf
        (bestätigt durch ✓ Connected to MQTT Broker...).
      - Der Roboter initialisiert sich im Wartemodus (WAITING_FOR_ORDER). Er
        verbleibt an seiner Startposition und wartet auf eingehende
        MQTT-Befehle.

3. Befehlsreferenz (Topic: robot/Robot02/command)

Senden Sie Befehle als Klartext (Payloads) an das konfigurierte Command-Topic.

3.1 Allgemeine Systembefehle

| Befehl                              | Aktion            | Beschreibung                                                                                                        |
| :---------------------------------- | :---------------- | :------------------------------------------------------------------------------------------------------------------ |
| **`start`** *(oder `order`, `run`)* | Automatik starten | Startet die automatische Pendelroute oder setzt sie nach einer Pause fort.                                          |
| **`stop`** *(oder `pause`)*         | Pause am Ziel     | Pausiert den AMR. Er fährt noch bis zum nächsten Zielpunkt (bzw. beendet die aktive Aufgabe) und wartet dort.       |
| **`restart`**                       | System-Reset      | Bricht den aktuellen Schritt sofort ab, setzt den Zyklus zurück und startet wieder bei **Schritt 1** (Lasercutter). |
| **`dock`** *(oder `charge`)*        | Sofortiges Laden  | Bricht den aktuellen Schritt sofort ab, schickt den AMR **direkt zur Ladestation** und wartet dort im Lademodus.    |

3.2 Einzelschritt-Modus

  - step (oder next): Der AMR führt exakt einen Prozessschritt der Route aus (z.
    B. eine einzelne Fahrt) und wechselt danach sofort wieder in den Wartemodus
    (WAITING_FOR_ORDER), bis der nächste Schritt-Befehl eintrifft.

3.3 Direkte Subprozess-Ausführung

Sie können vordefinierte Navigations- oder Taster-Aufgaben einzeln aufrufen. Das
laufende Programm wird dabei unterbrochen und der Roboter führt nur diesen
spezifischen Einzelprozess aus:

  - goto:lasercutter: Navigiert direkt zum Lasercutter und pausiert dort.
  - goto:nacharbeit: Navigiert direkt zur Nacharbeit und pausiert dort.
  - task:load_plates: Startet direkt die Taster-Abfrage für das Laden am
    Lasercutter und pausiert danach.
  - task:unload_parts: Startet direkt die Taster-Abfrage für das Entladen an der
    Nacharbeit und pausiert danach.

4. Status-Überwachung (Topic: robot/Robot02/status)

Der AMR sendet alle 2 Sekunden sowie nach jedem abgeschlossenen Prozessschritt
ein JSON-Dokument an das Status-Topic.

4.1 Systemzustände (state)

  - RUNNING: Der Roboter führt eine Navigation oder eine Aufgabe aus.
  - WAITING_FOR_ORDER: Der Roboter steht still und wartet auf einen Start- oder
    Einzelschritt-Befehl.
  - DOCKED_TIMEOUT: Der Roboter stand länger als 10 Minuten im Wartemodus ohne
    neuen Befehl und ist selbstständig zum Laden an die Ladestation gefahren.

4.2 Beispiel-Payload (Zustand: WAITING_FOR_ORDER)

{
  "timestamp": "2026-07-03 11:35:12",
  "robot_name": "Robot02",
  "state": "WAITING_FOR_ORDER",
  "battery": "94.0",
  "location": "Lasercutter",
  "extended_status": "idle at Lasercutter",
  "arcl_status": "idle"
}

5. Beispiele zur CLI-Steuerung

Sie können zur Steuerung grafische Clients wie MQTT Explorer nutzen oder Befehle
über das CLI-Tool mosquitto_pub absetzen (Achten Sie auf die TLS-Parameter für
Port 8883):

  - Route im Automatikbetrieb starten:

    mosquitto_pub -h 6cb0dc4093f24795858c66688fbff7a0.s1.eu.hivemq.cloud -p 8883 -u "Ihr_User" -P "Ihr_Passwort" -L "mqtts://host/robot/Robot02/command" -m "start"

  - Laufenden Betrieb abbrechen und sofort laden:

    mosquitto_pub -h 6cb0dc4093f24795858c66688fbff7a0.s1.eu.hivemq.cloud -p 8883 -u "Ihr_User" -P "Ihr_Passwort" -L "mqtts://host/robot/Robot02/command" -m "dock"

  - Einen einzelnen Zielpunkt manuell anfahren (Subprozess-Direktsteuerung):

    mosquitto_pub -h 6cb0dc4093f24795858c66688fbff7a0.s1.eu.hivemq.cloud -p 8883 -u "Ihr_User" -P "Ihr_Passwort" -L "mqtts://host/robot/Robot02/command" -m "goto:nacharbeit"
