
import os
import sys

# Agregar path
sys.path.append(os.getcwd())

import database
from config import MOVILES_SANTIAGO
from utils.db_connector import db_session

def register_santiago_mobiles():
    print("Registrando móviles de Santiago en la BD...")
    with db_session() as (conn, cursor):
        for m in MOVILES_SANTIAGO:
            try:
                # El cursor ya está disponible si usamos db_session()
                # O si db_session retorna la conexión, pedir el cursor.
                # En este proyecto, db_session es un context manager que retorna el cursor.
                sql = "INSERT INTO moviles (nombre, activo) VALUES (%s, 1) ON DUPLICATE KEY UPDATE activo=1"
                cursor.execute(sql, (m,))
                print(f"✅ {m} procesado.")
            except Exception as e:
                print(f"❌ Error con {m}: {e}")
    print("Finalizado.")

if __name__ == "__main__":
    register_santiago_mobiles()
