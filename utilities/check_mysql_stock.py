
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
cursor.execute("SELECT COUNT(*), SUM(cantidad) FROM productos")
res = cursor.fetchone()
print(f"Productos: {res[0]} rows, Total Stock: {res[1]}")

cursor.execute("SELECT COUNT(*) FROM asignacion_moviles")
print(f"Asignacion Moviles: {cursor.fetchone()[0]} rows")

conn.close()
