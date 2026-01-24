import os
import sys
from dotenv import load_dotenv

# 1. CONFIGURACIÓN DE CONEXIÓN Y DATOS INICIALES

# Detectar ruta base para archivos locales (.env, .db)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Cargar variables de entorno desde la ruta absoluta del .env
dotenv_path = os.path.join(application_path, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print(f"⚠️ Archivo .env no encontrado en: {dotenv_path}")

DATABASE_NAME = os.path.join(application_path, "inventario_sqlite.db")

# CONFIGURACIÓN DE DB SEGÚN ENTORNO
DB_TYPE = os.getenv("DB_TYPE", "SQLITE").upper() # 'SQLITE' o 'MYSQL'

# Parámetros MySQL (Para la Nube)
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

MOVILES_DISPONIBLES = ["Movil 200", "Movil 201", "Movil 202", "Movil 203", "Movil 204", "Movil 205"]
UBICACION_DESCARTE = "DESCARTE"
TIPO_MOVIMIENTO_DESCARTE = "DESCARTE" 
TIPOS_CONSUMO = ['SALIDA', 'CONSUMO_MOVIL', 'DESCARTE']
TIPOS_ABASTO = ['ENTRADA', 'ABASTO']
TIPOS_MOVIMIENTO = ['ENTRADA', 'ABASTO', 'SALIDA_MOVIL', 'RETORNO_MOVIL', 'CONSUMO_MOVIL', 'DESCARTE', 'SALIDA']

PAQUETES_MATERIALES = {
    "PAQUETE A": [
        ("10-1-04", 10),  # CONECTOR SENCILLO MACHO RJ-45
        ("1-2-16", 20),   # FIBRA OPTICA SM 1 HILOS
        ("4-3-18", 5)     # CONECTORES F.O SM SC-APC
    ],
    "PAQUETE B": [
        ("2-5-02", 15),   # GRAPA "Q" SPAN
        ("1-8-41", 3),    # TAPE ELECTRIC 3 M
        ("4-4-644", 1)    # ONT HUAWEI EchoLife EG8145V5
    ],
    "CARRO": [
        ("7-1-171", 30),  # CABLE COBRE UTP CM
        ("5-2-443", 2),   # Moldura eléctrica
        ("4-4-654", 1)    # Huawei OptiXstar EG8145X6-10
    ]
}

# Global State Variables (moved from main)
ULTIMO_LLENADO_SALIDA = {}
PRESTAMOS_SANTIAGO = []

# LISTA CORREGIDA - SIN DUPLICADOS
# LISTA CORREGIDA - NOMBRES DESDE EXCEL
# LISTA CORREGIDA - NOMBRES EXACTOS SEGÚN REPORT EXCEL
PRODUCTOS_INICIALES = [
    # (Nombre Excel, SKU, Secuencia)
    ("FIBUNHILO", "1-2-16", "001"),          # FIBRA OPTICA SM 1 HILOS
    ("CABLE_RJ45", "7-1-171", "002"),        # CABLE COBRE UTP CM
    ("C_UTP_CAT6", "10-1-04", "003"),        # CONECTOR SENCILLO MACHO RJ-45
    ("GRAPA P/CABLE TEL#6", "5-2-155", "004"), # Sin mapping en imagen, mantengo nombre sistema
    ("MOLDU", "5-2-443", "005"),             # Moldura
    ("PLACAS_F_O", "1-4-61", "006"),         # PLACA PEQ PRECAUCION FIBRA
    ("FAJILLA_8", "1-8-40", "007"),          # TIE 8" FAJILLA
    ("TAPE", "1-8-41", "008"),               # TAPE ELECTRIC
    ("GRAPAS", "2-5-02", "009"),             # GRAPA "Q" SPAN
    ("G_C_PARED6", "2-5-03", "010"),         # CLIP, 7MM CABLE BLANCO
    ("CALCAMONIA", "2-7-07", "011"),         # STICKER PRECAUCION
    ("COLILLA", "2-7-11", "012"),            # COLILLAS BLANCAS
    ("TOALLAS", "4-2-41", "013"),            # TOALLAS LIBRE PELO
    ("CONEC_MECA", "4-3-18", "014"),         # CONECTORES F.O SM SC-APC
    ("TENSOR_FO", "4-3-42", "015"),          # TENSOR P/ FIBRA DROP
    ("HG8247W5", "U4-4-633", "016"),         # ONT HUAWEI ECHOLIFE HG8247W5
    ("ONT HUAWEI OptiXstar HG8145X6", "U4-4-634", "017"), # Sin mapping
    ("O_EG8145V5", "4-4-644", "018"),        # ONT HUAWEI EchoLife EG8145V5
    ("ONT HUAWEI EchoLife EGX6", "4-4-654", "019"),     # Sin mapping claro en imagen para este SKU exacto (pero hay O_EG8041X6 abajo)
    ("O_EG8041X6", "4-4-656", "020"),        # Huawei OptiXstar EG8041X6-10
    ("R_K562E_10", "4-4-646", "021"),        # Huawei OptiXstar K562e-10
    ("WIFI_NET", "4-4-647", "022"),          # Broadband Network Terminal
    ("Dongle OTT Retail Z11D", "8-1-904", "023"), # Sin mapping
    ("T_PLAYPRO", "8-1-902", "024"),         # STB OTT RETAIL Z11B
    ("T_PLAY", "8-1-903", "025"),            # STBs OTT AOSP DUAL BAND Z4
]

# UI Colors
COLORS = {
    'primary': '#2c3e50',
    'secondary': '#3498db',
    'accent': '#e74c3c',
    'success': '#27ae60',
    'warning': '#f39c12',
    'info': '#17a2b8',
    'light_bg': '#ecf0f1',
    'dark_text': '#2c3e50',
    'light_text': '#ecf0f1'
}
