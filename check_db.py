import sqlite3
import os

db_path = r'c:\Users\johni\Documents\GestorInventario_MySQL\inventario_chiriqui.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- RECENT CONSUMOS ---")
cursor.execute("SELECT id, movil, sku, fecha, estado, fecha_registro FROM consumos_pendientes ORDER BY fecha_registro DESC LIMIT 20")
for row in cursor.fetchall():
    print(row)

print("\n--- MOVILES IN DB ---")
cursor.execute("SELECT DISTINCT movil FROM consumos_pendientes")
print([r[0] for r in cursor.fetchall()])

conn.close()
