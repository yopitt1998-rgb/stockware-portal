
import os

filepath = 'c:\\Users\\johni\\Documents\\GestorInventario_MySQL\\database.py'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if 'def obtener_todos_los_skus_para_movimiento' in line:
                print(f"Found at line {i+1}: {line.strip()}")
                # Print next few lines
                for j in range(1, 20):
                    if i+j < len(lines):
                        print(f"{i+1+j}: {lines[i+j].strip()}")
                break
except Exception as e:
    print(f"Error: {e}")
