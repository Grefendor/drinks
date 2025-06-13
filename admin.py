from db import get_connection


def export_pdf(path="report.pdf"):
    """
    Exportiert eine Tabelle mit:
      - Nutzer
      - Produkt
      - Verbrauch (Anzahl Buchungen)
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
          u.name       AS nutzer,
          p.name       AS produkt,
          COUNT(t.id)  AS verbrauch,
          p.price      AS preis,
          COUNT(t.id)*p.price AS kosten
        FROM transactions t
        JOIN users u      ON t.user_id    = u.id
        JOIN products p   ON t.product_id = p.id
        GROUP BY u.id, p.id
        ORDER BY u.name, p.name
    """)
    rows = cur.fetchall()
    conn.close()

    data = [("Nutzer", "Produkt", "Verbrauch", "Preis", "Kosten")] + rows
    doc = SimpleDocTemplate(path, pagesize=A4)
    table = Table(data, colWidths=[150, 180, 70, 60, 70])
    table.setStyle(TableStyle([
        ("GRID",       (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0),   colors.lightgrey),
        ("VALIGN",     (0,0), (-1,-1),  "MIDDLE"),
    ]))
    doc.build([table])


def export_users_pdf(path="users.pdf"):
    """Exportiert alle Nutzer als Tabelle (ID, Name, PIN)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, pin, is_admin FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()

    data = [("ID", "Name", "PIN", "Admin")] + rows
    doc = SimpleDocTemplate(path, pagesize=A4)
    table = Table(data, colWidths=[50, 200, 100])
    table.setStyle(TableStyle([
        ("GRID",       (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0),   colors.lightgrey),
        ("VALIGN",     (0,0), (-1,-1),  "MIDDLE"),
    ]))
    doc.build([table])


def export_inventory_pdf(path="inventory.pdf"):
    """Exportiert alle Produkte als Tabelle (ID, Barcode, Name, Bestand, Preis)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, barcode, name, count, price FROM products ORDER BY name")
    rows = cur.fetchall()
    conn.close()

    data = [("ID", "Barcode", "Name", "Bestand", "Preis")] + rows
    doc = SimpleDocTemplate(path, pagesize=A4)
    table = Table(data, colWidths=[40, 100, 180, 60, 60])
    table.setStyle(TableStyle([
        ("GRID",       (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0),   colors.lightgrey),
        ("VALIGN",     (0,0), (-1,-1),  "MIDDLE"),
    ]))
    doc.build([table])
