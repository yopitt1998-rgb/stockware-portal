
import sqlite3
import mysql.connector
import config
from database import get_db_connection

def sync_moviles():
    print("--- SYNC MOVILES TO CLOUD ---")
    
    # 1. Read from Local SQLite
    print("Reading from Local SQLite...")
    local_conn = sqlite3.connect("inventario_sqlite.db")
    local_cursor = local_conn.cursor()
    local_cursor.execute("SELECT nombre, patente, conductor, ayudante, activo FROM moviles")
    local_data = local_cursor.fetchall()
    local_conn.close()
    
    print(f"Found {len(local_data)} records in Local DB.")
    
    # 2. Connect to Cloud MySQL
    print("Connecting to Cloud MySQL...")
    cloud_conn = get_db_connection(target_db='MYSQL')
    cloud_cursor = cloud_conn.cursor()
    
    # 3. Create Table if not exists
    create_sql = """
    CREATE TABLE IF NOT EXISTS moviles (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(50) UNIQUE NOT NULL,
        patente VARCHAR(20),
        conductor VARCHAR(100),
        ayudante VARCHAR(100),
        activo TINYINT DEFAULT 1
    )
    """
    try:
        cloud_cursor.execute(create_sql)
        print("Table 'moviles' ensuring...")
    except Exception as e:
        print(f"Error creating table: {e}")
        return

    # 4. Insert Data
    for row in local_data:
        nombre, patente, conductor, ayudante, activo = row
        print(f"Syncing: {nombre} ({conductor})")
        
        # Check if exists
        cloud_cursor.execute("SELECT id FROM moviles WHERE nombre = %s", (nombre,))
        existing = cloud_cursor.fetchone()
        
        if existing:
            # Update
            cloud_cursor.execute("""
                UPDATE moviles 
                SET patente=%s, conductor=%s, ayudante=%s, activo=%s 
                WHERE nombre=%s
            """, (patente, conductor, ayudante, activo, nombre))
        else:
            # Insert
            cloud_cursor.execute("""
                INSERT INTO moviles (nombre, patente, conductor, ayudante, activo)
                VALUES (%s, %s, %s, %s, %s)
            """, (nombre, patente, conductor, ayudante, activo))
            
    cloud_conn.commit()
    cloud_conn.close()
    print("Sync Complete!")

if __name__ == "__main__":
    sync_moviles()
