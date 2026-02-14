from database import get_db_connection
from config import DB_TYPE, MYSQL_HOST, MYSQL_DB, MYSQL_USER

def inspect_cloud():
    print(f"--- DIAGNÓSTICO DE NUBE ---")
    print(f"DB_TYPE: {DB_TYPE}")
    print(f"HOST: {MYSQL_HOST}")
    print(f"DB: {MYSQL_DB}")
    print(f"USER: {MYSQL_USER}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Listar tablas
        print("\n--- TABLAS ENCONTRADAS ---")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        for t in tables:
            print(f"- {t[0]}")
            
        # Conteo detallado
        for table in ['productos', 'moviles', 'usuarios', 'movimientos']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ Tabla '{table}': {count} filas")
            except Exception as e:
                print(f"❌ Error en tabla '{table}': {e}")
                
        # Verificar BODEGA
        try:
            cursor.execute("SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
            count = cursor.fetchone()[0]
            print(f"📊 Productos en 'BODEGA': {count}")
        except: pass

    except Exception as e:
        print(f"❌ ERROR GENERAL: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    inspect_cloud()
