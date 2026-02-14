"""
Test script to verify what the web server is actually getting from the database
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("WEB SERVER DATABASE TEST")
print("=" * 60)

# Simulate what web_server.py does
from database import (
    obtener_nombres_moviles,
    obtener_todos_los_skus_para_movimiento,
    obtener_detalles_moviles
)

print("\n1. Testing obtener_nombres_moviles()...")
try:
    moviles = obtener_nombres_moviles()
    print(f"   Result: {moviles}")
    print(f"   Count: {len(moviles)}")
    print(f"   Type: {type(moviles)}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n2. Testing obtener_todos_los_skus_para_movimiento()...")
try:
    productos = obtener_todos_los_skus_para_movimiento()
    print(f"   Count: {len(productos)}")
    if len(productos) > 0:
        print(f"   First 3: {productos[:3]}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n3. Testing obtener_detalles_moviles()...")
try:
    details = obtener_detalles_moviles()
    print(f"   Count: {len(details)}")
    print(f"   Keys: {list(details.keys())}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

# Check what the web server index route would see
print("\n" + "=" * 60)
print("SIMULATING WEB SERVER INDEX ROUTE")
print("=" * 60)

count_m = len(moviles) if 'moviles' in locals() else 0
count_p = len(productos) if 'productos' in locals() else 0

print(f"count_m (moviles): {count_m}")
print(f"count_p (productos): {count_p}")

if count_m == 0 and count_p == 0:
    print("\n❌ STATUS: BASE DE DATOS VACÍA")
    print("   This is what the user would see!")
elif count_m == 0:
    print("\n⚠️ STATUS: No moviles, but has productos")
elif count_p == 0:
    print("\n⚠️ STATUS: Has moviles, but no productos")
else:
    print("\n✅ STATUS: OK")
    print(f"   {count_m} moviles and {count_p} productos available")

print("=" * 60)
