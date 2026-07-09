Omron_Lasercutter_loop

Diese README erklärt kurz und strukturiert Aufbau und Zweck der wichtigsten
Dateien und Ordner im Projekt.

Projektübersicht

  - main.py: Startpunkt der Anwendung. Initialisiert die ARCL- und
    MQTT-Schnittstellen, lädt die Konfiguration und startet die Hauptschleife,
    die auf MQTT-Befehle reagiert.
  - requirements.txt: Benötigte Python-Pakete: pyyaml, rich, loguru und
    paho-mqtt (für die verschlüsselte Anbindung an HiveMQ Cloud).
  - .gitignore: Git-Ausnahmen (z. B. __pycache__, Log-Dateien).

Installation/

  - Installation_Guide.md: Schritt-für-Schritt-Installationshinweise für dieses
    Projekt.
  - Start_Lasercutter_cycle.bat: Windows-Batch zum Starten des
    Lasercutter-Zyklus (schneller Start für Windows-Systeme).

config/

  - robot_config.yaml: Hauptkonfigurationsdatei für Roboter-, Lasercutter- und
    MQTT-Broker-Parameter (Netzwerk, Zugangsdaten für HiveMQ Cloud,
    Sicherheitsgrenzen, Pins, Zeitlimits, Topics).

logs/

  - Enthält aufgezeichnete Routen und Laufprotokolle. Dateinamensmuster:
    route_YYYYMMDD_HHMMSS.json und .yaml. Jede Datei repräsentiert einen
    aufgezeichneten Ablauf oder Testlauf.

src/ — Hauptcode

  - __init__.py: Paketinitialisierung.
  - arcl_connection.py: Schnittstelle/Kommunikation zur AMR-Steuerungseinheit
    (ARCL-Protokoll, Senden/Empfangen von Befehlen).
  - display_logger.py: Log-Ausgabe speziell für Anzeigezwecke (z. B.
    Terminal/Display).
  - enhanced_logger.py: Erweiterte Logging-Funktionen (Datei- und Konsole,
    Formatierung, Log-Rotation falls vorhanden).
  - goal_validator.py: Prüft Ziele/Koordinaten auf Gültigkeit und Existenz auf
    der AMR-Karte, bevor Befehle ausgeführt werden.
  - I_O_handler.py: Treiber/Abstraktion für Ein- und Ausgänge sowie interaktive
    Taster-Aufgaben (z. B. ConfirmButtonTask an den Arbeitsstationen).
  - mqtt_handler.py: Enthält die gesamte MQTT-Kommunikationslogik. Verwaltet die
    verschlüsselte SSL/TLS-Verbindung zu HiveMQ Cloud, abonniert Steuerbefehle
    (start, stop, restart, dock, step sowie Direkt-Subprozesse) und publiziert
    den Roboter-Status fortlaufend als JSON.
  - rich_ui.py: Konsolen-UI mit rich (Statusanzeigen, Fortschrittsanzeigen,
    farbige Protokollierung).
  - route_handler.py: Laden, Parsen und Ausführen der konfigurierten
    Fahrtschritte und Tasks (RouteExecutor).

Kurzbeschreibung des Ablaufs

1.  Initialisierung: main.py lädt die Konfiguration aus
    config/robot_config.yaml, startet den Konsolen-Logger und baut die physische
    Verbindung zum AMR (via arcl_connection.py) auf.
2.  MQTT-Verbindung: mqtt_handler.py stellt eine verschlüsselte Verbindung (TLS
    auf Port 8883) zu HiveMQ Cloud her, abonniert das Command-Topic und versetzt
    das System initial in den Wartemodus (WAITING_FOR_ORDER).
3.  Wartezustand & Start: Sobald der Befehl "start" über das MQTT-Command-Topic
    eingeht, wird die Routen-Validierung via goal_validator.py durchgeführt und
    der automatische Pendelzyklus gestartet.
4.  Schrittweise Abarbeitung: route_handler.py arbeitet die Schritte ab. Der AMR
    navigiert zu den Stationen, wo I_O_handler.py an den Terminals auf die
    physische Bestätigung (Tasterdruck des Bedieners) wartet.
5.  MQTT-Interaktionsmöglichkeiten (Jederzeit):
      - Pause: Bei "stop" beendet der AMR den laufenden Fahrtschritt sicher und
        pausiert am erreichten Ziel.
      - Inaktivitäts-Timeout: Wartet der AMR länger als 10 Minuten im
        Stop-Modus, fährt er selbstständig zurück zur Ladestation (_dock()).
      - Sofortiges Laden: Der Befehl "dock" schickt den AMR unverzüglich zur
        Ladestation zurück.
      - Manuelles Weiterschalten: Über "step" kann der AMR Schritt für Schritt
        manuell durch die Route getaktet werden.
      - Direktsteuerung von Subprozessen: Über "goto:<ziel>" oder
        "task:<aufgabe>" lassen sich einzelne Fahrten oder Taster-Aufgaben auf
        Knopfdruck direkt und außerhalb des Automatik-Loops starten.
6.  Protokollierung: Alle Zustandsänderungen werden lokal in logs/ gesichert und
    gleichzeitig als Echtzeit-JSON-Zustand über das MQTT-Status-Topic gestreut.

Kurze Hinweise zur Anpassung

  - Konfiguration: Passen Sie Netzwerk-Parameter, Roboter-IPs sowie Ihre
    HiveMQ-Cloud-Broker-Zugangsdaten in config/robot_config.yaml an.
  - Abhängigkeiten: Installieren Sie alle Pakete (inklusive der neuen
    MQTT-Bibliotheken) im venv mit:
    pip install -r requirements.txt
  - Windows-Start: Nutzen Sie für den schnellen Windows-Schnellstart die
    Batchdatei Installation/Start_Lasercutter_cycle.bat.

Fehlersuche (Quick tips)

  - Keine Reaktion auf MQTT-Befehle:
      - Prüfen Sie, ob in der Konsole ✓ Connected to MQTT Broker ausgegeben
        wurde. Falls nicht, überprüfen Sie die Broker-Adresse, Port 8883 und die
        HiveMQ-Anmeldedaten in der Konfigurationsdatei.
      - Stellen Sie sicher, dass Ihre Befehle (z. B. start, dock) komplett in
        Kleinbuchstaben und ohne Leerzeichen/Zeilenumbrüche gesendet werden.
  - Lokale Logs prüfen: Der Ordner logs/ enthält strukturierte JSON- und
    YAML-Protokolle aller Fahrten mit genauen Zeitstempeln und eventuellen
    Fehlerursachen.
  - AMR-Verbindungsprobleme: Falls die Kommunikation zum Roboter fehlschlägt,
    überprüfen Sie die Roboter-IP, den ARCL-Port 7171 sowie das Passwort (meist
    admin oder adept) in der Konfiguration.
