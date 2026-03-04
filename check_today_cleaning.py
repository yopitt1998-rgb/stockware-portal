
from database import get_db_connection, run_query
import sys
from datetime import date

def check_today_cleaning():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = date.today().isoformat()
        print(f"--- LOGS DE LIMPIEZA PARA HOY ({today}) ---")
        
        # MySQL version
        query = "SELECT movil_afectado, paquete_asignado, observaciones, fecha_movimiento FROM movimientos WHERE tipo_movimiento='LIMPIEZA_MOVIL' AND DATE(fecha_movimiento) = %s ORDER BY id DESC"
        run_query(cursor, query, (today,))
        
        res = cursor.fetchall()
        if not res:
            print("No se encontraron limpiezas hoy.")
        else:
            for r in res:
                print(f"Movil: {r[0]}, Paq: {r[1]}, Obs: {r[2]}, Fecha: {r[3]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_today_cleaning()
