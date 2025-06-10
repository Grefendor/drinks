# Getränkekeller

Dieses Projekt verwaltet den Getränkekonsum über eine lokale SQLite-Datenbank. Es
existieren eine einfache Kommandozeilen-Variante (`main.py`) und eine
komfortablere GUI auf Basis von Tkinter (`app.py`).

## Installation

1. Python 3 installieren.
2. Abhängigkeiten mittels `pip install -r requirements.txt` installieren.

## Nutzung

### Kommandozeile

```bash
python main.py
```

Beim ersten Start wird ein Admin-Benutzer mit PIN angelegt. Danach können
Produkte hinzugefügt und Buchungen vorgenommen werden.

### GUI

```bash
python app.py
```

Die GUI bietet dieselben Funktionen und ermöglicht zusätzlich das Erstellen
von PDF-Berichten über den Verbrauch.

## Datenbank

Alle Daten werden in der Datei `drinks.db` gespeichert. Die Tabellen werden beim
Start automatisch erstellt, falls sie noch nicht existieren.

## Funktionen

- Benutzerverwaltung (Admins können neue Benutzer anlegen)
- Produkte per Barcode erfassen
- Buchungen und Bestandsverwaltung
- Export eines Verbrauchsberichts als PDF
- Export der Nutzerliste als PDF
- Export der Produktliste als PDF

