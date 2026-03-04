
from database import get_db_connection, run_query
import sys

def check_cleaning():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("--- LOGS DE LIMPIEZA RECIENTES ---")
        run_query(cursor, "SELECT movil_afectado, paquete_asignado, observaciones, fecha_movimiento FROM movimientos WHERE tipo_movimiento='LIMPIEZA_MOVIL' ORDER BY id DESC LIMIT 20")
        res = cursor.fetchall()
        for r in res:
            print(f"Movil: {r[0]}, Paq: {r[1]}, Obs: {r[2]}, Fecha: {r[3]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_cleaning()
