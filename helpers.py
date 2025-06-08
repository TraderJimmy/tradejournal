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

def calculate_rr_stats(t):
    """
    Return a dict with rrr_planned, rrr_max, r_multiple for a given trade.
    All values are None if data is incomplete.
    """
    try:
        entry = float(t.get("entry_price"))
        sl = float(t.get("stop_loss"))
        tp = t.get("take_profit")
        tp = float(tp) if tp else None
        exit_price = t.get("exit_price")
        exit_price = float(exit_price) if exit_price else None
        exit_price_max = t.get("exit_price_max")
        exit_price_max = float(exit_price_max) if exit_price_max else None
        direction = t.get("direction")

        risk = abs(entry - sl) if sl is not None else None

        rrr_planned = round((tp - entry) / risk, 2) if risk and tp is not None and direction == "long" else \
                      round((entry - tp) / risk, 2) if risk and tp is not None and direction == "short" else None

        rrr_max = round((exit_price_max - entry) / risk, 2) if risk and exit_price_max is not None and direction == "long" else \
                  round((entry - exit_price_max) / risk, 2) if risk and exit_price_max is not None and direction == "short" else None

        r_multiple = round((exit_price - entry) / risk, 2) if risk and exit_price is not None and direction == "long" else \
                     round((entry - exit_price) / risk, 2) if risk and exit_price is not None and direction == "short" else None

        return {
            "rrr_planned": rrr_planned,
            "rrr_max": rrr_max,
            "r_multiple": r_multiple
        }
    except (TypeError, ValueError):
        return {
            "rrr_planned": None,
            "rrr_max": None,
            "r_multiple": None
        }


