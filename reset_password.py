import mysql.connector
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos
config = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
    'port': int(os.getenv('MYSQL_PORT', 3306))
}

try:
    # Conectar a la base de datos
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor(dictionary=True)
    
    print("✅ Conexión exitosa a la base de datos\n")
    
    # Verificar si la tabla usuarios existe
    cursor.execute("SHOW TABLES LIKE 'usuarios'")
    if not cursor.fetchone():
        print("❌ La tabla 'usuarios' no existe")
    else:
        # Listar usuarios existentes
        cursor.execute("SELECT usuario, rol FROM usuarios")
        usuarios = cursor.fetchall()
        
        print("📋 Usuarios en la base de datos:")
        print("-" * 60)
        for u in usuarios:
            usuario = u.get('usuario', 'N/A')
            rol = u.get('rol', 'N/A')
            print(f"Usuario: {usuario} | Rol: {rol}")
        print("-" * 60)
        print()
        
        # Verificar si existe el usuario 'admin'
        cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
        admin = cursor.fetchone()
        
        if admin:
            print("🔧 Actualizando contraseña del usuario 'admin' a 'admin123'...")
            cursor.execute("""
                UPDATE usuarios 
                SET password = 'admin123' 
                WHERE usuario = 'admin'
            """)
            conn.commit()
            print("✅ Contraseña actualizada exitosamente")
        else:
            print("➕ Creando usuario 'admin' con contraseña 'admin123'...")
            cursor.execute("""
                INSERT INTO usuarios (usuario, password, rol) 
                VALUES ('admin', 'admin123', 'ADMIN')
            """)
            conn.commit()
            print("✅ Usuario 'admin' creado exitosamente")
        
        print("\n" + "="*60)
        print("CREDENCIALES DE ACCESO:")
        print("Usuario: admin")
        print("Contraseña: admin123")
        print("="*60)
    
    cursor.close()
    conn.close()
    
except mysql.connector.Error as err:
    print(f"❌ Error de base de datos: {err}")
except Exception as e:
    print(f"❌ Error: {e}")

input("\nPresiona Enter para cerrar...")
