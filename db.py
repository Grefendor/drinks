import hashlib
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "drinks.db"
BACKUP_DIR = Path(__file__).parent / "backups"
MAX_BACKUPS = 30  # keep at most this many backup files

SCHEMA_VERSION = 2  # bump when schema changes

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection & transaction helpers
# ---------------------------------------------------------------------------

@contextmanager
def _connect(*, transaction=False):
    """Yield a connection that is always properly closed.

    If *transaction* is True the connection uses deferred transactions
    (BEGIN / COMMIT / ROLLBACK).  Otherwise autocommit is used for simple
    reads and single-statement writes.
    """
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=30,
        isolation_level="DEFERRED" if transaction else None,
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=FULL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        if transaction:
            conn.commit()
    except BaseException:
        if transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def _rotate_backups():
    """Delete oldest backups when we exceed MAX_BACKUPS."""
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("drinks_*.db"), key=lambda p: p.stat().st_mtime)
    while len(backups) > MAX_BACKUPS:
        old = backups.pop(0)
        old.unlink()
        log.info("Rotated old backup: %s", old.name)


def backup_db(reason: str = "manual") -> Path | None:
    """Create a safe, consistent backup using SQLite's online backup API.

    This is crash-safe even if the DB is being written to concurrently.
    After copying, the backup is verified with ``PRAGMA integrity_check``.
    Old backups beyond *MAX_BACKUPS* are automatically deleted.
    """
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"drinks_{stamp}_{reason}.db"

    # Checkpoint WAL so the main DB file is fully up to date
    src_conn = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except sqlite3.Error:
        pass  # non-fatal: backup API handles WAL pages anyway

    # Use SQLite's backup API for a consistent snapshot
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # Verify the backup is not corrupt
    check_conn = sqlite3.connect(str(dest))
    try:
        result = check_conn.execute("PRAGMA integrity_check").fetchone()
        if result[0] != "ok":
            log.error("Backup integrity check FAILED for %s: %s", dest, result)
            dest.unlink()
            return None
    finally:
        check_conn.close()

    _rotate_backups()
    log.info("Backup created: %s", dest)
    return dest


_backup_timer: threading.Timer | None = None
BACKUP_INTERVAL_SEC = 6 * 60 * 60  # every 6 hours


def start_scheduled_backups():
    """Start a background timer that creates a backup every BACKUP_INTERVAL_SEC."""
    def _tick():
        global _backup_timer
        try:
            backup_db("scheduled")
        except Exception:
            log.exception("Scheduled backup failed")
        _backup_timer = threading.Timer(BACKUP_INTERVAL_SEC, _tick)
        _backup_timer.daemon = True
        _backup_timer.start()

    _tick()


def stop_scheduled_backups():
    """Cancel the background backup timer (if running)."""
    global _backup_timer
    if _backup_timer is not None:
        _backup_timer.cancel()
        _backup_timer = None


# ---------------------------------------------------------------------------
# PIN hashing
# ---------------------------------------------------------------------------

def _hash_pin(pin: str, salt: bytes | None = None) -> str:
    """Return 'salt_hex$hash_hex' using PBKDF2-SHA256."""
    if salt is None:
        salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations=100_000)
    return salt.hex() + "$" + h.hex()


def _verify_pin(pin: str, stored: str) -> bool:
    """Check a plain-text PIN against a stored hash string."""
    if "$" not in stored:
        # Legacy plain-text PIN -- direct comparison
        return pin == stored
    salt_hex, hash_hex = stored.split("$", 1)
    salt = bytes.fromhex(salt_hex)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations=100_000)
    return h.hex() == hash_hex


# ---------------------------------------------------------------------------
# Schema initialisation & migration
# ---------------------------------------------------------------------------

def _get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        cur = conn.execute("PRAGMA user_version")
        return cur.fetchone()[0]
    except sqlite3.Error:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int):
    conn.execute(f"PRAGMA user_version = {int(version)}")


def _migrate(conn: sqlite3.Connection):
    """Run incremental migrations."""
    ver = _get_schema_version(conn)

    if ver < 1:
        # Initial schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY,
                pin       TEXT UNIQUE NOT NULL,
                name      TEXT NOT NULL,
                is_admin  INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id       INTEGER PRIMARY KEY,
                barcode  TEXT UNIQUE NOT NULL,
                name     TEXT NOT NULL,
                count    INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                ts          DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id)    REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        """)
        _set_schema_version(conn, 1)
        ver = 1

    if ver < 2:
        # Migrate plain-text PINs to hashed PINs
        rows = conn.execute("SELECT id, pin FROM users").fetchall()
        for uid, pin_val in rows:
            if "$" not in pin_val:
                hashed = _hash_pin(pin_val)
                conn.execute(
                    "UPDATE users SET pin = ? WHERE id = ?", (hashed, uid)
                )
        _set_schema_version(conn, 2)
        ver = 2


def init_db():
    """Create tables / run migrations.  Backs up before migrating."""
    if DB_PATH.exists():
        backup_db("pre_migration")
    with _connect(transaction=True) as conn:
        _migrate(conn)


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def get_user_count() -> int:
    with _connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    return n


def create_user(pin: str, name: str, is_admin: bool = False):
    hashed = _hash_pin(pin)
    with _connect(transaction=True) as conn:
        try:
            conn.execute(
                "INSERT INTO users (pin, name, is_admin) VALUES (?, ?, ?)",
                (hashed, name, int(is_admin)),
            )
        except sqlite3.IntegrityError:
            raise ValueError("PIN schon vergeben")


def authenticate(pin: str):
    """Return (id, name, is_admin) or None."""
    with _connect() as conn:
        rows = conn.execute("SELECT id, name, is_admin, pin FROM users").fetchall()
    for uid, name, is_admin, stored_pin in rows:
        if _verify_pin(pin, stored_pin):
            return (uid, name, is_admin)
    return None


def update_pin(name: str, new_pin: str):
    hashed = _hash_pin(new_pin)
    with _connect(transaction=True) as conn:
        cur = conn.execute(
            "UPDATE users SET pin = ? WHERE name = ?", (hashed, name)
        )
        if cur.rowcount == 0:
            raise ValueError("Name nicht gefunden")


def delete_user(name: str, current_user_id: int):
    """Delete a user by name ensuring at least one admin remains."""
    with _connect(transaction=True) as conn:
        row = conn.execute(
            "SELECT id, is_admin FROM users WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            raise ValueError("Name nicht gefunden")
        user_id, is_admin = row
        if user_id == current_user_id:
            raise ValueError("Eigenen Account kann man nicht loeschen")
        if is_admin:
            (admin_count,) = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1"
            ).fetchone()
            if admin_count <= 1:
                raise ValueError("Mindestens ein Admin muss bestehen bleiben")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Product operations
# ---------------------------------------------------------------------------

def create_product(barcode: str, name: str, count: int = 0):
    with _connect(transaction=True) as conn:
        try:
            conn.execute(
                "INSERT INTO products (barcode, name, count) VALUES (?, ?, ?)",
                (barcode, name, count),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Barcode existiert bereits")


def get_inventory():
    """Return list of (id, barcode, name, count)."""
    with _connect() as conn:
        return conn.execute(
            "SELECT id, barcode, name, count FROM products ORDER BY name"
        ).fetchall()


def update_product_count(barcode: str, new_count: int):
    with _connect(transaction=True) as conn:
        cur = conn.execute(
            "UPDATE products SET count = ? WHERE barcode = ?",
            (new_count, barcode),
        )
        if cur.rowcount == 0:
            raise ValueError("Barcode nicht gefunden")


def delete_product(barcode: str):
    """Delete a product by barcode."""
    with _connect(transaction=True) as conn:
        cur = conn.execute(
            "DELETE FROM products WHERE barcode = ?", (barcode,)
        )
        if cur.rowcount == 0:
            raise ValueError("Barcode nicht gefunden")


# ---------------------------------------------------------------------------
# Transactions (bookings)
# ---------------------------------------------------------------------------

def record_transaction(user_id: int, barcode: str, quantity: int = 1):
    """Atomically record a booking and decrement stock."""
    with _connect(transaction=True) as conn:
        prod = conn.execute(
            "SELECT id, count FROM products WHERE barcode = ?", (barcode,)
        ).fetchone()
        if not prod:
            raise ValueError("Unbekannter Barcode")
        prod_id, current_count = prod
        if quantity <= 0:
            raise ValueError("Ungueltige Menge")
        if current_count < quantity:
            raise ValueError("Produkt nicht mehr vorraetig")
        for _ in range(quantity):
            conn.execute(
                "INSERT INTO transactions (user_id, product_id) VALUES (?, ?)",
                (user_id, prod_id),
            )
        conn.execute(
            "UPDATE products SET count = count - ? WHERE id = ?",
            (quantity, prod_id),
        )


def get_user_summary(user_id: int):
    """Return aggregated consumption for a user: list of (product_name, count)."""
    with _connect() as conn:
        return conn.execute(
            """
            SELECT p.name, COUNT(t.id) AS cnt
            FROM transactions t
            JOIN products p ON t.product_id = p.id
            WHERE t.user_id = ?
            GROUP BY p.id
            ORDER BY p.name
            """,
            (user_id,),
        ).fetchall()
