
import os

file_path = "database.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_next = False

for i in range(len(lines)):
    line = lines[i]
    if "cursor = conn.cursor()" in line and "if DB_TYPE == 'MYSQL':" not in lines[i-1 if i > 0 else 0]:
        indent = line[:line.find("cursor")]
        new_lines.append(f"{indent}if DB_TYPE == 'MYSQL':\n")
        new_lines.append(f"{indent}    cursor = conn.cursor(buffered=True)\n")
        new_lines.append(f"{indent}else:\n")
        new_lines.append(f"{indent}    cursor = conn.cursor()\n")
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Reemplazo masivo completado en database.py")
