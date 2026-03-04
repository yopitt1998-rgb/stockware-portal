
from database import get_db_connection, run_query
import sys

def check_db(movil):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"--- ASIGNACION_MOVILES para {movil} ---")
        run_query(cursor, "SELECT sku_producto, paquete, cantidad FROM asignacion_moviles WHERE movil=%s", (movil,))
        res = cursor.fetchall()
        for r in res:
            print(f"SKU: {r[0]}, Paquete: {r[1]}, Cantidad: {r[2]}")
            
        print(f"\n--- MOVIMIENTOS RECIENTES para {movil} ---")
        run_query(cursor, "SELECT sku_producto, tipo_movimiento, cantidad_afectada, paquete_asignado, fecha_movimiento FROM movimientos WHERE movil_afectado=%s ORDER BY id DESC LIMIT 5", (movil,))
        res = cursor.fetchall()
        for r in res:
            print(f"SKU: {r[0]}, Tipo: {r[1]}, Cant: {r[2]}, Paq: {r[3]}, Fecha: {r[4]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db("Movil 201")
