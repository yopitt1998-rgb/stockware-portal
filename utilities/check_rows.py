
import os
import mysql.connector
from dotenv import load_dotenv

# Load env from current directory
load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "SQLITE").upper()
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

print(f"Checking {DB_TYPE} database...")
print(f"Host: {MYSQL_HOST}")
print(f"User: {MYSQL_USER}")
print(f"DB: {MYSQL_DB}")

try:
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )
    cursor = conn.cursor()
    
    tables = [
        'productos', 'asignacion_moviles', 'movimientos', 
        'prestamos_activos', 'recordatorios_pendientes', 
        'configuracion', 'usuarios', 'moviles', 'consumos_pendientes'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Table {table}: {count} rows")
        except Exception as e:
            print(f"Table {table}: Error checking - {e}")
            
    conn.close()
except Exception as e:
    print(f"❌ Error connecting to database: {e}")
