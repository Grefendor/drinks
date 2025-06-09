# db.py
import sqlite3

DB_PATH = "drinks.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=FULL;")
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY,
            pin       TEXT UNIQUE NOT NULL,
            name      TEXT NOT NULL,
            is_admin  INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id       INTEGER PRIMARY KEY,
            barcode  TEXT UNIQUE NOT NULL,
            name     TEXT NOT NULL,
            count    INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            ts          DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)    REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    conn.close()

def create_user(pin: str, name: str, is_admin: bool=False):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (pin, name, is_admin) VALUES (?, ?, ?)",
            (pin, name, int(is_admin))
        )
        conn.commit()
        print(f"User '{name}' angelegt (admin={is_admin}).")
    except sqlite3.IntegrityError:
        print("Fehler: Diese PIN ist bereits vergeben!")
    finally:
        conn.close()

def authenticate(pin: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, is_admin FROM users WHERE pin = ?",
        (pin,)
    )
    row = cur.fetchone()
    conn.close()
    return row  # (id, name, is_admin) oder None

def create_product(barcode: str, name: str, count: int=0):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO products (barcode, name, count) VALUES (?, ?, ?)",
            (barcode, name, count)
        )
        conn.commit()
        print(f"Produkt '{name}' (Barcode: {barcode}) mit Bestand {count} angelegt.")
    except sqlite3.IntegrityError:
        print("Fehler: Dieser Barcode ist bereits vorhanden!")
    finally:
        conn.close()

def record_transaction(user_id: int, barcode: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM products WHERE barcode = ?", (barcode,))
    prod = cur.fetchone()
    if not prod:
        print("Unbekannter Barcode. Bitte Produkt vorher anlegen.")
    else:
        prod_id = prod[0]
        cur.execute(
            "INSERT INTO transactions (user_id, product_id) VALUES (?, ?)",
            (user_id, prod_id)
        )
        cur.execute(
            "UPDATE products SET count = count - 1 WHERE id = ?",
            (prod_id,)
        )
        conn.commit()
        print("Buchung erfolgreich.")
    conn.close()

def get_inventory():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, barcode, name, count FROM products ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_product_count(barcode: str, new_count: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE products SET count = ? WHERE barcode = ?",
        (new_count, barcode)
    )
    if cur.rowcount == 0:
        raise ValueError("Barcode nicht gefunden")
    conn.commit()
    conn.close()
