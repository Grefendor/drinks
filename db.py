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

def get_user_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    (n,) = cur.fetchone()
    conn.close()
    return n

def create_user(pin: str, name: str, is_admin: bool=False):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (pin, name, is_admin) VALUES (?, ?, ?)",
            (pin, name, int(is_admin))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("PIN schon vergeben")
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
    except sqlite3.IntegrityError:
        raise ValueError("Barcode existiert bereits")
    finally:
        conn.close()

def record_transaction(user_id: int, barcode: str, quantity: int = 1):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, count FROM products WHERE barcode = ?", (barcode,))
    prod = cur.fetchone()
    if not prod:
        conn.close()
        raise ValueError("Unbekannter Barcode")
    prod_id, current_count = prod
    if quantity <= 0:
        conn.close()
        raise ValueError("Ungültige Menge")
    if current_count < quantity:
        conn.close()
        raise ValueError("Produkt nicht mehr vorrätig")
    for _ in range(quantity):
        cur.execute(
            "INSERT INTO transactions (user_id, product_id) VALUES (?, ?)",
            (user_id, prod_id)
        )
    cur.execute(
        "UPDATE products SET count = count - ? WHERE id = ?",
        (quantity, prod_id)
    )
    conn.commit()
    conn.close()

def get_inventory():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, barcode, name, count FROM products ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return rows  # List of (id, barcode, name, count)

def update_product_count(barcode: str, new_count: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE products SET count = ? WHERE barcode = ?", (new_count, barcode))
    if cur.rowcount == 0:
        conn.close()
        raise ValueError("Barcode nicht gefunden")
    conn.commit()
    conn.close()

def update_pin(name: str, new_pin: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET pin = ? WHERE name = ?", (new_pin, name))
    if cur.rowcount == 0:
        conn.close()
        raise ValueError("Name nicht gefunden")
    conn.commit()
    conn.close()


def delete_user(name: str, current_user_id: int):
    """Delete a user by name ensuring at least one admin remains."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, is_admin FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Name nicht gefunden")
    user_id, is_admin = row
    if user_id == current_user_id:
        conn.close()
        raise ValueError("Eigenen Account kann man nicht löschen")
    if is_admin:
        cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        (admin_count,) = cur.fetchone()
        if admin_count <= 1:
            conn.close()
            raise ValueError("Mindestens ein Admin muss bestehen bleiben")
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_product(barcode: str):
    """Delete a product by barcode."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE barcode = ?", (barcode,))
    if cur.rowcount == 0:
        conn.close()
        raise ValueError("Barcode nicht gefunden")
    conn.commit()
    conn.close()


def get_user_summary(user_id: int):
    """Return aggregated consumption for a user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.name, COUNT(t.id) as count
        FROM transactions t
        JOIN products p ON t.product_id = p.id
        WHERE t.user_id = ?
        GROUP BY p.id
        ORDER BY p.name
        """,
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows
