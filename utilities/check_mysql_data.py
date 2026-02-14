
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    port=int(os.getenv("MYSQL_PORT", 3306))
)
cursor = conn.cursor()
cursor.execute("SELECT tipo_movimiento, COUNT(*) FROM movimientos GROUP BY tipo_movimiento")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")
conn.close()
