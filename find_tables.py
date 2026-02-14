
from database import get_db_connection
import mysql.connector

def find_tables():
    print("--- SEARCHING FOR TABLES ---")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    # Get all databases
    cursor.execute("SHOW DATABASES")
    dbs = [d[0] for d in cursor.fetchall()]
    print(f"Databases found: {dbs}")
    
    found_any = False
    
    for db in dbs:
        if db in ['INFORMATION_SCHEMA', 'PERFORMANCE_SCHEMA', 'mysql', 'sys']:
            continue
            
        print(f"\nScanning DB: {db}...")
        try:
            cursor.execute(f"USE {db}")
            cursor.execute("SHOW TABLES")
            tables = [t[0] for t in cursor.fetchall()]
            
            if tables:
                print(f"  Tables: {tables}")
                if 'productos' in tables or 'asignacion_moviles' in tables:
                    print(f"  >>> FOUND TARGET TABLES IN: {db} <<<")
                    found_any = True
            else:
                print("  (Empty)")
                
        except Exception as e:
            print(f"  Error scanning {db}: {e}")

    conn.close()
    if not found_any:
        print("\n❌ Could not find target tables in any user database.")

if __name__ == "__main__":
    find_tables()
