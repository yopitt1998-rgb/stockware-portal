"""
Script para limpiar los bloques de imports genéricos en data_layer/.
Cada módulo sólo necesita lo que realmente usa.
"""
import re
import os

# ---- Cabecera limpia por módulo ----
HEADERS = {
    "core.py": """\
import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
import shutil
from datetime import datetime, date, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)
""",
    "inventory.py": """\
import sqlite3
import os
from datetime import datetime, date

from utils.logger import get_logger

logger = get_logger(__name__)
""",
    "movements.py": """\
import sqlite3
import os
from datetime import datetime, date

from utils.logger import get_logger

logger = get_logger(__name__)
""",
    "mobile.py": """\
import os
from datetime import datetime, date, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)
""",
    "reminders.py": """\
import os
from datetime import datetime, date

from utils.logger import get_logger

logger = get_logger(__name__)
""",
}

# Estos son los imports adicionales que cada módulo necesita DESPUÉS de su logger
ADDITIONAL_IMPORTS = {
    "core.py": """\
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session

try:
    from tkinter import messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False
""",
    "inventory.py": """\
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session
from data_layer.core import run_query, safe_messagebox
""",
    "movements.py": """\
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session
from data_layer.core import run_query, safe_messagebox
from data_layer.inventory import registrar_series_bulk, obtener_info_serial
""",
    "mobile.py": """\
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session
from data_layer.core import run_query, safe_messagebox
from data_layer.inventory import limpiar_productos_duplicados
""",
    "reminders.py": """\
from config import DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT
from utils.db_connector import get_db_connection, close_connection, db_session
from data_layer.core import run_query, safe_messagebox
""",
}

# Bloque de imports a reemplazar en cada archivo
OLD_BLOCK = """\
import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
import csv
import shutil
from datetime import datetime, date, timedelta"""


def clean_module(filepath, filename):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Construir nuevo bloque de inicio
    new_header = HEADERS[filename]
    add_imports = ADDITIONAL_IMPORTS[filename]

    # El bloque viejo termina en la línea 'from data_layer.core import run_query...'
    # o en 'from data_layer.inventory import *'
    # Encontrar donde termina el bloque de imports
    old_import_marker = "from data_layer.inventory import *"
    old_import_marker2 = "from data_layer.core import run_query, safe_messagebox\nfrom data_layer.inventory import *"

    # Normalizar el archivo: eliminar el bloque de imports genérico y las líneas previas
    # Buscamos el primer def o función para inyectar antes
    lines = content.split('\n')

    # Encontrar la última línea de imports
    last_import_line = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from ') or stripped == '':
            if stripped:  # no blank
                last_import_line = i
        elif stripped.startswith('def ') or stripped.startswith('class '):
            break

    # Extraer funciones (todo desde el primer 'def ')
    first_def_line = None
    for i, line in enumerate(lines):
        if line.strip().startswith('def ') or line.strip().startswith('class '):
            first_def_line = i
            break

    if first_def_line is None:
        print(f"  No se encontró def en {filename}, omitiendo.")
        return

    funcs_content = '\n'.join(lines[first_def_line:])

    new_content = new_header + '\n' + add_imports + '\n' + funcs_content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✅ {filename} limpiado")


if __name__ == "__main__":
    data_layer_dir = "data_layer"
    for fname in HEADERS.keys():
        fpath = os.path.join(data_layer_dir, fname)
        if os.path.exists(fpath):
            print(f"Procesando {fname}...")
            clean_module(fpath, fname)
        else:
            print(f"  ⚠️ No encontrado: {fpath}")
    print("\nLimpieza completada.")
