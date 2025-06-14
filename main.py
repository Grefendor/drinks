import sqlite3
import requests
from db import (
    init_db, authenticate, create_user, create_product,
    record_transaction, get_inventory, update_product_count,
    delete_user, delete_product, get_user_summary
)
from admin import export_pdf, export_users_pdf, export_inventory_pdf

def fetch_product_name_online(barcode: str) -> str:
    """
    Kostenlose Abfrage bei OpenFoodFacts.
    Liefert Produktname oder wirft Exception, falls nicht gefunden.
    """
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == 1 and data["product"].get("product_name"):
        return data["product"]["product_name"]
    raise RuntimeError("Produkt nicht gefunden oder keine Daten verfügbar")

def ensure_initial_admin():
    conn = sqlite3.connect("drinks.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    (user_count,) = cur.fetchone()
    conn.close()
    if user_count == 0:
        print("=== Erster Start: Initialen Admin anlegen ===")
        while True:
            pin  = input("Admin-PIN: ").strip()
            name = input("Admin-Name: ").strip()
            if pin and name:
                create_user(pin, name, is_admin=True)
                print(f"Initialer Admin '{name}' angelegt.\n")
                break
            print("PIN und Name dürfen nicht leer sein.")

def show_inventory():
    print("\n=== Aktueller Bestand ===")
    for _id, barcode, name, count in get_inventory():
        print(f"{_id}: {name} (Barcode: {barcode}) – Bestand: {count}")
    print()

def edit_inventory():
    barcode = input("Barcode des Produkts zum Bearbeiten: ").strip()
    try:
        # suche altes
        inv = [(b, n, c) for (_, b, n, c) in get_inventory() if b == barcode]
        if not inv:
            print("Produkt nicht gefunden.")
            return
        _, name, old = inv[0]
        new = input(f"Neuer Bestand für '{name}' (bisher {old}): ").strip()
        new_count = int(new)
        update_product_count(barcode, new_count)
        print("Bestand aktualisiert.")
    except ValueError as e:
        print(f"Fehler: {e}")

def delete_user_cli(current_user_id: int):
    name = input("Name des Nutzers zum Löschen: ").strip()
    if not name:
        return
    confirm = input(f"{name} wirklich löschen? (j/N): ").lower().startswith("j")
    if not confirm:
        return
    try:
        delete_user(name, current_user_id)
        print("Nutzer gelöscht.")
    except Exception as e:
        print(f"Fehler: {e}")


def delete_product_cli():
    bc = input("Barcode des Produkts zum Löschen: ").strip()
    if not bc:
        return
    confirm = input(f"Produkt {bc} löschen? (j/N): ").lower().startswith("j")
    if not confirm:
        return
    try:
        delete_product(bc)
        print("Produkt gelöscht.")
    except Exception as e:
        print(f"Fehler: {e}")


def admin_menu(current_user_id: int):
    while True:
        print("\n=== Admin-Menü ===")
        print("1) Neuen Nutzer anlegen")
        print("2) Neues Produkt anlegen")
        print("3) Bestand anzeigen")
        print("4) Bestand bearbeiten")
        print("5) PDF-Report exportieren")
        print("6) Userliste exportieren")
        print("7) Produktliste exportieren")
        print("8) Nutzer löschen")
        print("9) Produkt löschen")
        print("10) Logout")
        choice = input("Auswahl: ").strip()
        if choice == "1":
            pin   = input("Neue PIN: ").strip()
            name  = input("Name des Nutzers: ").strip()
            admin = input("Admin? (j/N): ").lower().startswith("j")
            create_user(pin, name, admin)
        elif choice == "2":
            bc = input("Produkt-Barcode: ").strip()
            try:
                name = fetch_product_name_online(bc)
                print(f"Online gefunden: {name}")
            except Exception as e:
                print(f"Online-Abfrage fehlgeschlagen: {e}")
                name = input("Produktname manuell eingeben: ").strip()
            cnt = input("Anfangsbestand (default 0): ").strip()
            cnt = int(cnt) if cnt.isdigit() else 0
            create_product(bc, name, cnt)
        elif choice == "3":
            show_inventory()
        elif choice == "4":
            edit_inventory()
        elif choice == "5":
            export_pdf()
        elif choice == "6":
            export_users_pdf()
        elif choice == "7":
            export_inventory_pdf()
        elif choice == "8":
            delete_user_cli(current_user_id)
        elif choice == "9":
            delete_product_cli()
        elif choice == "10":
            break
        else:
            print("Ungültige Auswahl.")

def user_menu(user_id: int, user_name: str):
    summary = get_user_summary(user_id)
    print(f"\n=== Übersicht für {user_name} ===")
    if summary:
        for name, cnt in summary:
            print(f"{name}: {cnt}")
    else:
        print("Keine Buchungen vorhanden.")
    print("Bitte Barcode scannen…")
    barcode = input().strip()
    record_transaction(user_id, barcode)

def main():
    init_db()
    ensure_initial_admin()
    while True:
        pin = input("\nPIN eingeben (oder 'exit'): ").strip()
        if pin.lower() == 'exit':
            break
        auth = authenticate(pin)
        if not auth:
            print("Falscher PIN.")
            continue
        user_id, name, is_admin = auth
        if is_admin:
            admin_menu(user_id)
        else:
            user_menu(user_id, name)

if __name__ == "__main__":
    main()
