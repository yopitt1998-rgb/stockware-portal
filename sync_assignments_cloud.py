
import sqlite3
from database import get_db_connection, run_query
import config

def sync_assignments():
    print("--- SYNCING ASSIGNMENTS FROM LOCAL SQLITE TO CLOUD MYSQL ---")
    
    # 1. Get Local Assignments
    print("Reading from Local SQLite...")
    # Manually connect to SQLite to avoid config.DB_TYPE override issues
    db_path = config.DATABASE_NAME
    conn_sqlite = sqlite3.connect(db_path)
    cursor_sqlite = conn_sqlite.cursor()
    
    # Check if 'paquete' column exists
    cursor_sqlite.execute("PRAGMA table_info(asignacion_moviles)")
    cols = [info[1] for info in cursor_sqlite.fetchall()]
    has_package = 'paquete' in cols
    
    if has_package:
        cursor_sqlite.execute("SELECT sku_producto, movil, paquete, cantidad FROM asignacion_moviles")
        rows = cursor_sqlite.fetchall()
        local_assignments = rows
    else:
        print("  (Local DB does not have 'paquete' column. Defaulting to None)")
        cursor_sqlite.execute("SELECT sku_producto, movil, cantidad FROM asignacion_moviles")
        rows = cursor_sqlite.fetchall()
        # Add None for package
        local_assignments = [(r[0], r[1], None, r[2]) for r in rows]
    conn_sqlite.close()
    
    print(f"Found {len(local_assignments)} assignments in local DB.")
    
    # 2. Push to Cloud MySQL
    print("Writing to Cloud MySQL...")
    conn_mysql = get_db_connection(target_db='MYSQL')
    cursor_mysql = conn_mysql.cursor()
    
    try:
        cursor_mysql.execute("USE test")
    except:
        pass
        
    synced = 0
    errors = 0
    
    for sku, movil, paquete, cantidad in local_assignments:
        try:
            # Check if exists
            query_check = "SELECT id FROM asignacion_moviles WHERE sku_producto = ? AND movil = ? AND paquete = ?"
            # MySQL uses %s, SQLite uses ? -> helper run_query usually handles this but here we use raw cursor for bulk
            # Let's use run_query which adapts in database.py but we need explicit format here if using raw cursor.
            # Actually run_query in database.py handles the DB_TYPE switch?
            # No, run_query converts ? to %s if DB_TYPE is MYSQL. 
            # But here 'conn_mysql' is definitely MySQL, checking how I obtained it.
            # database.py logic relies on global config.DB_TYPE for query formatting.
            
            # To be safe, I will manually format the query for MySQL (%s)
            check_sql = "SELECT id FROM asignacion_moviles WHERE sku_producto = %s AND movil = %s AND paquete = %s"
            cursor_mysql.execute(check_sql, (sku, movil, paquete))
            exists = cursor_mysql.fetchone()
            
            if exists:
                # Update
                update_sql = "UPDATE asignacion_moviles SET cantidad = %s WHERE id = %s"
                cursor_mysql.execute(update_sql, (cantidad, exists[0]))
            else:
                # Insert
                insert_sql = "INSERT INTO asignacion_moviles (sku_producto, movil, paquete, cantidad) VALUES (%s, %s, %s, %s)"
                cursor_mysql.execute(insert_sql, (sku, movil, paquete, cantidad))
            
            synced += 1
            if synced % 50 == 0:
                print(f"  Processed {synced}...")
                conn_mysql.commit()
                
    
        except Exception as e:
            print(f"Error syncing {sku} for {movil}: {e}")
            errors += 1

    conn_mysql.commit()
    conn_mysql.close()
    
    print(f" Sync Complete. Processed: {synced}. Errors: {errors}")

if __name__ == "__main__":
    sync_assignments()
