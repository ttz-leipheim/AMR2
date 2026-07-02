# Omron_Lasercutter_loop

Diese README erklärt kurz und strukturiert Aufbau und Zweck der wichtigsten Dateien und Ordner im Projekt.

**Projektübersicht**
- **main.py**: Startpunkt der Anwendung. Initialisiert Komponenten, lädt Konfiguration und startet die Hauptschleife.
- **requirements.txt**: Benötigte Python-Pakete: `pyyaml`, `rich`, `loguru`.
- **.gitignore**: Git-Ausnahmen (z. B. `__pycache__`).

**Installation/**
- `Installation_Guide.md`: Schritt-für-Schritt-Installationshinweise für dieses Projekt.
- `Start_Lasercutter_cycle.bat`: Windows-Batch zum Starten des Lasercutter-Zyklus (schneller Start für Windows-Systeme).

**config/**
- `robot_config.yaml`: Hauptkonfigurationsdatei für Roboter- und Lasercutter-Parameter (Netzwerk, Sicherheitsgrenzen, Pins, Zeitlimits).

**logs/**
- Enthält aufgezeichnete Routen und Laufprotokolle. Dateinamensmuster: `route_YYYYMMDD_HHMMSS.json` und `.yaml`. Jede Datei repräsentiert einen aufgezeichneten Ablauf oder Testlauf.

**src/** — Hauptcode
- `__init__.py`: Paketinitialisierung.
- `arcl_connection.py`: Schnittstelle/Kommunikation zur Steuerungseinheit (ARCL-Protokoll, Senden/Empfangen von Befehlen).
- `display_logger.py`: Log-Ausgabe speziell für Anzeigezwecke (z. B. Terminal/Display).
- `enhanced_logger.py`: Erweiterte Logging-Funktionen (Datei- und Konsole, Formatierung, Log-Rotation falls vorhanden).
- `goal_validator.py`: Prüft Ziele/Koordinaten auf Gültigkeit und Sicherheitsgrenzen bevor ein Befehl ausgeführt wird.
- `I_O_handler.py`: Treiber/Abstraktion für Ein- und Ausgänge (Sensoren, Aktoren, Not-Aus, Pins).
- `rich_ui.py`: Konsolen-UI mit `rich` (Statusanzeigen, Fortschrittsanzeigen, Benutzerinfos).
- `route_handler.py`: Laden, Parsen und Validieren von Routen/Tasks; Schnittstelle zwischen Route-Daten und Ausführungsmodul.

Hinweis: Der Ordner `__pycache__` enthält kompilierte Python-Dateien und wird von Git ignoriert.

Kurzbeschreibung des Ablaufs
1. `main.py` lädt `robot_config.yaml` und initialisiert Logger und Kommunikationsschnittstellen.
2. Routen werden über `route_handler.py` eingelesen und mit `goal_validator.py` geprüft.
3. `arcl_connection.py` sendet die validierten Befehle an die Hardware.
4. `I_O_handler.py` überwacht Ein-/Ausgänge und Sicherheitszustände während der Ausführung.
5. Laufzeitinformationen und Fehler werden über `enhanced_logger.py` / `display_logger.py` protokolliert und ggf. in `logs/` gespeichert.

Kurze Hinweise zur Anpassung
- Konfiguration: Passe `config/robot_config.yaml` an (Netzwerk, Sicherheitsgrenzen, Zeitlimits).
- Abhängigkeiten: Installiere mit `pip install -r requirements.txt`.
- Windows-Start: Zur schnellen Ausführung nutze `Installation/Start_Lasercutter_cycle.bat`.

Fehlersuche (Quick tips)
- Logs prüfen: `logs/` enthält die aufgezeichneten Routen/Protokolle mit Zeitstempel.
- Kommunikation prüfen: In `arcl_connection.py` nach Netzwerk-/Seriell-Parametern suchen.
- UI-Probleme: `rich_ui.py` regelt die Anzeige; Fehlermeldungen hier deuten meist auf Konfig- oder Abhängigkeitsprobleme.

Weiteres
- Für tiefere Erklärungen einzelner Funktionen öffne die entsprechende Datei in `src/` — die Dateinamen sind selbsterklärend und die Implementierung folgt üblichen Python-Konventionen.

