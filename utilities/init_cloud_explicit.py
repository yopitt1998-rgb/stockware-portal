
import os
from database import get_db_connection
import mysql.connector

def init_cloud_tables():
    print("--- CONNECTING TO CLOUD DB ---")
    try:
        # Force MySQL connection
        conn = get_db_connection(target_db='MYSQL')
        cursor = conn.cursor()
        print("Connected.")
        
        # 1. PRODUCTOS
        print("Creating table 'productos'...")
        api_prod = """
            CREATE TABLE IF NOT EXISTS productos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                sku VARCHAR(50) NOT NULL,
                cantidad INTEGER NOT NULL DEFAULT 0,
                ubicacion VARCHAR(50) NOT NULL,
                minimo_stock INTEGER DEFAULT 10,
                categoria VARCHAR(100) DEFAULT 'General',
                marca VARCHAR(100) DEFAULT 'N/A',
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                secuencia_vista VARCHAR(20),
                codigo_barra VARCHAR(100),
                codigo_barra_maestro VARCHAR(100),
                UNIQUE (sku, ubicacion)
            )
        """
        cursor.execute(api_prod)
        print("Table 'productos' checked/created.")
        
        # 2. ASIGNACION_MOVILES
        print("Creating table 'asignacion_moviles'...")
        api_asig = """
            CREATE TABLE IF NOT EXISTS asignacion_moviles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sku_producto VARCHAR(50) NOT NULL,
                movil VARCHAR(100) NOT NULL,
                paquete VARCHAR(50),
                cantidad INTEGER NOT NULL DEFAULT 0,
                UNIQUE (sku_producto, movil, paquete)
            )
        """
        cursor.execute(api_asig)
        print("Table 'asignacion_moviles' checked/created.")
        
        # 3. MOVILES (Required for foreign keys or logic)
        print("Creating table 'moviles'...")
        api_mov = """
            CREATE TABLE IF NOT EXISTS moviles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL UNIQUE,
                patente VARCHAR(20),
                conductor VARCHAR(255),
                ayudante VARCHAR(255),
                activo INTEGER DEFAULT 1,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        cursor.execute(api_mov)
        print("Table 'moviles' checked/created.")
        
        conn.commit()
        conn.close()
        print("\n--- SUCCESS: Tables Initialized ---")
        return True
        
    except Exception as e:
        msg = f"\n❌ ERROR: {e}"
        print(msg)
        with open("init_log.txt", "w") as f:
            f.write(str(e))
        return False

if __name__ == "__main__":
    init_cloud_tables()
