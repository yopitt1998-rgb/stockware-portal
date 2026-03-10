
import os
import sys

# Forzar sucursal Chiriquí
os.environ['FORCE_BRANCH'] = 'CHIRIQUI'
os.environ['SANTIAGO_DIRECT_MODE'] = '0'

# Importar y ejecutar la aplicación principal
from app_inventario import main

if __name__ == "__main__":
    main()
