"""
Direct MySQL query to verify moviles table state
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("DIRECT MYSQL CHECK")
print("=" * 60)

try:
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
    cursor = conn.cursor()
    
    # Check moviles
    cursor.execute("SELECT COUNT(*) FROM moviles")
    count = cursor.fetchone()[0]
    print(f"Total moviles in database: {count}")
    
    if count > 0:
        cursor.execute("SELECT nombre, activo FROM moviles")
        print("\nMoviles found:")
        for row in cursor.fetchall():
            print(f"  - {row[0]} (activo={row[1]})")
    else:
        print("\n❌ MOVILES TABLE IS STILL EMPTY!")
        print("The fix_moviles.py script may not have worked")
        
        # Try to populate now
        print("\nAttempting to populate now...")
        from config import MOVILES_DISPONIBLES
        
        for movil in MOVILES_DISPONIBLES:
            try:
                cursor.execute(
                    "INSERT INTO moviles (nombre, activo) VALUES (%s, 1)",
                    (movil,)
                )
                print(f"  ✅ Inserted: {movil}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        conn.commit()
        
        # Verify again
        cursor.execute("SELECT COUNT(*) FROM moviles")
        new_count = cursor.fetchone()[0]
        print(f"\n✅ Now has {new_count} moviles")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Database error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
