
from database import get_db_connection
import mysql.connector

def test_tables():
    print("--- TESTING TABLES IN 'test' ---")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    try:
        print("\n1. Testing 'moviles' table...")
        cursor.execute("SELECT COUNT(*) FROM moviles")
        print(f"   SUCCESS: Found {cursor.fetchone()[0]} rows.")
    except Exception as e:
        print(f"   FAILURE: {e}")
        
    try:
        print("\n2. Testing 'asignacion_moviles' table...")
        cursor.execute("SELECT COUNT(*) FROM asignacion_moviles")
        print(f"   SUCCESS: Found {cursor.fetchone()[0]} rows.")
    except Exception as e:
        print(f"   FAILURE: {e}")

    try:
        print("\n3. Testing 'productos' table...")
        cursor.execute("SELECT COUNT(*) FROM productos")
        print(f"   SUCCESS: Found {cursor.fetchone()[0]} rows.")
    except Exception as e:
        print(f"   FAILURE: {e}")
        
    conn.close()

if __name__ == "__main__":
    test_tables()
