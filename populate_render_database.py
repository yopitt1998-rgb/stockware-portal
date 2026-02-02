"""
Script to populate the REMOTE MySQL database (Render deployment) with moviles
This connects to the same MySQL database that Render uses
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 70)
print("POPULATING RENDER CLOUD DATABASE WITH MOVILES")
print("=" * 70)

# These are the same credentials that Render uses
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

print(f"\nConnecting to: {MYSQL_HOST}")
print(f"Database: {MYSQL_DATABASE}")

try:
    # Connect to the SAME MySQL that Render uses
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT
    )
    cursor = conn.cursor()
    
    print("✅ Connected successfully")
    
    # Check current state
    cursor.execute("SELECT COUNT(*) FROM moviles")
    current_count = cursor.fetchone()[0]
    print(f"\nCurrent moviles in database: {current_count}")
    
    if current_count > 0:
        cursor.execute("SELECT nombre, activo FROM moviles")
        print("\nExisting moviles:")
        for row in cursor.fetchall():
            status = "✅" if row[1] == 1 else "❌"
            print(f"  {status} {row[0]}")
    
    # Get moviles from config
    from config import MOVILES_DISPONIBLES
    print(f"\nMoviles to insert: {MOVILES_DISPONIBLES}")
    
    # Insert each movil
    inserted = 0
    skipped = 0
    for movil in MOVILES_DISPONIBLES:
        try:
            cursor.execute(
                "INSERT INTO moviles (nombre, activo) VALUES (%s, 1)",
                (movil,)
            )
            inserted += 1
            print(f"  ✅ Inserted: {movil}")
        except mysql.connector.IntegrityError:
            skipped += 1
            print(f"  ⏭️  Already exists: {movil}")
        except Exception as e:
            print(f"  ❌ Error with {movil}: {e}")
    
    conn.commit()
    
    # Verify final state
    cursor.execute("SELECT COUNT(*) FROM moviles WHERE activo = 1")
    final_count = cursor.fetchone()[0]
    
    print(f"\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"✅ Inserted: {inserted}")
    print(f"⏭️  Skipped (already existed): {skipped}")
    print(f"📊 Total active moviles: {final_count}")
    
    # Verify productos too
    cursor.execute("SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
    productos_count = cursor.fetchone()[0]
    print(f"📦 Total productos in BODEGA: {productos_count}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("SUCCESS!")
    print("=" * 70)
    print("\n🌐 The Render portal should now show:")
    print(f"   - {final_count} moviles in dropdown")
    print(f"   - {productos_count} productos in materials list")
    print("\n🔄 Refresh the page: https://stockware-portal.onrender.com/")
    print("   (No need to restart Render - just refresh the browser)")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
