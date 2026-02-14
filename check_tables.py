
from database import get_db_connection, run_query
import mysql.connector

try:
    print("Connecting to MySQL...")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    print("Listing tables in 'test'...")
    cursor.execute("USE test")
    run_query(cursor, "SHOW TABLES LIKE 'productos'")
    result = cursor.fetchone()
    if result:
        print(f"FOUND TABLE: {result[0]}")
    else:
        print("TABLE 'productos' NOT FOUND in 'test'")
        
    run_query(cursor, "SHOW TABLES")
    tables = cursor.fetchall()
    print(f"Total tables in 'test': {len(tables)}")
    for t in tables:
         if t[0] in ['productos', 'asignacion_moviles', 'moviles', 'series_registradas']:
             print(f" - {t[0]} [FOUND]")

        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
