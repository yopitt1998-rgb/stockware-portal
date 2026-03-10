
import re

file_path = "database.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Patrón redundante inyectado por fix_cursors.py
redundant_pattern = re.compile(
    r"( {4,})if DB_TYPE == 'MYSQL':\n"
    r"\1    cursor = conn.cursor\(buffered=True\)\n"
    r"\1else:\n"
    r"\1    if DB_TYPE == 'MYSQL':\n"
    r"\1        cursor = conn.cursor\(buffered=True\)\n"
    r"\1    else:\n"
    r"\1        cursor = conn.cursor\(\)\n",
    re.MULTILINE
)

# Reemplazar por la versión simplificada
fixed_content = redundant_pattern.sub(
    r"\1if DB_TYPE == 'MYSQL':\n"
    r"\1    cursor = conn.cursor(buffered=True)\n"
    r"\1else:\n"
    r"\1    cursor = conn.cursor()\n",
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("Limpieza de redundancias completada en database.py")
