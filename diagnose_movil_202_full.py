from database import get_db_connection, run_query
import json

def diagnose_movil(movil):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"--- Diagnóstico Detallado para {movil} ---")
    
    # Raw assignments
    query = """
    SELECT sku_producto, cantidad, paquete, id 
    FROM asignacion_moviles 
    WHERE movil = ?
    """
    run_query(cursor, query, (movil,))
    rows = cursor.fetchall()
    
    print("\nRegistros en asignacion_moviles (TODOS):")
    for sku, qty, pq, rid in rows:
        print(f"ID: {rid:5} | SKU: {sku:15} | Qty: {qty:5} | Package: {pq}")
        
    conn.close()

if __name__ == "__main__":
    diagnose_movil("Movil 202")
