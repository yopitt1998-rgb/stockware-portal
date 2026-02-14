"""
Final verification that everything is working
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("FINAL VERIFICATION - WEB PORTAL DATA")
print("=" * 70)

from database import (
    obtener_nombres_moviles,
    obtener_todos_los_skus_para_movimiento,
    obtener_detalles_moviles
)
from config import DB_TYPE

print(f"\nDatabase Type: {DB_TYPE}")

# Test the functions that the web portal uses
print("\n1. obtener_nombres_moviles()...")
moviles = obtener_nombres_moviles()
print(f"   ✅ Returns {len(moviles)} moviles")
if moviles:
    print(f"   Moviles: {', '.join(moviles)}")

print("\n2. obtener_todos_los_skus_para_movimiento()...")
productos = obtener_todos_los_skus_para_movimiento()
print(f"   ✅ Returns {len(productos)} productos")
if productos:
    print(f"   First 3: {[p[0] for p in productos[:3]]}")

print("\n3. obtener_detalles_moviles()...")
detalles = obtener_detalles_moviles()
print(f"   ✅ Returns {len(detalles)} moviles with details")

# Simulate web server logic
print("\n" + "=" * 70)
print("WEB PORTAL STATUS")
print("=" * 70)

count_m = len(moviles)
count_p = len(productos)

if count_m == 0 and count_p == 0:
    status = "BASE DE DATOS VACÍA"
    print(f"❌ Status: {status}")
    print("   The web portal will show empty database message")
elif count_m == 0:
    status = "PARTIAL - No moviles"
    print(f"⚠️  Status: {status}")
    print("   The web portal will show products but no moviles")
elif count_p == 0:
    status = "PARTIAL - No productos"
    print(f"⚠️  Status: {status}")
    print("   The web portal will show moviles but no products")
else:
    status = "OK"
    print(f"✅ Status: {status}")
    print(f"   The web portal will show:")
    print(f"   - {count_m} moviles in dropdown")
    print(f"   - {count_p} productos in materials list")

print("\n" + "=" * 70)
if status == "OK":
    print("🎉 SUCCESS! Everything is ready")
    print("\n📋 NEXT STEPS:")
    print("   1. If web server is running: Refresh the browser page")
    print("   2. If web server is not running: Start it with:")
    print("      python app_inventario.py")
    print("      (or python web_server.py)")
else:
    print("⚠️  There are still issues to resolve")

print("=" * 70)
