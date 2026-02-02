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

print("=" * 60)
print("CHECKING MOVILES TABLE")
print("=" * 60)

# Check if table exists
cursor.execute("SHOW TABLES LIKE 'moviles'")
if cursor.fetchone():
    print("✅ Table 'moviles' exists")
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM moviles")
    count = cursor.fetchone()[0]
    print(f"📊 Total moviles: {count}")
    
    if count > 0:
        cursor.execute("SELECT nombre, patente, conductor, ayudante, activo FROM moviles")
        print("\nMoviles in database:")
        for row in cursor.fetchall():
            print(f"  - {row[0]} (Activo: {row[4]})")
    else:
        print("\n⚠️ MOVILES TABLE IS EMPTY!")
        print("\nThis is why the web portal shows 'BASE DE DATOS VACÍA'")
        print("\nSolution: Need to populate moviles table from MOVILES_DISPONIBLES config")
        
        from config import MOVILES_DISPONIBLES
        print(f"\nMOVILES_DISPONIBLES from config: {MOVILES_DISPONIBLES}")
        
        print("\n" + "=" * 60)
        print("POPULATING MOVILES TABLE")
        print("=" * 60)
        
        for movil in MOVILES_DISPONIBLES:
            try:
                cursor.execute(
                    "INSERT INTO moviles (nombre, activo) VALUES (%s, 1)",
                    (movil,)
                )
                print(f"✅ Inserted: {movil}")
            except Exception as e:
                print(f"❌ Error inserting {movil}: {e}")
        
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM moviles")
        new_count = cursor.fetchone()[0]
        print(f"\n✅ Moviles table now has {new_count} records")
else:
    print("❌ Table 'moviles' does not exist!")

conn.close()

print("\n" + "=" * 60)
print("CHECK COMPLETED")
print("=" * 60)
