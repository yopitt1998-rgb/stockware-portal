
from database import obtener_consumos_pendientes
import json

print("--- TESTING CONSOLIDATED HISTORY (ESTADO='TODOS') ---")
res = obtener_consumos_pendientes(moviles_filtro=['Movil 203'], estado='TODOS', limite=10)
print(f"Total found for 203: {len(res)}")
for r in res:
    print(f"ID: {r[0]} | Movil: {r[1]} | SKU: {r[2]} | Nombre: {r[3]} | Fecha: {r[7]} | Estado: {r[13]}")

print("\n--- TESTING CHIRIQUI CONTEXT ---")
from config import CURRENT_CONTEXT
CURRENT_CONTEXT['BRANCH'] = 'CHIRIQUI'
CURRENT_CONTEXT['MOVILES'] = ["Movil 200", "Movil 201", "Movil 202", "Movil 203", "Movil 204", "Movil 205", "Movil 206"]

res_branch = obtener_consumos_pendientes(estado='TODOS', limite=5)
print(f"Found in Chiriqui: {len(res_branch)}")
for r in res_branch:
    print(f"Movil: {r[1]} | SKU: {r[2]} | Fecha: {r[7]}")
