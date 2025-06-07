import sqlite3

def get_db_connection():
    conn = sqlite3.connect("tradejournal.db")  # ← Använd rätt filnamn här!
    conn.row_factory = sqlite3.Row       # Gör det möjligt att använda t["kommentar"]
    return conn
