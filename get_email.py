import sqlite3
import os

db_path = 'c:/Users/user/mini/bloodbank.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM donor LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Email: {row[0]}")
    else:
        print("No donors found.")
    conn.close()
else:
    print("Database file not found.")
