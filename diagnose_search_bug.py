
import os
import sys
import mysql.connector
from mysql.connector import Error

# Agregar el directorio actual al path para importar database.py y config.py
sys.path.append(os.getcwd())

import config
from utils.db_connector import get_db_connection
from database import run_query

def diagnose_serial(serial_to_search):
    print(f"--- Diagnóstico para Serial/MAC: {serial_to_search} ---")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        # 1. Buscar en series_registradas
        print("\n1. Buscando en 'series_registradas':")
        sql_s = "SELECT * FROM series_registradas WHERE UPPER(serial_number) = UPPER(%s) OR UPPER(mac_number) = UPPER(%s)"
        cursor.execute(sql_s, (serial_to_search, serial_to_search))
        series = cursor.fetchall()
        
        if not series:
            print(f"   ❌ No se encontró el serial '{serial_to_search}' en 'series_registradas'.")
        else:
            for s in series:
                print(f"   ✅ Encontrado: SKU={s['sku']}, Ubicacion={s['ubicacion']}, Estado={s['estado']}, Sucursal={s['sucursal']}")
        
        # 2. Buscar en productos (por SKU)
        if series:
            sku = series[0]['sku']
            print(f"\n2. Buscando SKU '{sku}' en 'productos':")
            sql_p = "SELECT * FROM productos WHERE sku = %s"
            cursor.execute(sql_p, (sku,))
            prods = cursor.fetchall()
            
            if not prods:
                print(f"   ❌ El SKU '{sku}' no tiene registros en la tabla 'productos'.")
            else:
                for p in prods:
                    print(f"   - Nombre={p['nombre']}, Ubicacion={p['ubicacion']}, Sucursal={p['sucursal']}, Stock={p['cantidad']}")

        # 3. Simular la lógica de buscar_equipo_global
        print("\n3. Verificando lógica de 'buscar_equipo_global':")
        from config import CURRENT_CONTEXT
        sucursal_target = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        print(f"   Contexto de sucursal actual: {sucursal_target}")
        
        sql_test = """
            SELECT s.serial_number, s.mac_number, s.sucursal
            FROM series_registradas s
            WHERE (UPPER(s.serial_number) = %s OR UPPER(s.mac_number) = %s)
              AND (s.sucursal = %s OR (s.sucursal IS NULL AND %s = 'CHIRIQUI'))
        """
        cursor.execute(sql_test, (serial_to_search, serial_to_search, sucursal_target, sucursal_target))
        match = cursor.fetchone()
        if match:
            print("   ✅ El filtro de sucursal COINCIDE.")
        else:
            print("   ❌ El filtro de sucursal NO COINCIDE.")

    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        diagnose_serial(sys.argv[1])
    else:
        # Serial del usuario anterior como ej
        diagnose_serial("GZ25040112723608")
