"""
Script de prueba para verificar SKUs disponibles en el sistema
"""
import sys
sys.path.insert(0, r'c:\Users\johni\Documents\GestorInventario_MySQL')

from database import obtener_todos_los_skus_para_movimiento

print("="*60)
print("VERIFICACIÓN DE SKUs DISPONIBLES PARA ABASTO")
print("="*60)

productos = obtener_todos_los_skus_para_movimiento()

if not productos:
    print("❌ ERROR: No se pudieron cargar productos de la base de datos")
else:
    print(f"✅ Se encontraron {len(productos)} productos en total\n")
    print("Primeros 20 productos:")
    print("-" * 60)
    print(f"{'Nombre':<30} {'SKU':<15} {'Stock':>10}")
    print("-" * 60)
    
    for nombre, sku, stock in productos[:20]:
        print(f"{nombre:<30} {sku:<15} {stock:>10}")
    
    if len(productos) > 20:
        print(f"\n... y {len(productos) - 20} productos más")
    
    print("\n" + "="*60)
    print("PRUEBA DE ESCANEO:")
    print("="*60)
    
    # Crear un diccionario simulando entry_vars
    entry_vars = {sku: f"Widget para {sku}" for nombre, sku, stock in productos}
    
    # Probar algunos códigos comunes
    codigos_prueba = [
        "1-2-16",      # FIBUNHILO
        "7-1-171",     # Cable UTP
        "10-1-04",     # Conector RJ45
        "4-4-644",     # ONT
        "U4-4-633",    # ONT con U al inicio
    ]
    
    print("\nProbando búsqueda de códigos:")
    for codigo in codigos_prueba:
        if codigo in entry_vars:
            print(f"✅ '{codigo}' - ENCONTRADO")
        else:
            # Búsqueda case-insensitive
            encontrado = False
            for sku in entry_vars.keys():
                if sku.upper() == codigo.upper():
                    print(f"⚠️  '{codigo}' - ENCONTRADO (diferente capitalización): '{sku}'")
                    encontrado = True
                    break
            if not encontrado:
                print(f"❌ '{codigo}' - NO ENCONTRADO")
    
    print("\n" + "="*60)

input("\nPresiona Enter para salir...")
