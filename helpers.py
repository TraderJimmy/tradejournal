# helpers.py

from db import get_db_connection

def get_journal_name(journal_id):
    """Returnerar namnet på journalen utifrån dess ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    result = cursor.execute("SELECT name FROM journals WHERE id = ?", (journal_id,)).fetchone()
    conn.close()
    return result["name"] if result else "unknown"


def get_all_journals():
    """Returnerar alla journaler (t.ex. till dropdown-menyn)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    journals = cursor.execute("SELECT * FROM journals ORDER BY created DESC").fetchall()
    conn.close()
    return journals


def get_active_journal_name(journal_id, journals):
    """Returnerar namnet på den aktiva journalen baserat på ID och tillgängliga journaler."""
    for journal in journals:
        if journal["id"] == journal_id:
            return journal["name"]
    return "unknown"

def get_table_columns(table_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return columns

