
from database import get_db_connection, run_query

def clean_cloud_moviles():
    try:
        print("Connecting to Cloud DB...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Mobiles to keep (Chiriqui)
        to_keep = ["Movil 200", "Movil 201", "Movil 202", "Movil 203", "Movil 204", "Movil 205", "Movil 206"]
        
        # Mobiles to remove (Santiago - 207-210)
        to_remove = ["Movil 207", "Movil 208", "Movil 209", "Movil 210"]
        
        print(f"Removing Santiago mobiles from 'moviles' table: {to_remove}")
        
        # Using %s since get_db_connection gives MySQL/TiDB connection
        placeholders = ", ".join(["%s"] * len(to_remove))
        sql = f"DELETE FROM moviles WHERE nombre IN ({placeholders})"
        
        cursor.execute(sql, tuple(to_remove))
        deleted_count = cursor.rowcount
        
        conn.commit()
        print(f"✅ Success! Deleted {deleted_count} mobiles from cloud.")
        
        # Verify 206 exists
        cursor.execute("SELECT nombre FROM moviles WHERE nombre = %s", ("Movil 206",))
        if cursor.fetchone():
            print("✅ Verified: Movil 206 is present in cloud 'moviles' table.")
        else:
            print("⚠️ Warning: Movil 206 is NOT in cloud 'moviles' table. Adding it...")
            cursor.execute("INSERT INTO moviles (nombre, activo) VALUES (%s, 1) ON DUPLICATE KEY UPDATE activo = 1", ("Movil 206",))
            conn.commit()
            print("✅ Movil 206 added/updated.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    clean_cloud_moviles()
