
from database import get_db_connection, run_query
from config import PRODUCTOS_CON_CODIGO_BARRA
import json

def simulate_api(movil):
    print(f"--- Simulating API for {movil} ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql_asignacion = """
        SELECT p.nombre, a.sku_producto, a.cantidad, COALESCE(a.paquete, 'NINGUNO') as paquete
        FROM asignacion_moviles a
        JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
        WHERE a.movil = ?
        AND a.cantidad > 0
    """
    run_query(cursor, sql_asignacion, (movil,))
    asignacion = cursor.fetchall()
    
    print(f"Found {len(asignacion)} items assigned.")
    
    inventario = []
    for nombre, sku, cantidad, paquete in asignacion:
        item = {
            "sku": sku,
            "nombre": nombre,
            "cantidad": cantidad,
            "paquete": paquete
        }
        print(f"   Item: {item}")
        inventario.append(item)
        
    conn.close()
    return inventario

if __name__ == "__main__":
    from config import MOVILES_DISPONIBLES, MOVILES_SANTIAGO
    all_moviles = MOVILES_DISPONIBLES + MOVILES_SANTIAGO
    
    print(f"Checking {len(all_moviles)} mobiles for assignments...")
    
    conn = get_db_connection()
    c = conn.cursor()
    run_query(c, "SELECT movil, COUNT(*) FROM asignacion_moviles GROUP BY movil")
    counts = c.fetchall()
    
    print("\n--- Summary of Assignments in Cloud DB ---")
    for m, count in counts:
        print(f"Mobile '{m}': {count} items")
        
    if not counts:
        print("NO ASSIGNMENTS FOUND IN CLOUD DB (Table empty or no matches).")
        
    conn.close()
