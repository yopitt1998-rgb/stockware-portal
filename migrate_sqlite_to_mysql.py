import sqlite3
import mysql.connector
import os
from database import inicializar_bd, get_db_connection
from config import DATABASE_NAME, DB_TYPE

def migrar():
    if DB_TYPE != 'MYSQL':
        print("❌ Para migrar, el DB_TYPE en .env o config.py debe ser 'MYSQL'.")
        return

    print("🚀 INICIANDO MIGRACIÓN: SQLite -> Cloud MySQL")
    
    # 1. Asegurar que MySQL tiene las tablas (Limpiar primero para actualizar esquema)
    print("📋 Preparando tablas en MySQL...")
    try:
        mysql_conn = get_db_connection()
        mysql_cur = mysql_conn.cursor()
        tablas_a_limpiar = [
            'productos', 'asignacion_moviles', 'movimientos', 
            'prestamos_activos', 'recordatorios_pendientes', 
            'configuracion', 'usuarios', 'moviles', 'consumos_pendientes'
        ]
        print("🧹 Limpiando esquema viejo en la nube...")
        for t in tablas_a_limpiar:
            mysql_cur.execute(f"DROP TABLE IF EXISTS {t}")
        mysql_conn.commit()
        mysql_conn.close()
    except Exception as e:
        print(f"⚠️ Error limpiando esquema: {e}")

    if not inicializar_bd():
        print("❌ Error al preparar las tablas en MySQL.")
        return

    try:
        # Conexiones
        sqlite_conn = sqlite3.connect(DATABASE_NAME)
        mysql_conn = get_db_connection()
        
        sqlite_cur = sqlite_conn.cursor()
        mysql_cur = mysql_conn.cursor()

        tablas = [
            'productos', 'asignacion_moviles', 'movimientos', 
            'prestamos_activos', 'recordatorios_pendientes', 
            'configuracion', 'usuarios', 'moviles', 'consumos_pendientes'
        ]

        for tabla in tablas:
            print(f"📦 Migrando tabla: {tabla}...")
            
            try:
                # Obtener datos de SQLite
                sqlite_cur.execute(f"SELECT * FROM {tabla}")
                filas = sqlite_cur.fetchall()
                
                if not filas:
                    print(f"   (Sin datos en {tabla})")
                    continue

                # Obtener nombres de columnas
                sqlite_cur.execute(f"PRAGMA table_info({tabla})")
                columnas = [c[1] for c in sqlite_cur.fetchall()]
                print(f"   Columnas detectadas en SQLite: {columnas}")
                
                # Preparar insert en MySQL
                placeholders = ", ".join(["%s"] * len(columnas))
                col_string = ", ".join(columnas)
                insert_query = f"INSERT IGNORE INTO {tabla} ({col_string}) VALUES ({placeholders})"
                print(f"   Consulta: {insert_query}")
                
                mysql_cur.executemany(insert_query, filas)
                mysql_conn.commit()
                print(f"   ✅ {len(filas)} registros migrados.")
            except Exception as table_err:
                print(f"   ❌ Error en tabla {tabla}: {table_err}")

        print("\n✨ ¡PROCESO DE MIGRACIÓN FINALIZADO! ✨")

    except Exception as e:
        print(f"❌ Error crítico durante la migración: {e}")
    finally:
        sqlite_conn.close()
        mysql_conn.close()

if __name__ == "__main__":
    migrar()
