import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
from contextlib import contextmanager
from utils.logger import get_logger
from config import (
    DATABASE_NAME,
    DB_TYPE,
    MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT
)

# Inicializar logger
logger = get_logger(__name__)

# Diccionario de pools por nombre de base de datos
_mysql_pools = {}

def get_db_connection(target_db=None):
    """
    Retorna una conexión activa a la base de datos de la sucursal actual.
    Implementa pooling para MySQL y conexión estándar para SQLite.
    
    Args:
        target_db (str, optional): Nombre específico de la BD a conectar. 
                                  Si es None, usa la BD del contexto actual.
    
    Returns:
        Connection: objeto de conexión (MySQLConnection o sqlite3.Connection)
        
    Raises:
        Exception: Si no se puede establecer la conexión.
    """
    global _mysql_pools
    
    # 1. Resolver Nombre de BD
    if target_db:
        db_name = target_db
    else:
        # Usar contexto dinámico (solo en app de escritorio)
        try:
            from config import get_current_db_name
            db_name = get_current_db_name()
        except ImportError:
            # Fallback para web server (no tiene contexto de sucursales)
            db_name = MYSQL_DB if DB_TYPE == 'MYSQL' else DATABASE_NAME
    
    # 2. Conectar según tipo de BD
    if DB_TYPE == 'MYSQL':
        try:
            if db_name not in _mysql_pools:
                logger.info(f"🔌 [POOL] Creando pool de conexiones para MySQL -> DB: {db_name}")
                _mysql_pools[db_name] = pooling.MySQLConnectionPool(
                    pool_name=f"pool_{db_name.replace('-', '_')}",
                    pool_size=10,
                    pool_reset_session=True,
                    host=MYSQL_HOST,
                    user=MYSQL_USER,
                    password=MYSQL_PASS,
                    database=db_name,
                    port=MYSQL_PORT,
                    connect_timeout=30,
                    use_pure=True
                )

            # Obtener conexión del pool
            return _mysql_pools[db_name].get_connection()

        except (mysql.connector.errors.PoolError,
                mysql.connector.errors.OperationalError,
                mysql.connector.errors.InterfaceError) as err:
            logger.warning(f"⚠️ [POOL] Error de conexión para {db_name}, reintentando una vez: {err}")
            # Limpiar pool si falló
            if db_name in _mysql_pools:
                try: del _mysql_pools[db_name]
                except: pass
            
            # Un solo reintento directo
            try:
                if db_name not in _mysql_pools:
                    _mysql_pools[db_name] = pooling.MySQLConnectionPool(
                        pool_name=f"pool_{db_name.replace('-', '_')}_retry",
                        pool_size=10,
                        pool_reset_session=True,
                        host=MYSQL_HOST,
                        user=MYSQL_USER,
                        password=MYSQL_PASS,
                        database=db_name,
                        port=MYSQL_PORT,
                        connect_timeout=30,
                        use_pure=True
                    )
                return _mysql_pools[db_name].get_connection()
            except Exception as e:
                logger.error(f"❌ [DB] Error fatal conectando a {db_name}: {e}")
                raise e
        except Exception as e:
            logger.error(f"❌ Error inesperado conectando a MySQL ({db_name}): {e}")
            raise e
    else:
        # SQLite
        try:
            conn = sqlite3.connect(db_name)
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except Exception as e:
            logger.error(f"Error conectando a SQLite ({db_name}): {e}")
            raise e

def close_connection(conn, cursor=None):
    """
    Cierra la conexión y el cursor de forma segura.
    
    Args:
        conn: Objeto de conexión
        cursor: Objeto de cursor (opcional)
    """
    try:
        if cursor:
            cursor.close()
    except Exception as e:
        logger.warning(f"Error cerrando cursor: {e}")
        
    try:
        if conn:
            conn.close()
    except Exception as e:
        logger.warning(f"Error cerrando conexión: {e}")

@contextmanager
def db_session(target_db=None, existing_conn=None):
    """
    Context manager para manejar el ciclo de vida automatizando commit/rollback y finally.
    Acepta 'existing_conn' para permitir transacciones anidadas (unirse al padre).
    Patrón de uso:
        with db_session() as (conn, cursor):
            ...
    """
    conn = existing_conn
    cursor = None
    we_created_conn = False

    try:
        if conn is None:
            conn = get_db_connection(target_db)
            we_created_conn = True

        # Usar cursores con buffer para MySQL para evitar problemas de "Unread result found"
        if DB_TYPE == 'MYSQL':
            cursor = conn.cursor(buffered=True)
        else:
            cursor = conn.cursor()

        yield conn, cursor

        # Solo hacer commit si esta sesión fue la que abrió la conexión (es el nivel más alto)
        if we_created_conn:
            conn.commit()

    except Exception as e:
        # Solo hacer rollback si esta sesión es la dueña de la conexión
        if we_created_conn and conn:
            conn.rollback()
        raise e
    finally:
        # Siempre cerramos el cursor que abrimos en ESTA sesión
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                logger.warning(f"Error cerrando cursor en db_session: {e}")
        
        # Solo cerramos la conexión si nosotros la creamos
        if we_created_conn and conn:
            close_connection(conn)
