
import os
import sys

# Agregar path
sys.path.append(os.getcwd())

import database
import config

def test_search(term):
    print(f"Probando búsqueda global para: {term}")
    res = database.buscar_equipo_global(term)
    if res:
        print(f"✅ Éxito: {res}")
    else:
        print(f"❌ No se encontró nada o hubo error.")

if __name__ == "__main__":
    test_search("GZ25040112723608")
