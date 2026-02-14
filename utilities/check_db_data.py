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

print("=" * 60)
print("VERIFICACIÓN DE TABLAS Y DATOS")
print("=" * 60)

# Listar todas las tablas
cursor.execute("SHOW TABLES")
tables = cursor.fetchall()
print(f"\n📋 Tablas encontradas: {len(tables)}")
for (table,) in tables:
    print(f"  - {table}")

print("\n" + "=" * 60)
print("CONTEO DE REGISTROS POR TABLA")
print("=" * 60)

# Contar registros en cada tabla
for (table,) in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count} registros")

# Verificar específicamente productos y movimientos
print("\n" + "=" * 60)
print("DETALLE DE PRODUCTOS")
print("=" * 60)

cursor.execute("SELECT COUNT(*) FROM productos")
productos_count = cursor.fetchone()[0]
print(f"Total productos: {productos_count}")

if productos_count > 0:
    cursor.execute("SELECT sku, nombre, ubicacion FROM productos LIMIT 10")
    print("\nPrimeros 10 productos:")
    for row in cursor.fetchall():
        print(f"  SKU: {row[0]}, Nombre: {row[1]}, Ubicación: {row[2]}")
else:
    print("⚠️ NO HAY PRODUCTOS EN LA BASE DE DATOS")

print("\n" + "=" * 60)
print("DETALLE DE MOVIMIENTOS")
print("=" * 60)

cursor.execute("SELECT COUNT(*) FROM movimientos")
movimientos_count = cursor.fetchone()[0]
print(f"Total movimientos: {movimientos_count}")

if movimientos_count > 0:
    cursor.execute("""
        SELECT tipo_movimiento, COUNT(*) 
        FROM movimientos 
        GROUP BY tipo_movimiento
    """)
    print("\nMovimientos por tipo:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
else:
    print("⚠️ NO HAY MOVIMIENTOS EN LA BASE DE DATOS")

# Verificar ubicaciones
print("\n" + "=" * 60)
print("PRODUCTOS POR UBICACIÓN")
print("=" * 60)

cursor.execute("""
    SELECT ubicacion, COUNT(*) 
    FROM productos 
    GROUP BY ubicacion
""")
ubicaciones = cursor.fetchall()
if ubicaciones:
    for row in ubicaciones:
        print(f"  {row[0]}: {row[1]} productos")
else:
    print("⚠️ NO HAY PRODUCTOS CON UBICACIONES")

conn.close()
print("\n" + "=" * 60)
print("VERIFICACIÓN COMPLETADA")
print("=" * 60)
