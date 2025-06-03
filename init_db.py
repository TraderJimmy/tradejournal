import sqlite3

# Skapa anslutning till databasen
conn = sqlite3.connect("trades.db")
cursor = conn.cursor()

# Skapa tabellen
cursor.execute("""
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kommentar TEXT,
    bild1 TEXT,
    bild2 TEXT
)
""")

# Lägg till några testtrades
cursor.execute("INSERT INTO trades (kommentar, bild1, bild2) VALUES (?, ?, ?)", (
    "Testtrade 1", 
    "https://via.placeholder.com/400x300.png?text=Bild+1", 
    "https://via.placeholder.com/400x300.png?text=Bild+2"
))

cursor.execute("INSERT INTO trades (kommentar, bild1, bild2) VALUES (?, ?, ?)", (
    "Testtrade 2", 
    "https://via.placeholder.com/400x300.png?text=Bild+1", 
    "https://via.placeholder.com/400x300.png?text=Bild+2"
))

conn.commit()
conn.close()

print("Databasen trades.db skapad med testdata.")
