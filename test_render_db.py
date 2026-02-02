"""
Test what Render is actually seeing from the database
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 70)
print("TESTING RENDER DATABASE CONNECTION")
print("=" * 70)

try:
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
    cursor = conn.cursor()
    
    print(f"✅ Connected to: {os.getenv('MYSQL_HOST')}")
    print(f"   Database: {os.getenv('MYSQL_DATABASE')}")
    
    # Test 1: Check moviles
    print("\n" + "=" * 70)
    print("TEST 1: MOVILES TABLE")
    print("=" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM moviles")
    total_moviles = cursor.fetchone()[0]
    print(f"Total moviles: {total_moviles}")
    
    cursor.execute("SELECT COUNT(*) FROM moviles WHERE activo = 1")
    active_moviles = cursor.fetchone()[0]
    print(f"Active moviles: {active_moviles}")
    
    if total_moviles > 0:
        cursor.execute("SELECT nombre, activo FROM moviles ORDER BY nombre")
        print("\nAll moviles:")
        for row in cursor.fetchall():
            status = "✅ ACTIVE" if row[1] == 1 else "❌ INACTIVE"
            print(f"  {status} - {row[0]}")
    else:
        print("⚠️ NO MOVILES IN DATABASE!")
    
    # Test 2: Check productos
    print("\n" + "=" * 70)
    print("TEST 2: PRODUCTOS TABLE")
    print("=" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
    productos_count = cursor.fetchone()[0]
    print(f"Productos in BODEGA: {productos_count}")
    
    if productos_count > 0:
        cursor.execute("SELECT sku, nombre FROM productos WHERE ubicacion = 'BODEGA' LIMIT 5")
        print("\nFirst 5 productos:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}")
    else:
        print("⚠️ NO PRODUCTOS IN BODEGA!")
    
    # Test 3: Simulate what obtener_nombres_moviles() does
    print("\n" + "=" * 70)
    print("TEST 3: SIMULATING obtener_nombres_moviles()")
    print("=" * 70)
    
    query = "SELECT nombre, patente, conductor, ayudante, activo FROM moviles WHERE activo = 1 ORDER BY nombre ASC"
    cursor.execute(query)
    moviles_result = cursor.fetchall()
    
    print(f"Query returned {len(moviles_result)} rows")
    
    if moviles_result:
        nombres = [m[0] for m in moviles_result]
        print(f"Nombres list: {nombres}")
    else:
        print("⚠️ Query returned EMPTY!")
    
    conn.close()
    
    # Final verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    
    if active_moviles > 0 and productos_count > 0:
        print("✅ DATABASE HAS DATA")
        print(f"   Render should show {active_moviles} moviles and {productos_count} productos")
        print("\n⚠️ If Render still shows empty, the problem might be:")
        print("   1. Render is using a different database")
        print("   2. Render environment variables are different")
        print("   3. Render needs to be redeployed")
    else:
        print("❌ DATABASE IS STILL EMPTY")
        print("   The populate script may have failed")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
