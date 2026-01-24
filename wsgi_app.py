import sys
import os

# Añadir el directorio actual al path para que Python encuentre los módulos
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Importar la aplicación Flask
# PythonAnywhere busca una variable llamada 'application'
from web_server import app as application

if __name__ == "__main__":
    application.run()
