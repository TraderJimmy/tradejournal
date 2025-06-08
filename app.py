from flask import Flask, render_template, request, redirect, url_for, jsonify, session, Response, flash, send_file
from collections import defaultdict
from urllib.parse import urlencode
from itertools import groupby
from datetime import datetime
from io import StringIO
from helpers import get_journal_name, get_all_journals, get_active_journal_name, get_table_columns, calculate_rr_stats
import sqlite3
import os
import uuid
import csv


app = Flask(__name__)

app.secret_key = "superhemlig_nyckel_123"  # byt ut till något unikt för dig

DB_PATH = "tradejournal.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Standardjournal (fallback om ingen är vald)
def get_active_journal():
    return session.get("journal_id", 1)


def calculate_rr(entry, stop, exit_price, direction):
    try:
        risk = abs(entry - stop)
        reward = (exit_price - entry) if direction == 'long' else (entry - exit_price)
        return round(reward / risk, 2) if risk > 0 else None
    except:
        return None

def calculate_pnl(entry, exit_price, qty, fees, direction):
    try:
        gross = (exit_price - entry) * qty if direction == 'long' else (entry - exit_price) * qty
        net = gross - (fees or 0)
        return round(gross, 2), round(net, 2)
    except:
        return None, None


def get_all_trades(filters=None, journal_id=1):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM trades"
    conditions = ["journal_id = ?"]
    params = [journal_id]

    if filters:
        # Exakta matchningar (dropdowns, radioknappar, datum)
        exact_fields = ["instrument", "setup", "direction", "datum", "outcome", "rr"]
        for field in exact_fields:
            values = filters.get(field, [])
            if not isinstance(values, list):
                values = [values]
            for val in values:
                if val:
                    conditions.append(f"{field} = ?")
                    params.append(val)

        # 📅 Datumintervall
        start_date = filters.get("start_date", [None])[0]
        end_date = filters.get("end_date", [None])[0]

        if start_date:
            conditions.append("datum >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("datum <= ?")
            params.append(end_date)


        # Fält som tillåter flera värden (checkboxar)
        checkbox_fields = ["regler", "entry_logic", "exit_logic", "premarket", "obalans", "återtesten", "reversal_rules", "continuation_rules"]
        for field in checkbox_fields:
            values = filters.get(field, [])
            if not isinstance(values, list):
                values = [values]
            for val in values:
                if val:
                    conditions.append(f"{field} LIKE ?")
                    params.append(f"%{val}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY datum DESC"

    cursor.execute(query, params)
    trades = cursor.fetchall()

    # Packa upp tags per trade
    trade_data = []
    for trade in trades:
        cursor.execute("""
            SELECT tags.name AS tag_name, categories.name AS category_name, tags.id AS tag_id
            FROM trade_tags
            JOIN tags ON trade_tags.tag_id = tags.id
            JOIN categories ON tags.category_id = categories.id
            WHERE trade_tags.trade_id = ?
        """, (trade["id"],))
        tag_rows = cursor.fetchall()

        tags_by_category = defaultdict(list)
        tag_id_list = []

        for row in tag_rows:
            tags_by_category[row['category_name']].append(row['tag_name'])
            tag_id_list.append(row['tag_id'])

        trade_data.append({
            'id': trade['id'],
            'datum': trade['datum'],
            'instrument': trade['instrument'],
            'setup': trade['setup'],
            'regler': trade['regler'],
            'direction': trade['direction'],
            'outcome': trade['outcome'],
            'rr_logisk': trade['rr_logisk'],
            'rr_max': trade['rr_max'],
            'entry_logic': trade['entry_logic'],
            'exit_logic': trade['exit_logic'],
            'premarket': trade['premarket'],
            'obalans': trade['obalans'],
            'återtesten': trade['återtesten'],
            'kommentar': trade['kommentar'],
            'image1': trade['image1'],
            'image2': trade['image2'],
            'tags_by_category': tags_by_category,
            'tag_ids': tag_id_list,
            'reversal_rules': trade['reversal_rules'],
            'continuation_rules': trade['continuation_rules'],
            'entry_price': trade['entry_price'],
            'exit_price': trade['exit_price'],
            'exit_price_max': trade['exit_price_max'],
            'stop_loss': trade['stop_loss'],
            'take_profit': trade['take_profit'],
            'quantity': trade['quantity'],
            'exit_date': trade['exit_date'],
            'fees': trade['fees'],
            'net_pl': trade['net_pl'],
            'gross_pl': trade['gross_pl']
        })

    # Alla tillgängliga taggar
    cursor.execute("""
        SELECT tags.id AS tag_id, tags.name AS tag_name, categories.name AS category_name
        FROM tags
        JOIN categories ON tags.category_id = categories.id
        ORDER BY categories.name, tags.name
    """)
    all_tags = cursor.fetchall()

    conn.close()
    return trade_data, all_tags



@app.route('/')
def index():
    filters = request.args.to_dict(flat=False)  # Viktigt: flat=False för att stödja checkboxar

    # 🔄 Hämta aktiv journal
    journal_id = get_active_journal()

    # Hämta filtrerade trades
    trades, all_tags = get_all_trades(filters, journal_id=journal_id)

    # 🔄 Hämta alla journaler (till dropdown)
    conn = get_db_connection()
    cursor = conn.cursor()
    journals = cursor.execute("SELECT * FROM journals ORDER BY created DESC").fetchall()

    # 🔍 Hämta namn på aktiv journal
    active_journal_name = None
    for j in journals:
        if j["id"] == journal_id:
            active_journal_name = j["name"]
            break

    conn.close()

    # För badges och clear-länkar
    active_filters = {}
    clear_links = {}

    for key, values in filters.items():
        non_empty = [v for v in values if v]  # hoppa över tomma värden
        if non_empty:
            active_filters[key] = non_empty
            for v in non_empty:
                updated_args = filters.copy()
                updated_args[key] = [val for val in non_empty if val != v]
                clear_links[f"{key}:{v}"] = url_for("index") + "?" + urlencode(updated_args, doseq=True)

    return render_template(
        "index.html",
        trades=trades,
        all_tags=all_tags,
        active_filters=active_filters,
        clear_links=clear_links,
        journals=journals,
        active_journal_id=journal_id,
        active_journal_name=active_journal_name
    )



@app.route("/upload", methods=["POST"])
def upload():
    import uuid
    kommentar = request.form.get("kommentar")
    datum = request.form.get("datum")
    instrument = request.form.get("instrument")
    setup = request.form.get("setup")
    direction = request.form.get("direction")
    outcome = request.form.get("outcome")
    rr_logisk = request.form.get("rr_logisk")
    rr_max = request.form.get("rr_max")

    try:
        rr_logisk = float(rr_logisk) if rr_logisk else rr_logisk
    except ValueError:
        rr_logisk = None

    try:
        rr_max = float(rr_max) if rr_max else None
    except ValueError:
        rr_max = None
    if not rr_max:
        rr_max = calculate_rr(entry_price, stop_loss, exit_price_max, direction)


    # Nya numeriska fält
    try:
        entry_price = float(request.form.get("entry_price") or 0)
        exit_price = float(request.form.get("exit_price") or 0)
        stop_loss = float(request.form.get("stop_loss") or 0)
        take_profit = float(request.form.get("take_profit") or 0)
        quantity = float(request.form.get("quantity") or 0)
        fees = float(request.form.get("fees") or 0)
    except ValueError:
        entry_price = exit_price = stop_loss = take_profit = quantity = fees = 0

    try:
        exit_price_max = float(request.form.get("exit_price_max") or 0)
    except ValueError:
        exit_price_max = 0


    exit_date = request.form.get("exit_date")

    # RR-logisk – beräkna endast om fältet är tomt
    if not rr_logisk:
        rr_logisk = calculate_rr(entry_price, stop_loss, exit_price, direction)

    # Beräkna PnL
    gross_pl, net_pl = calculate_pnl(entry_price, exit_price, quantity, fees, direction)


    regler = ", ".join(request.form.getlist("regler[]"))
    entry_logic = ", ".join(request.form.getlist("entry_logic"))
    exit_logic = ", ".join(request.form.getlist("exit_logic"))
    premarket = ", ".join(request.form.getlist("premarket"))
    obalans = ", ".join(request.form.getlist("obalans"))
    återtesten = ", ".join(request.form.getlist("återtesten"))
    reversal_rules = ", ".join(request.form.getlist("reversal_rules"))
    continuation_rules = ", ".join(request.form.getlist("continuation_rules"))

    image1 = request.files.get("bild1")
    image2 = request.files.get("bild2")
    image1_web_path, image2_web_path = None, None

    if image1 and image2:
        os.makedirs("static/images", exist_ok=True)
        filename1 = str(uuid.uuid4()) + "_" + image1.filename
        filename2 = str(uuid.uuid4()) + "_" + image2.filename
        image1_path = os.path.join("static", "images", filename1)
        image2_path = os.path.join("static", "images", filename2)
        image1.save(image1_path)
        image2.save(image2_path)
        image1_web_path = f"/static/images/{filename1}"
        image2_web_path = f"/static/images/{filename2}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades 
        (kommentar, datum, instrument, setup, regler, direction, outcome, rr_logisk, rr_max,
         entry_logic, exit_logic, premarket, obalans, återtesten, image1, image2,
         reversal_rules, continuation_rules,
         entry_price, exit_price, stop_loss, take_profit, quantity, exit_date, fees, gross_pl, net_pl, exit_price_max)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        kommentar, datum, instrument, setup, regler, direction, outcome, rr_logisk, rr_max,
        entry_logic, exit_logic, premarket, obalans, återtesten,
        image1_web_path, image2_web_path, reversal_rules, continuation_rules,
        entry_price, exit_price, stop_loss, take_profit, quantity, exit_date, fees, gross_pl, net_pl, exit_price_max
    ))

    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/update", methods=["POST"])
def update():
    import uuid
    trade_id = request.form.get("trade_id")
    kommentar = request.form.get("kommentar")
    datum = request.form.get("datum")
    instrument = request.form.get("instrument")
    setup = request.form.get("setup")
    direction = request.form.get("direction")
    outcome = request.form.get("outcome")
    rr_logisk = request.form.get("rr_logisk")
    rr_max = request.form.get("rr_max")

    # Initiera fält till 0
    entry_price = exit_price = stop_loss = take_profit = quantity = fees = exit_price_max = 0

    # ✅ Konvertera RR-fält till float
    try:
        rr_logisk = float(rr_logisk) if rr_logisk else None
    except ValueError:
        rr_logisk = None

    try:
        rr_max = float(rr_max) if rr_max else None
    except ValueError:
        rr_max = None

    # Nya numeriska fält
    try:
        entry_price = float(request.form.get("entry_price") or 0)
        exit_price = float(request.form.get("exit_price") or 0)
        stop_loss = float(request.form.get("stop_loss") or 0)
        take_profit = float(request.form.get("take_profit") or 0)
        quantity = float(request.form.get("quantity") or 0)
        fees = float(request.form.get("fees") or 0)
        exit_price_max = float(request.form.get("exit_price_max") or 0)
    except ValueError:
        pass # Vi låter dem stanna på 0 om det blir fel

    exit_date = request.form.get("exit_date")

    # RR-Max – räkna ut om fältet är tomt
    if not rr_max and entry_price > 0 and stop_loss > 0 and exit_price_max > 0:
        rr_max = calculate_rr(entry_price, stop_loss, exit_price_max, direction)

    # RR-logisk – räkna ut om fältet är tomt
    if not rr_logisk:
        rr_logisk = calculate_rr(entry_price, stop_loss, exit_price, direction)

    # P&L
    gross_pl, net_pl = calculate_pnl(entry_price, exit_price, quantity, fees, direction)

    regler = ", ".join(request.form.getlist("regler[]"))
    entry_logic = ", ".join(request.form.getlist("entry_logic"))
    exit_logic = ", ".join(request.form.getlist("exit_logic"))
    premarket = ", ".join(request.form.getlist("premarket"))
    obalans = ", ".join(request.form.getlist("obalans"))
    återtesten = ", ".join(request.form.getlist("återtesten"))
    reversal_rules = ", ".join(request.form.getlist("reversal_rules"))
    continuation_rules = ", ".join(request.form.getlist("continuation_rules"))

    image1 = request.files.get("bild1")
    image2 = request.files.get("bild2")

    update_fields = [
        "kommentar = ?", "datum = ?", "instrument = ?", "setup = ?", "regler = ?",
        "direction = ?", "outcome = ?", "rr_logisk = ?", "rr_max = ?", "entry_logic = ?", "exit_logic = ?",
        "premarket = ?", "obalans = ?", "återtesten = ?", "reversal_rules = ?", "continuation_rules = ?", 
        "entry_price = ?", "exit_price = ?", "stop_loss = ?", "take_profit = ?",
        "quantity = ?", "exit_date = ?", "fees = ?", "gross_pl = ?", "net_pl = ?", "exit_price_max = ?"
    ]

    values = [
        kommentar, datum, instrument, setup, regler,
        direction, outcome, rr_logisk, rr_max, entry_logic, exit_logic,
        premarket, obalans, återtesten, reversal_rules, continuation_rules,
        entry_price, exit_price, stop_loss, take_profit,
        quantity, exit_date, fees, gross_pl, net_pl, exit_price_max
    ]

    if image1:
        filename1 = str(uuid.uuid4()) + "_" + image1.filename
        image1_path = os.path.join("static", "images", filename1)
        image1.save(image1_path)
        update_fields.append("image1 = ?")
        values.append(f"/static/images/{filename1}")

    if image2:
        filename2 = str(uuid.uuid4()) + "_" + image2.filename
        image2_path = os.path.join("static", "images", filename2)
        image2.save(image2_path)
        update_fields.append("image2 = ?")
        values.append(f"/static/images/{filename2}")

    values.append(trade_id)
    sql = f"UPDATE trades SET {', '.join(update_fields)} WHERE id = ?"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, values)
    conn.commit()
    conn.close()

    return redirect(url_for("index") + f"#trade-{trade_id}")




@app.route('/add_tag', methods=['POST'])
def add_tag():
    trade_id = request.form['trade_id']
    tag_id = request.form['tag_id']
    if not tag_id:
        flash("Ingen tagg vald", "error")
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO trade_tags (trade_id, tag_id) VALUES (?, ?)", (trade_id, tag_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/remove_tag', methods=['POST'])
def remove_tag():
    trade_id = request.form['trade_id']
    tag_name = request.form['tag_name']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Slå upp tag_id via tag_name
    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
    tag = cursor.fetchone()
    if tag:
        tag_id = tag['id']
        cursor.execute("DELETE FROM trade_tags WHERE trade_id = ? AND tag_id = ?", (trade_id, tag_id))
        conn.commit()

    conn.close()
    return redirect('/')

@app.route("/get_trade/<int:trade_id>")
def get_trade(trade_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    trade = cursor.fetchone()
    conn.close()

    if trade:
        return jsonify({
            "id": trade["id"],
            "datum": trade["datum"],
            "instrument": trade["instrument"],
            "setup": trade["setup"],
            "regler": trade["regler"],
            "direction": trade["direction"],
            "outcome": trade["outcome"],
            "rr_logisk": trade["rr_logisk"],
            "rr_max": trade["rr_max"],  
            "entry_logic": trade["entry_logic"],
            "exit_logic": trade["exit_logic"],
            "premarket": trade["premarket"],
            "obalans": trade["obalans"],
            "återtesten": trade["återtesten"],
            "kommentar": trade["kommentar"],
            "reversal_rules": trade["reversal_rules"],
            "continuation_rules": trade["continuation_rules"],
            "entry_price": trade["entry_price"],
            "exit_price": trade["exit_price"],
            "stop_loss": trade["stop_loss"],
            "take_profit": trade["take_profit"],
            "quantity": trade["quantity"],
            "exit_date": trade["exit_date"],
            "fees": trade["fees"],
            "gross_pl": trade["gross_pl"],
            "net_pl": trade["net_pl"],
            "exit_price_max": trade["exit_price_max"]


        })
    return jsonify({}), 404

@app.route("/delete_trade/<int:trade_id>", methods=["POST"])
def delete_trade(trade_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ta även bort tagg-kopplingar först om de finns
    cursor.execute("DELETE FROM trade_tags WHERE trade_id = ?", (trade_id,))
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/filtered_trades")
def filtered_trades():
    filters = request.args.to_dict(flat=True)
    trades, all_tags = get_all_trades(filters)

    # Samma badge-logik
    active_filters = {}
    clear_links = {}

    for key, val in filters.items():
        if val:
            active_filters[key] = val
            new_args = filters.copy()
            new_args.pop(key)
            clear_links[key] = url_for('index') + '?' + urlencode(new_args)

    return render_template(
        "partials/trade_wrapper.html",
        trades=trades,
        all_tags=all_tags,
        active_filters=active_filters,
        clear_links=clear_links
    )

@app.route("/trades/table")
def trades_table():
    journal_id = get_active_journal()
    filters = request.args.to_dict(flat=False)
    trades, _ = get_all_trades(filters=filters, journal_id=journal_id)

    for t in trades:
        entry = t.get("entry_price")
        exit_ = t.get("exit_price")
        exit_max = t.get("exit_price_max")
        tp = t.get("take_profit")
        sl = t.get("stop_loss")
        direction = t.get("direction")

        try:
            entry = float(entry)
            exit_ = float(exit_) if exit_ is not None else None
            exit_max = float(exit_max) if exit_max is not None else None
            tp = float(tp) if tp is not None else None
            sl = float(sl) if sl is not None else None
        except (ValueError, TypeError):
            entry = exit_ = exit_max = tp = sl = None

        risk = abs(entry - sl) if entry is not None and sl is not None else None

        # 🔹 RRR Planned (entry -> TP)
        if risk and tp is not None:
            if direction == "long":
                t["rrr_planned"] = round((tp - entry) / risk, 2)
            elif direction == "short":
                t["rrr_planned"] = round((entry - tp) / risk, 2)
            else:
                t["rrr_planned"] = None
        else:
            t["rrr_planned"] = None

        # 🔸 RRR Max (entry -> exit_price_max)
        if risk and exit_max is not None:
            if direction == "long":
                t["rrr_max"] = round((exit_max - entry) / risk, 2)
            elif direction == "short":
                t["rrr_max"] = round((entry - exit_max) / risk, 2)
            else:
                t["rrr_max"] = None
        else:
            t["rrr_max"] = None

        # 🟥 R-Multiple (entry -> exit)
        if risk and exit_ is not None:
            if direction == "long":
                t["r_multiple"] = round((exit_ - entry) / risk, 2)
            elif direction == "short":
                t["r_multiple"] = round((entry - exit_) / risk, 2)
            else:
                t["r_multiple"] = None
        else:
            t["r_multiple"] = None


    # 🧹 Skapa länkar för att rensa enskilda filter
    clear_links = {}
    base_args = filters.copy()

    for key, values in filters.items():
        for val in values:
            new_args = base_args.copy()
            new_vals = new_args.get(key, []).copy()
            if val in new_vals:
                new_vals.remove(val)
            if new_vals:
                new_args[key] = new_vals
            else:
                new_args.pop(key, None)

            clear_links[f"{key}:{val}"] = f"/trades/table?{urlencode(new_args, doseq=True)}"


    return render_template(
        "trades_table.html",
        trades=trades,
        active_filters=filters,
        clear_links=clear_links
    )

@app.route("/switch_journal", methods=["POST"])
def switch_journal():
    journal_id = request.form.get("journal_id")
    if journal_id:
        session["journal_id"] = int(journal_id)
    return redirect(url_for("index"))

@app.route("/add_journal", methods=["POST"])
def add_journal():
    new_name = request.form.get("new_journal")
    if new_name:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO journals (name) VALUES (?)", (new_name,))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        session["journal_id"] = new_id  # Byt direkt till nya journalen
    return redirect(url_for("index"))


@app.route("/stats")
def stats():

    # 📥 1. Läs in filter från URL-parametrar
    filters = request.args.to_dict(flat=False)
    rr_max_filter = filters.get("rr_max_filter", [None])[0]

    # 🟢 Hämta aktiv journal
    journal_id = get_active_journal()

    # 🔄 Hämta alla journaler (till dropdown)
    conn = get_db_connection()
    cursor = conn.cursor()
    journals = cursor.execute("SELECT * FROM journals ORDER BY created DESC").fetchall()

    # 🔍 Hämta namn på aktiv journal
    active_journal_name = None
    for j in journals:
        if j["id"] == journal_id:
            active_journal_name = j["name"]
            break
    conn.close()

    # 🧮 Hämta filtrerade trades för aktuell journal
    trades, _ = get_all_trades(filters, journal_id=journal_id)

    # 🧮 2. Hämta filtrerade trades
    trades, _ = get_all_trades(filters)

    # 📊 3. Initiera variabler för Total-statistik
    total_trades = 0
    rr_list = []             # Ursprungliga rr-fältet
    rr_logisk_list = []      # För teknisk/logisk exit
    rr_max_list = []         # För fast exit
    rr_max_list_total = []

    wins = 0
    losses = 0
    wins_logisk = 0
    losses_logisk = 0
    wins_max = 0
    losses_max = 0
    longs_won = 0
    shorts_won = 0
    outcome_sequence = []
    outcome_seq_logisk = []
    outcome_seq_max = []

    longs_won_logisk = 0
    shorts_won_logisk = 0
    count_logisk_trades = 0
    count_max_trades = 0
    longs_won_max = 0
    shorts_won_max = 0

    wins_max_total = 0
    losses_max_total = 0
    longs_won_max_total = 0
    shorts_won_max_total = 0


    rr_logisk_list_total = []
    wins_logisk_total = 0
    losses_logisk_total = 0
    count_logisk_total = 0
    longs_won_logisk_total = 0
    shorts_won_logisk_total = 0
    outcome_seq_logisk_total = []
    outcome_seq_max_total = []


    # 🔁 4. Loopa över alla trades
    for t in trades:
        rr_l = t.get("rr_logisk")
        rr_m = t.get("rr_max")
        outcome = t.get("outcome")

        # ⛔️ Hoppa över tomma trades
        if (not rr_l or str(rr_l).strip() == "") and (not rr_m or str(rr_m).strip() == "") and (not outcome or outcome == "none"):
            continue

        total_trades += 1  # ✅ Giltig trade räknas

        direction = t.get("direction")


        if outcome == "tp":
            wins += 1
            outcome_sequence.append("W")
            if direction == "long":
                longs_won += 1
            elif direction == "short":
                shorts_won += 1
        elif outcome == "sl":
            losses += 1
            outcome_sequence.append("L")
        else:
            outcome_sequence.append("N")

        # 🔢 4a. RR (vanliga fältet, inte logisk/max)
        rr_val = t.get("rr")
        if isinstance(rr_val, str):
            rr_val = rr_val.strip()
        try:
            rr_list.append(float(rr_val))
        except (TypeError, ValueError):
            pass

        # 🔢 4b. RR Logisk Exit (för totalsammanställning – separata variabler)
        rr_l = t.get("rr_logisk")
        rr_m = t.get("rr_max")
        direction = t.get("direction")

        if isinstance(rr_l, str): rr_l = rr_l.strip()
        if isinstance(rr_m, str): rr_m = rr_m.strip()

        try:
            val_l = float(rr_l)
            val_m = float(rr_m)
            count_logisk_total += 1  # ✅ detta är det nya namnet

            if val_l <= val_m:
                # ✅ TP
                rr_logisk_list_total.append(val_l)
                wins_logisk_total += 1
                outcome_seq_logisk_total.append("W")
                if direction == "long":
                    longs_won_logisk_total += 1
                elif direction == "short":
                    shorts_won_logisk_total += 1
            else:
                # ❌ SL
                rr_logisk_list_total.append(-1)
                losses_logisk_total += 1
                outcome_seq_logisk_total.append("L")

        except (TypeError, ValueError):
            rr_logisk_list_total.append(0)
            outcome_seq_logisk_total.append("N")





        # 🔢 4c. RR Max (Fast Exit med korrekt filterhantering)
        rr_m = t.get("rr_max")
        direction = t.get("direction")

        if isinstance(rr_m, str):
            rr_m = rr_m.strip()

        try:
            val = float(rr_m)
            count_max_trades += 1

            if rr_max_filter:
                target = float(rr_max_filter)
                if val >= target:
                    rr_max_list_total.append(target)  # 🔁 ⬅️ viktig ändring: använd target!
                    wins_max_total += 1
                    outcome_seq_max_total.append("W")
                    if direction == "long":
                        longs_won_max_total += 1
                    elif direction == "short":
                        shorts_won_max_total += 1
                else:
                    rr_max_list_total.append(-1)
                    losses_max_total += 1
                    outcome_seq_max_total.append("L")
            else:
                rr_max_list.append(val)
                if val > 0:
                    wins_max += 1
                    outcome_seq_max_total.append("W")
                    if direction == "long":
                        longs_won_max += 1
                    elif direction == "short":
                        shorts_won_max += 1
                elif val < 0:
                    losses_max += 1
                    outcome_seq_max_total.append("L")
                else:
                    outcome_seq_max_total.append("N")

        except (TypeError, ValueError):
            outcome_seq_max_total.append("N")




    # 📈 5. Summerad statistik för alla typer
    total_rr         = round(sum(rr_list), 2) if rr_list else 0
    avg_rr           = round(total_rr / total_trades, 2) if total_trades else 0
    winrate          = round((wins / total_trades) * 100, 1) if total_trades else 0

    # 📈 5. Summerad statistik för logisk
    total_rr_logisk = round(sum(rr_logisk_list_total), 2)
    avg_rr_logisk = round(total_rr_logisk / count_logisk_total, 2) if count_logisk_total else 0
    winrate_logisk = round((wins_logisk_total / count_logisk_total) * 100, 1) if count_logisk_total else 0

    max_wins_row_logisk = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_logisk_total) if k == "W"), default=0)
    max_losses_row_logisk = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_logisk_total) if k == "L"), default=0)


    total_rr_max     = round(sum(rr_max_list_total), 2) 
    avg_rr_max = round(total_rr_max / len(rr_max_list_total), 2) if rr_max_list_total else 0
    winrate_max = round((wins_max_total / len(rr_max_list_total)) * 100, 1) if rr_max_list_total else 0

    print("Fast Exit DEBUG")
    print("rr_max_list:", rr_max_list)
    print("TP:", wins_max)
    print("SL:", losses_max)
    print("Trades:", count_max_trades)
    print("Longs won:", longs_won_max)
    print("Shorts won:", shorts_won_max)


    # 📊 6. Sekvensanalys (för max W/L i rad)
    max_wins_row = max((sum(1 for _ in g) for k, g in groupby(outcome_sequence) if k == "W"), default=0)
    max_losses_row = max((sum(1 for _ in g) for k, g in groupby(outcome_sequence) if k == "L"), default=0)

    # 🔁 Sekvensanalys för logisk och fast exit
    max_wins_row_logisk = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_logisk_total) if k == "W"), default=0)
    max_losses_row_logisk = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_logisk_total) if k == "L"), default=0)

    max_wins_row_max = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_max_total) if k == "W"), default=0)
    max_losses_row_max = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_max_total) if k == "L"), default=0)

    # 🧹 7. Skapa badge-struktur för aktiva filter
    active_filters = {}
    clear_links = {}
    for key, values in filters.items():
        non_empty = [v for v in values if v]
        if non_empty:
            active_filters[key] = non_empty
            for v in non_empty:
                updated_args = filters.copy()
                updated_args[key] = [val for val in non_empty if val != v]
                clear_links[f"{key}:{v}"] = url_for("stats") + "?" + urlencode(updated_args, doseq=True)

    # 📊 Monthly stats
    monthly_stats = {}
    trades_by_month = defaultdict(list)
    for t in trades:
        try:
            month = datetime.strptime(t["datum"], "%Y-%m-%d").strftime("%Y-%m")
            trades_by_month[month].append(t)
        except Exception:
            continue
    for month, trades_in_month in sorted(trades_by_month.items(), reverse=True):
        rr_logisk_list = []
        rr_max_list = []

        wins_logisk = losses_logisk = wins_max = losses_max = 0
        longs_won_logisk = shorts_won_logisk = 0
        longs_won_max = shorts_won_max = 0

        outcome_seq_logisk = []
        outcome_seq_max = []

        for t in trades_in_month:
            # === Logisk Exit ===
            direction = t.get("direction")
            outcome = t.get("outcome")
            rr_l = t.get("rr_logisk")

            if isinstance(rr_l, str): rr_l = rr_l.strip()

            try:
                val = float(rr_l)

                if outcome == "tp":
                    rr_logisk_list.append(val)
                    wins_logisk += 1
                    outcome_seq_logisk.append("W")
                    if direction == "long":
                        longs_won_logisk += 1
                    elif direction == "short":
                        shorts_won_logisk += 1
                elif outcome == "sl":
                    rr_logisk_list.append(-1)
                    losses_logisk += 1
                    outcome_seq_logisk.append("L")
                else:
                    rr_logisk_list.append(0)
                    outcome_seq_logisk.append("N")

            except:
                rr_logisk_list.append(0)
                outcome_seq_logisk.append("N")

            # === Fast Exit ===
            rr_m = t.get("rr_max")
            if rr_m is None or rr_m == "":
                continue
            if isinstance(rr_m, str): rr_m = rr_m.strip()
            try:
                val = float(rr_m)
                if rr_max_filter:
                    target = float(rr_max_filter)
                    if val >= target:
                        rr_max_list.append(target)
                        wins_max += 1
                        outcome_seq_max.append("W")
                        if direction == "long":
                            longs_won_max += 1
                        elif direction == "short":
                            shorts_won_max += 1
                    else:
                        rr_max_list.append(-1)
                        losses_max += 1
                        outcome_seq_max.append("L")
                else:
                    rr_max_list.append(val)
                    if val > 0:
                        wins_max += 1
                        outcome_seq_max.append("W")
                        if direction == "long":
                            longs_won_max += 1
                        elif direction == "short":
                            shorts_won_max += 1
                    elif val < 0:
                        losses_max += 1
                        outcome_seq_max.append("L")
                    else:
                        outcome_seq_max.append("N")
            except:
                continue

        # ✅ Filtrera bort ogiltiga logiska rr
        valid_rr_logisk = [v for v in rr_logisk_list if v != 0]
        valid_wins_logisk = sum(1 for v in valid_rr_logisk if v > 0)
        valid_losses_logisk = sum(1 for v in valid_rr_logisk if v < 0)
        winrate_l = round((valid_wins_logisk / len(valid_rr_logisk)) * 100, 1) if valid_rr_logisk else 0
        total_rr_l = round(sum(valid_rr_logisk), 2) if valid_rr_logisk else 0
        avg_rr_l = round(total_rr_l / len(valid_rr_logisk), 2) if valid_rr_logisk else 0

        # 🔁 Fast Exit kalkyl
        def calc_stats(rr_list, wins, losses):
            total = round(sum(rr_list), 2) if rr_list else 0
            avg = round(total / len(rr_list), 2) if rr_list else 0
            winrate = round((wins / len(rr_list)) * 100, 1) if rr_list else 0
            return total, avg, wins, losses, winrate

        total_rr_m, avg_rr_m, w_m, l_m, winrate_m = calc_stats(rr_max_list, wins_max, losses_max)

        # 🔁 Sekvenser
        max_wins_row_l = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_logisk) if k == "W"), default=0)
        max_losses_row_l = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_logisk) if k == "L"), default=0)
        max_wins_row_m = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_max) if k == "W"), default=0)
        max_losses_row_m = max((sum(1 for _ in g) for k, g in groupby(outcome_seq_max) if k == "L"), default=0)

        monthly_stats[month] = {
            "logisk": {
                "total": total_rr_l,
                "avg": avg_rr_l,
                "wins": valid_wins_logisk,
                "losses": valid_losses_logisk,
                "winrate": winrate_l,
                "longs_won": longs_won_logisk,
                "shorts_won": shorts_won_logisk,
                "max_wins_row": max_wins_row_l,
                "max_losses_row": max_losses_row_l
            },
            "max": {
                "total": total_rr_m,
                "avg": avg_rr_m,
                "wins": w_m,
                "losses": l_m,
                "winrate": winrate_m,
                "longs_won": longs_won_max,
                "shorts_won": shorts_won_max,
                "max_wins_row": max_wins_row_m,
                "max_losses_row": max_losses_row_m
            },
            "extra": {
                "total_trades": len([
                    t for t in trades_in_month
                    if not (
                        (not t.get("rr_logisk") or str(t.get("rr_logisk")).strip() == "") and
                        (not t.get("rr_max") or str(t.get("rr_max")).strip() == "") and
                        (not t.get("outcome") or t.get("outcome") == "none")
                    )
                ])
            }
        }


    # 📤 8. Skicka allt till templaten
    return render_template(
        "stats.html",
        total_trades=total_trades,
        total_rr=total_rr,
        avg_rr=avg_rr,
        wins=wins,
        losses=losses,
        winrate=winrate,

        # Logisk exit
        total_rr_logisk=total_rr_logisk,
        avg_rr_logisk=avg_rr_logisk,
        winrate_logisk=winrate_logisk,
        wins_logisk=wins_logisk_total,
        losses_logisk=losses_logisk_total,
        total_trades_logisk=count_logisk_total,
        longs_won_logisk=longs_won_logisk_total,
        shorts_won_logisk=shorts_won_logisk_total,
        max_wins_row_logisk=max_wins_row_logisk,
        max_losses_row_logisk=max_losses_row_logisk,


        # Fast exit
        total_rr_max=total_rr_max,
        avg_rr_max=avg_rr_max,
        winrate_max=winrate_max,
        wins_max=wins_max_total,
        losses_max=losses_max_total,
        total_trades_max=count_max_trades,
        longs_won_max=longs_won_max_total,
        shorts_won_max=shorts_won_max_total,
        max_wins_row_max=max_wins_row_max,
        max_losses_row_max=max_losses_row_max,


        # Övrigt
        longs_won=longs_won,
        shorts_won=shorts_won,
        max_wins_row=max_wins_row,
        max_losses_row=max_losses_row,
        rr_max_filter=rr_max_filter,
        active_filters=active_filters,
        clear_links=clear_links,
        monthly_stats=monthly_stats,
        journals=journals,
        active_journal_id=journal_id,
        active_journal_name=active_journal_name



    )

@app.route("/stats/details")
def stats_details():

    filters = request.args.to_dict(flat=False)
    rr_max_filter = filters.get("rr_max_filter", [None])[0]
    journal_id = get_active_journal()

    # Hämta alla journaler och namnet på aktiv
    journals = get_all_journals()
    active_journal_name = get_active_journal_name(journal_id, journals)

    # Hämta trades för journalen
    trades, _ = get_all_trades(filters, journal_id=journal_id)

    # Initiera statistikvariabler
    total_trades_logisk = total_trades_max = 0
    wins_logisk = losses_logisk = 0
    wins_max = losses_max = 0
    rr_logisk_list = []
    rr_max_list = []

    for t in trades:
        rr_data = calculate_rr_stats(t)
        rrr_planned = rr_data["rrr_planned"]
        rrr_max = rr_data["rrr_max"]

        if rrr_planned is not None and rrr_max is not None:
            total_trades_logisk += 1
            if rrr_planned <= rrr_max:
                wins_logisk += 1
                rr_logisk_list.append(rrr_planned)
            else:
                losses_logisk += 1
                rr_logisk_list.append(-1)

        if rrr_max is not None:
            total_trades_max += 1
            if rr_max_filter:
                try:
                    target = float(rr_max_filter)
                    if rrr_max >= target:
                        wins_max += 1
                        rr_max_list.append(target)
                    else:
                        losses_max += 1
                        rr_max_list.append(-1)
                except:
                    continue
            else:
                if rrr_max > 0:
                    wins_max += 1
                elif rrr_max < 0:
                    losses_max += 1
                rr_max_list.append(rrr_max)

    def calc_stats(rrs, wins, losses):
        total = round(sum(rrs), 2) if rrs else 0
        avg = round(total / len(rrs), 2) if rrs else 0
        winrate = round((wins / len(rrs)) * 100, 1) if rrs else 0
        return total, avg, winrate, wins, losses, len(rrs)

    # Summerad statistik
    total_rr_logisk, avg_rr_logisk, winrate_logisk, wins_logisk, losses_logisk, count_logisk_total = calc_stats(rr_logisk_list, wins_logisk, losses_logisk)
    total_rr_max, avg_rr_max, winrate_max, wins_max, losses_max, count_max_total = calc_stats(rr_max_list, wins_max, losses_max)

    # Grupp per månad
    trades_by_month = defaultdict(list)
    for t in trades:
        try:
            month = datetime.strptime(t["datum"], "%Y-%m-%d").strftime("%Y-%m")
            trades_by_month[month].append(t)
        except:
            continue

    monthly_stats = {}
    for month, month_trades in sorted(trades_by_month.items(), reverse=True):
        m_rr_logisk = []
        m_rr_max = []
        w_l = l_l = w_m = l_m = 0

        for t in month_trades:
            rr = calculate_rr_stats(t)
            rrr_planned = rr["rrr_planned"]
            rrr_max = rr["rrr_max"]

            if rrr_planned is not None and rrr_max is not None:
                if rrr_planned <= rrr_max:
                    m_rr_logisk.append(rrr_planned)
                    w_l += 1
                else:
                    m_rr_logisk.append(-1)
                    l_l += 1

            if rrr_max is not None:
                if rr_max_filter:
                    try:
                        target = float(rr_max_filter)
                        if rrr_max >= target:
                            m_rr_max.append(target)
                            w_m += 1
                        else:
                            m_rr_max.append(-1)
                            l_m += 1
                    except:
                        continue
                else:
                    m_rr_max.append(rrr_max)
                    if rrr_max > 0:
                        w_m += 1
                    elif rrr_max < 0:
                        l_m += 1

        logisk_total, logisk_avg, logisk_wr, *_ = calc_stats(m_rr_logisk, w_l, l_l)
        max_total, max_avg, max_wr, *_ = calc_stats(m_rr_max, w_m, l_m)

        monthly_stats[month] = {
            "logisk": {"total": logisk_total, "avg": logisk_avg, "winrate": logisk_wr, "wins": w_l, "losses": l_l},
            "max": {"total": max_total, "avg": max_avg, "winrate": max_wr, "wins": w_m, "losses": l_m},
        }

    # Filter-badges
    active_filters = {}
    clear_links = {}
    for key, values in filters.items():
        non_empty = [v for v in values if v]
        if non_empty:
            active_filters[key] = non_empty
            for v in non_empty:
                updated_args = filters.copy()
                updated_args[key] = [val for val in non_empty if val != v]
                clear_links[f"{key}:{v}"] = url_for("stats_details") + "?" + urlencode(updated_args, doseq=True)

    return render_template("stats_details.html",
        total_rr_logisk=total_rr_logisk,
        avg_rr_logisk=avg_rr_logisk,
        winrate_logisk=winrate_logisk,
        wins_logisk=wins_logisk,
        losses_logisk=losses_logisk,
        total_trades_logisk=count_logisk_total,

        total_rr_max=total_rr_max,
        avg_rr_max=avg_rr_max,
        winrate_max=winrate_max,
        wins_max=wins_max,
        losses_max=losses_max,
        total_trades_max=count_max_total,

        active_filters=active_filters,
        clear_links=clear_links,
        monthly_stats=monthly_stats,

        journals=journals,
        active_journal_id=journal_id,
        active_journal_name=active_journal_name
    )





@app.route("/export_trades")
def export_trades():
    journal_id = get_active_journal()
    journal_name = get_journal_name(journal_id)
    trades, _ = get_all_trades({}, journal_id=journal_id)

    if not trades:
        return "Inga trades att exportera", 400

    # Hämta alla kolumnnamn från databasen (exkludera "id")
    db_columns = get_table_columns("trades")
    db_columns = [col for col in db_columns if col != "id"]

    # Rensa bort "id" från varje trade också
    cleaned_trades = []
    for t in trades:
        cleaned_trades.append({k: t.get(k, "") for k in db_columns})

    timestamp = datetime.now().strftime("%Y-%m-%d")
    safe_name = journal_name.replace(" ", "_").lower()
    filename = f"trades_{safe_name}_{timestamp}.csv"

    export_dir = os.path.join("static", "export")
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, filename)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=db_columns)
        writer.writeheader()
        writer.writerows(cleaned_trades)

    return send_file(filepath, as_attachment=True)



@app.route("/import_trades", methods=["POST"])
def import_trades():
    if 'file' not in request.files or request.files['file'].filename == '':
        flash("Ingen fil vald", "error")
        return redirect(request.referrer)

    file = request.files['file']
    journal_id = get_active_journal()
    stream = StringIO(file.stream.read().decode("utf-8"))
    reader = csv.DictReader(stream)

    conn = get_db_connection()
    cursor = conn.cursor()

    imported = 0
    skipped = 0

    db_columns = get_table_columns("trades")
    db_columns = [col for col in db_columns if col != "id"]

    for row in reader:
        # Ignorera kolumner som inte finns i databasen
        row = {k: v for k, v in row.items() if k in db_columns}
        row["journal_id"] = journal_id

        # Kontrollera dubblett
        check_query = """
            SELECT 1 FROM trades 
            WHERE journal_id = ?
              AND datum = ?
              AND instrument = ?
              AND setup = ?
              AND direction = ?
              AND rr_logisk = ?
        """
        values_check = (
            journal_id,
            row.get("datum"),
            row.get("instrument"),
            row.get("setup"),
            row.get("direction"),
            row.get("rr_logisk"),
        )
        existing = cursor.execute(check_query, values_check).fetchone()

        if existing:
            skipped += 1
            continue

        # Infoga trade
        columns = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        values = list(row.values())
        cursor.execute(f"INSERT INTO trades ({columns}) VALUES ({placeholders})", values)
        imported += 1

    conn.commit()
    conn.close()

    flash(f"{imported} trades importerades. {skipped} hoppades över (dubbletter).", "success")
    return redirect(request.referrer)






if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

