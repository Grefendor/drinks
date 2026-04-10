from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from db import _connect


def _build_pdf(path: str, header: list[str], rows: list[tuple], col_widths: list[int]):
    """Generic helper to build a single-table PDF."""
    data = [header] + [list(r) for r in rows]
    doc = SimpleDocTemplate(path, pagesize=A4)
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1,  0), colors.lightgrey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    doc.build([table])


def export_pdf(path: str = "report.pdf"):
    """Export a consumption report: user x product x count."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT u.name AS nutzer,
                   p.name AS produkt,
                   COUNT(t.id) AS verbrauch
            FROM transactions t
            JOIN users u    ON t.user_id    = u.id
            JOIN products p ON t.product_id = p.id
            GROUP BY u.id, p.id
            ORDER BY u.name, p.name
        """).fetchall()
    _build_pdf(path, ["Nutzer", "Produkt", "Verbrauch"], rows, [150, 200, 100])


def export_users_pdf(path: str = "users.pdf"):
    """Export all users as a table (ID, Name, Admin)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, is_admin FROM users ORDER BY id"
        ).fetchall()
    _build_pdf(path, ["ID", "Name", "Admin"], rows, [50, 250, 80])


def export_inventory_pdf(path: str = "inventory.pdf"):
    """Export all products as a table (ID, Barcode, Name, Bestand)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, barcode, name, count FROM products ORDER BY name"
        ).fetchall()
    _build_pdf(path, ["ID", "Barcode", "Name", "Bestand"], rows, [50, 100, 200, 80])
