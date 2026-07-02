start_robot.bat - Übertragungs-Anleitung

✅ Übertragung Schritt-für-Schritt

1. Auf NEUEN Computer kopieren
Methode	Anleitung
USB-Stick	Drag&Drop → Projektordner komplett kopieren
E-Mail	ZIP → senden → entpacken
TeamViewer	Ordner freigeben → kopieren
Git	git push → git clone

2. Auf DESKTOP ziehen

Rechtsklick start_robot.bat → "Kopieren"
DESKTOP → Rechtsklick → "Einfügen"

3. Pfad anpassen 

    1. DESKTOP » start_robot.bat → RECHTSKLICK → "Bearbeiten"
    2. Zeile 6 finden:
    set "PROJECT_PATH=C:\Users\anal8266\Documents\Omron\Programmierung\omron_robot_control"

    3. NEUEN Pfad zum Skript eingeben

    4. Programm nach Pfadkorrektur starten

## ❓ Häufige Probleme
| Problem | Lösung |
|---------|--------|
| `main.py nicht gefunden` | Projektordner nicht verschieben |
| `Python nicht gefunden` | Python 3.8+ installieren |
| `Connection failed` | Robot im selben Netzwerk |

🎯 **Fertig!**

DESKTOP » Doppelklick start_robot.bat
✅ "✓ Projektverzeichnis: C:\Users\NEUER_NAME\..."
✅ Robot verbindet + Display "Connected!"
✅ Route Loop startet automatisch
