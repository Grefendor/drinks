from db import (
    init_db, authenticate, create_user, create_product,
    record_transaction, get_inventory, update_product_count,
    delete_user, delete_product, get_user_summary,
    start_scheduled_backups, stop_scheduled_backups,
)
from admin import export_pdf, export_users_pdf, export_inventory_pdf
from utils import fetch_product_name_online


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_initial_admin():
    """Prompt for the first admin account when the DB is empty."""
    from db import get_user_count
    if get_user_count() > 0:
        return
    print("=== Erster Start: Initialen Admin anlegen ===")
    while True:
        pin = input("Admin-PIN: ").strip()
        name = input("Admin-Name: ").strip()
        if pin and name:
            create_user(pin, name, is_admin=True)
            print(f"Initialer Admin '{name}' angelegt.\n")
            break
        print("PIN und Name duerfen nicht leer sein.")


def _show_inventory():
    print("\n=== Aktueller Bestand ===")
    for pid, barcode, name, count in get_inventory():
        print(f"  {pid}: {name} (Barcode: {barcode}) -- Bestand: {count}")
    print()


def _edit_inventory():
    barcode = input("Barcode des Produkts zum Bearbeiten: ").strip()
    inv = [(b, n, c) for (_, b, n, c) in get_inventory() if b == barcode]
    if not inv:
        print("Produkt nicht gefunden.")
        return
    _, name, old = inv[0]
    new = input(f"Neuer Bestand fuer '{name}' (bisher {old}): ").strip()
    try:
        update_product_count(barcode, int(new))
        print("Bestand aktualisiert.")
    except ValueError as exc:
        print(f"Fehler: {exc}")


def _delete_user_cli(current_user_id: int):
    name = input("Name des Nutzers zum Loeschen: ").strip()
    if not name:
        return
    if not input(f"{name} wirklich loeschen? (j/N): ").lower().startswith("j"):
        return
    try:
        delete_user(name, current_user_id)
        print("Nutzer geloescht.")
    except Exception as exc:
        print(f"Fehler: {exc}")


def _delete_product_cli():
    bc = input("Barcode des Produkts zum Loeschen: ").strip()
    if not bc:
        return
    if not input(f"Produkt {bc} loeschen? (j/N): ").lower().startswith("j"):
        return
    try:
        delete_product(bc)
        print("Produkt geloescht.")
    except Exception as exc:
        print(f"Fehler: {exc}")


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

def _admin_menu(current_user_id: int):
    while True:
        print("\n=== Admin-Menue ===")
        print("1) Neuen Nutzer anlegen")
        print("2) Neues Produkt anlegen")
        print("3) Bestand anzeigen")
        print("4) Bestand bearbeiten")
        print("5) PDF-Report exportieren")
        print("6) Userliste exportieren")
        print("7) Produktliste exportieren")
        print("8) Nutzer loeschen")
        print("9) Produkt loeschen")
        print("10) Logout")
        choice = input("Auswahl: ").strip()

        if choice == "1":
            pin = input("Neue PIN: ").strip()
            name = input("Name des Nutzers: ").strip()
            admin = input("Admin? (j/N): ").lower().startswith("j")
            try:
                create_user(pin, name, admin)
                print("Nutzer angelegt.")
            except ValueError as exc:
                print(f"Fehler: {exc}")
        elif choice == "2":
            bc = input("Produkt-Barcode: ").strip()
            try:
                name = fetch_product_name_online(bc)
                print(f"Online gefunden: {name}")
            except Exception as exc:
                print(f"Online-Abfrage fehlgeschlagen: {exc}")
                name = input("Produktname manuell eingeben: ").strip()
            cnt = input("Anfangsbestand (default 0): ").strip()
            cnt = int(cnt) if cnt.isdigit() else 0
            try:
                create_product(bc, name, cnt)
                print("Produkt angelegt.")
            except ValueError as exc:
                print(f"Fehler: {exc}")
        elif choice == "3":
            _show_inventory()
        elif choice == "4":
            _edit_inventory()
        elif choice == "5":
            export_pdf()
            print("report.pdf erstellt.")
        elif choice == "6":
            export_users_pdf()
            print("users.pdf erstellt.")
        elif choice == "7":
            export_inventory_pdf()
            print("inventory.pdf erstellt.")
        elif choice == "8":
            _delete_user_cli(current_user_id)
        elif choice == "9":
            _delete_product_cli()
        elif choice == "10":
            break
        else:
            print("Ungueltige Auswahl.")


def _user_menu(user_id: int, user_name: str):
    summary = get_user_summary(user_id)
    print(f"\n=== Uebersicht fuer {user_name} ===")
    if summary:
        for name, cnt in summary:
            print(f"  {name}: {cnt}")
    else:
        print("  Keine Buchungen vorhanden.")
    print("Bitte Barcode scannen...")
    barcode = input().strip()
    try:
        record_transaction(user_id, barcode)
        print("Buchung erfolgreich.")
    except ValueError as exc:
        print(f"Fehler: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    init_db()
    start_scheduled_backups()
    _ensure_initial_admin()
    try:
        while True:
            pin = input("\nPIN eingeben (oder 'exit'): ").strip()
            if pin.lower() == "exit":
                break
            auth = authenticate(pin)
            if not auth:
                print("Falscher PIN.")
                continue
            user_id, name, is_admin = auth
            if is_admin:
                _admin_menu(user_id)
            else:
                _user_menu(user_id, name)
    finally:
        stop_scheduled_backups()


if __name__ == "__main__":
    main()
