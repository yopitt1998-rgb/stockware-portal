
from database import get_db_connection, run_query
import sys

def global_audit():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("--- AUDITORIA GLOBAL DE ASIGNACIONES ---")
        run_query(cursor, "SELECT movil, COUNT(*), SUM(cantidad) FROM asignacion_moviles GROUP BY movil")
        res = cursor.fetchall()
        for r in res:
            print(f"Movil: {r[0]}, SKUs: {r[1]}, Unidades: {r[2]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    global_audit()
