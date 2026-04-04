from utils.db_connector import db_session
from config import DB_TYPE

def run_corrective_migration():
    print("🚀 Iniciando corrección de migración SKU 4-4-654 -> 4-4-656...")
    
    OLD_SKU = '4-4-654'
    NEW_SKU = '4-4-656'
    
    try:
        with db_session() as (conn, cursor):
            # 1. CORREGIR LA TABLA DE SERIALES (LA MÁS IMPORTANTE)
            print("🔢 Corrigiendo tabla series_registradas...")
            cursor.execute("UPDATE series_registradas SET sku = %s WHERE sku = %s" if DB_TYPE == 'MYSQL' else "UPDATE series_registradas SET sku = ? WHERE sku = ?", (NEW_SKU, OLD_SKU))
            print(f"   Filas afectadas: {cursor.rowcount}")

            # 2. AGREGAR ALIAS EN PRODUCTOS (Para que si escanean el SKU viejo como barcode, funcione)
            print("🏷️ Agregando 4-4-654 como barcode secundario para 4-4-656...")
            cursor.execute("UPDATE productos SET codigo_barra = %s WHERE sku = %s AND (codigo_barra IS NULL OR codigo_barra = '')" if DB_TYPE == 'MYSQL' else "UPDATE productos SET codigo_barra = ? WHERE sku = ? AND (codigo_barra IS NULL OR codigo_barra = '')", (OLD_SKU, NEW_SKU))
            
            # 3. OTROS POSIBLES SALTADOS
            tablas_adicionales = [
                ("faltantes_registrados", "sku"),
                ("seriales_faltantes_detalle", "sku"), # Por si acaso existe esta columna
                ("recordatorios_pendientes", "sku"),   # No suele tener pero validamos
                ("usuarios", "sku"),                   # No
            ]
            
            for tabla, columna in tablas_adicionales:
                try:
                    print(f"🔄 Intentando actualizar {tabla}...")
                    cursor.execute(f"UPDATE {tabla} SET {columna} = %s WHERE {columna} = %s" if DB_TYPE == 'MYSQL' else f"UPDATE {tabla} SET {columna} = ? WHERE {columna} = ?", (NEW_SKU, OLD_SKU))
                    if cursor.rowcount > 0:
                        print(f"   Actualizada: {tabla} ({cursor.rowcount} filas)")
                except Exception:
                    pass # Probablemente la tabla/columna no existe

            print("✅ Corrección de base de datos completada.")
            return True

    except Exception as e:
        print(f"❌ Error durante la corrección: {e}")
        return False

if __name__ == "__main__":
    run_corrective_migration()
