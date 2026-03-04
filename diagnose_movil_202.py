from database import get_db_connection, run_query
import json

def diagnose_movil(movil):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"--- Diagnóstico para {movil} ---")
    
    # Check assignments
    query = """
    SELECT sku_producto, cantidad, paquete 
    FROM asignacion_moviles 
    WHERE movil = ?
    """
    run_query(cursor, query, (movil,))
    rows = cursor.fetchall()
    
    print("\nAsignaciones en asignacion_moviles:")
    for sku, qty, pq in rows:
        print(f"SKU: {sku:15} | Qty: {qty:5} | Package: {pq}")
        
    # Check series
    query = """
    SELECT sku, serial_number, paquete 
    FROM series_registradas 
    WHERE ubicacion = ?
    """
    run_query(cursor, query, (movil,))
    rows = cursor.fetchall()
    
    print("\nSeries en series_registradas:")
    for sku, sn, pq in rows:
        print(f"SKU: {sku:15} | SN: {sn:20} | Package: {pq}")
        
    conn.close()

if __name__ == "__main__":
    diagnose_movil("Movil 202")
