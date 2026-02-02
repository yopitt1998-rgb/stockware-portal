"""
Check if SQLite database exists and has data
"""
import os
import sqlite3

db_path = "inventario_sqlite.db"

if os.path.exists(db_path):
    print(f"✅ SQLite database found: {db_path}")
    print(f"   Size: {os.path.getsize(db_path)} bytes")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check moviles
        cursor.execute("SELECT COUNT(*) FROM moviles")
        moviles_count = cursor.fetchone()[0]
        print(f"   Moviles: {moviles_count}")
        
        # Check productos
        cursor.execute("SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
        productos_count = cursor.fetchone()[0]
        print(f"   Productos (BODEGA): {productos_count}")
        
        conn.close()
        
        if moviles_count == 0 and productos_count == 0:
            print("\n❌ SQLite database is EMPTY!")
            print("   This is why web portal shows empty when using SQLite")
        
    except Exception as e:
        print(f"   Error reading SQLite: {e}")
else:
    print(f"❌ SQLite database NOT found: {db_path}")
