import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    port=int(os.getenv("MYSQL_PORT", 3306))
)
cursor = conn.cursor()

print("FINAL VERIFICATION")
print("=" * 60)

cursor.execute("SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
productos_count = cursor.fetchone()[0]
print(f"✅ Productos in BODEGA: {productos_count}")

cursor.execute("SELECT COUNT(*) FROM moviles WHERE activo = 1")
moviles_count = cursor.fetchone()[0]
print(f"✅ Moviles activos: {moviles_count}")

print("\n" + "=" * 60)
if productos_count > 0 and moviles_count > 0:
    print("✅ DATABASE IS NOW WORKING!")
    print("   Web portal should show data correctly")
else:
    print("⚠️ Still has issues")

conn.close()
