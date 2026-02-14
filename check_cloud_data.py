
from database import get_db_connection

def check_cloud_data():
    print("--- CHECKING CLOUD DB DATA ---")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    try:
        print("Forcing USE test...")
        cursor.execute("USE test")
        
        # Check Products
        cursor.execute("SELECT COUNT(*) FROM productos")
        prod_count = cursor.fetchone()[0]
        print(f"Productos: {prod_count}")
        
        # Check Assignments
        cursor.execute("SELECT COUNT(*) FROM asignacion_moviles")
        asig_count = cursor.fetchone()[0]
        print(f"Asignaciones: {asig_count}")
        
        # Check Moviles defined
        cursor.execute("SELECT COUNT(*) FROM moviles")
        movil_count = cursor.fetchone()[0]
        print(f"Moviles: {movil_count}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_cloud_data()
