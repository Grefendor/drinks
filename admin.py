# admin.py
from db import get_connection
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

def export_pdf(path="report.pdf"):
    """
    Exportiert eine Tabelle mit:
      - Nutzer
      - Produkt
      - Verbrauch (Anzahl Buchungen)
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
          u.name       AS nutzer,
          p.name       AS produkt,
          COUNT(t.id)  AS verbrauch
        FROM transactions t
        JOIN users u      ON t.user_id    = u.id
        JOIN products p   ON t.product_id = p.id
        GROUP BY u.id, p.id
        ORDER BY u.name, p.name
    """)
    rows = cur.fetchall()
    conn.close()

    # Kopfzeile + Daten
    data = [("Nutzer", "Produkt", "Verbrauch")] + rows

    # PDF-Erzeugung
    doc = SimpleDocTemplate(path, pagesize=A4)
    # Spaltenbreiten optional anpassen
    table = Table(data, colWidths=[150, 200, 100])
    table.setStyle(TableStyle([
        ("GRID",       (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0),   colors.lightgrey),
        ("VALIGN",     (0,0), (-1,-1),  "MIDDLE"),
    ]))
    doc.build([table])
    print(f"PDF exportiert nach {path}")
