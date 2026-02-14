"""
Script to ensure MySQL database has moviles populated
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 60)
print("POPULATING MYSQL DATABASE WITH MOVILES")
print("=" * 60)

try:
    # Connect to MySQL
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
    cursor = conn.cursor()
    
    # Check current state
    cursor.execute("SELECT COUNT(*) FROM moviles")
    current_count = cursor.fetchone()[0]
    print(f"\nCurrent moviles in MySQL: {current_count}")
    
    if current_count > 0:
        cursor.execute("SELECT nombre FROM moviles")
        existing = [row[0] for row in cursor.fetchall()]
        print(f"Existing moviles: {existing}")
    
    # Get moviles from config
    from config import MOVILES_DISPONIBLES
    print(f"\nMoviles to ensure exist: {MOVILES_DISPONIBLES}")
    
    # Insert each movil if it doesn't exist
    inserted = 0
    for movil in MOVILES_DISPONIBLES:
        try:
            cursor.execute(
                "INSERT INTO moviles (nombre, activo) VALUES (%s, 1)",
                (movil,)
            )
            inserted += 1
            print(f"  ✅ Inserted: {movil}")
        except mysql.connector.IntegrityError:
            print(f"  ⏭️  Already exists: {movil}")
        except Exception as e:
            print(f"  ❌ Error with {movil}: {e}")
    
    conn.commit()
    
    # Verify final state
    cursor.execute("SELECT COUNT(*) FROM moviles WHERE activo = 1")
    final_count = cursor.fetchone()[0]
    
    print(f"\n✅ Final count of active moviles: {final_count}")
    
    # Show all moviles
    cursor.execute("SELECT nombre, activo FROM moviles ORDER BY nombre")
    print("\nAll moviles in database:")
    for row in cursor.fetchall():
        status = "✅" if row[1] == 1 else "❌"
        print(f"  {status} {row[0]}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("SUCCESS! MySQL database is ready")
    print("=" * 60)
    print("\n🔄 NEXT STEP: Restart the web server or desktop app")
    print("   to load the updated data")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
