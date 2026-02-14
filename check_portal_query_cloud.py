
from database import get_db_connection

def check_portal_query():
    print("--- SIMULATING PORTAL QUERY ON CLOUD DB ---")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    try:
        cursor.execute("USE test")
        
        # 1. Check if 'Movil 200' has assignments
        cursor.execute("SELECT COUNT(*) FROM asignacion_moviles WHERE movil = 'Movil 200'")
        print(f"Assignments for Movil 200: {cursor.fetchone()[0]}")
        
        # 2. Check if products exist in BODEGA
        cursor.execute("SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
        print(f"Products in BODEGA: {cursor.fetchone()[0]}")
        
        # 3. Run the JOIN Query
        sql = """
            SELECT p.nombre, a.sku_producto, a.cantidad, COALESCE(a.paquete, 'NINGUNO') as paquete
            FROM asignacion_moviles a
            JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE a.movil = 'Movil 200' AND a.cantidad > 0
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        print(f"\n--- PORTAL QUERY RESULTS ({len(rows)} rows) ---")
        for r in rows:
            print(f"  {r}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_portal_query()
