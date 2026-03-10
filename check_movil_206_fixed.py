import os
import sys

# Asegurar que el directorio actual esté en el path para importar database
sys.path.append(os.getcwd())

from database import get_db_connection, close_connection

def check_movil_206():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("--- ASIGNACION MOVILES (Móvil 206) ---")
    cursor.execute("SELECT * FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = 'MOVIL 206'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    print("\n--- SERIES REGISTRADAS (Ubicación Móvil 206) ---")
    cursor.execute("SELECT sku, serial_number, mac_number, estado FROM series_registradas WHERE UPPER(TRIM(ubicacion)) = 'MOVIL 206'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    close_connection(conn)

if __name__ == "__main__":
    check_movil_206()
