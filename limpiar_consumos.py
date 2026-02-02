"""
Script para limpiar datos de consumos_pendientes
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 70)
print("LIMPIEZA DE CONSUMOS PENDIENTES")
print("=" * 70)

try:
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
    cursor = conn.cursor()
    
    # Contar registros antes
    cursor.execute("SELECT COUNT(*) FROM consumos_pendientes")
    count_antes = cursor.fetchone()[0]
    
    print(f"\n📊 Registros actuales: {count_antes}")
    
    if count_antes == 0:
        print("\n✅ No hay registros para borrar")
    else:
        print("\n⚠️ OPCIONES DE LIMPIEZA:")
        print("1. Borrar TODOS los consumos pendientes")
        print("2. Borrar solo consumos AUDITADOS (ya procesados)")
        print("3. Borrar consumos anteriores a una fecha")
        print("4. Cancelar")
        
        opcion = input("\nSelecciona una opción (1-4): ").strip()
        
        if opcion == "1":
            confirmar = input(f"\n¿Estás seguro de borrar TODOS los {count_antes} registros? (si/no): ").strip().lower()
            if confirmar == "si":
                cursor.execute("DELETE FROM consumos_pendientes")
                conn.commit()
                print(f"\n✅ Se borraron {count_antes} registros")
            else:
                print("\n❌ Operación cancelada")
        
        elif opcion == "2":
            cursor.execute("SELECT COUNT(*) FROM consumos_pendientes WHERE estado = 'AUDITADO'")
            count_auditados = cursor.fetchone()[0]
            
            if count_auditados == 0:
                print("\n✅ No hay consumos auditados para borrar")
            else:
                confirmar = input(f"\n¿Borrar {count_auditados} consumos AUDITADOS? (si/no): ").strip().lower()
                if confirmar == "si":
                    cursor.execute("DELETE FROM consumos_pendientes WHERE estado = 'AUDITADO'")
                    conn.commit()
                    print(f"\n✅ Se borraron {count_auditados} consumos auditados")
                else:
                    print("\n❌ Operación cancelada")
        
        elif opcion == "3":
            fecha = input("\nBorrar consumos anteriores a (YYYY-MM-DD): ").strip()
            cursor.execute("SELECT COUNT(*) FROM consumos_pendientes WHERE fecha < %s", (fecha,))
            count_fecha = cursor.fetchone()[0]
            
            if count_fecha == 0:
                print(f"\n✅ No hay consumos anteriores a {fecha}")
            else:
                confirmar = input(f"\n¿Borrar {count_fecha} consumos anteriores a {fecha}? (si/no): ").strip().lower()
                if confirmar == "si":
                    cursor.execute("DELETE FROM consumos_pendientes WHERE fecha < %s", (fecha,))
                    conn.commit()
                    print(f"\n✅ Se borraron {count_fecha} consumos")
                else:
                    print("\n❌ Operación cancelada")
        
        else:
            print("\n❌ Operación cancelada")
    
    # Contar registros después
    cursor.execute("SELECT COUNT(*) FROM consumos_pendientes")
    count_despues = cursor.fetchone()[0]
    
    print(f"\n📊 Registros restantes: {count_despues}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("IMPORTANTE:")
    print("- Reinicia la aplicación para ver los cambios")
    print("- En la app, también puedes usar el botón '🗑️ Limpiar Todo'")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
