import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
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
            # Implementar pooling: crear pool por BD si no existe
            if db_name not in _mysql_pools:
                logger.info(f"🔌 [POOL] Creando pool de conexiones para MySQL -> DB: {db_name}")
                try:
                    _mysql_pools[db_name] = pooling.MySQLConnectionPool(
                        pool_name=f"pool_{db_name.replace('-', '_')}",
                        pool_size=3, # Desktop app, single user
                        pool_reset_session=True,
                        host=MYSQL_HOST,
                        user=MYSQL_USER,
                        password=MYSQL_PASS,
                        database=db_name,
                        port=MYSQL_PORT,
                        connect_timeout=60, # Increased for slow cloud responses
                        use_pure=True  # Avoid C extension issues
                    )
                except mysql.connector.Error as pool_err:
                    logger.error(f"Error creando pool MySQL para {db_name}: {pool_err}")
                    # Intentar conexión directa simple como fallback si falla el pool
                    # O relanzar para manejo superior
                    raise pool_err
            
            # Obtener conexión del pool
            return _mysql_pools[db_name].get_connection()
            
        except Exception as e:
            logger.error(f"Error conectando a MySQL ({db_name}): {e}")
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
