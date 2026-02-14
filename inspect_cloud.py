
from database import get_db_connection

def inspect_cloud_assignments():
    print("--- INSPECTING CLOUD ASSIGNMENTS ---")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    try:
        cursor.execute("USE test")
        cursor.execute("SELECT * FROM asignacion_moviles LIMIT 10")
        rows = cursor.fetchall()
        print(f"Total rows fetched: {len(rows)}")
        for r in rows:
            print(r)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_cloud_assignments()
