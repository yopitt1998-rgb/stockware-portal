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
print(f"[SEARCH] Buscando .env en: {dotenv_path}")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print("[OK] .env cargado exitosamente")
else:
    print(f"[WARNING] Archivo .env no encontrado en: {dotenv_path}")

DATABASE_NAME = os.path.join(application_path, "inventario_sqlite.db")

# CONFIGURACIÓN DE DB SEGÚN ENTORNO
DB_TYPE = "MYSQL" # Sincronizado con la Web (TiDB/Render)
# DB_TYPE = "SQLITE" # Local (Desconectado)

# Parámetros MySQL (Para la Nube)
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DATABASE_OVERRIDE", os.getenv("MYSQL_DATABASE"))
MYSQL_DB_SANTIAGO = os.getenv("MYSQL_DATABASE_SANTIAGO") # Nuevo: DB para Santiago
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

# Branch Name for UI title
BRANCH_NAME = os.getenv("CURRENT_BRANCH_NAME", "")


MOVILES_DISPONIBLES = ["Movil 200", "Movil 201", "Movil 202", "Movil 203", "Movil 204", "Movil 205"]
MOVILES_SANTIAGO = ["Movil 206", "Movil 207", "Movil 208", "Movil 209", "Movil 210"]
ALL_MOVILES = MOVILES_DISPONIBLES + MOVILES_SANTIAGO

# DETALLES DE MÓVILES (Fallback para Cloud cuando no hay tabla 'moviles')
# Formato: "Nombre Movil": {"conductor": "Nombre", "ayudante": "Nombre", "patente": "Patente"}
MOVILES_DETAILS_FALLBACK = {
    "Movil 200": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 201": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 202": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 203": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 204": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 205": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 206": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 207": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 208": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 209": {"conductor": "", "ayudante": "", "patente": ""},
    "Movil 210": {"conductor": "", "ayudante": "", "patente": ""}
}
UBICACION_DESCARTE = "DESCARTE"
TIPO_MOVIMIENTO_DESCARTE = "DESCARTE" 
TIPOS_CONSUMO = ['SALIDA', 'CONSUMO_MOVIL', 'DESCARTE']
TIPOS_ABASTO = ['ENTRADA', 'ABASTO']
TIPOS_MOVIMIENTO = ['ENTRADA', 'ABASTO', 'SALIDA_MOVIL', 'RETORNO_MOVIL', 'CONSUMO_MOVIL', 'DESCARTE', 'SALIDA', 'TRASLADO', 'PRESTAMO_SANTIAGO']

PAQUETES_MATERIALES = {
    "PAQUETE A": [
        ("1-4-61", 5),      # PLACAS_F_O
        ("1-8-40", 60),     # FAJILLA_8
        ("2-5-02", 30),     # GRAPAS
        ("2-7-07", 30),     # CALCAMONIA
        ("2-7-11", 7),      # COLILLA
        ("4-2-41", 7),      # TOALLAS
        ("4-3-18", 16),     # CONEC_MECA
        ("4-3-42", 60),     # TENSOR_FO
        ("U4-4-633", 1),    # HG8247W5 (con serial)
        ("4-4-644", 1),     # ONT HUAWEI EchoLife EG8145V5 (con serial)
        ("4-4-654", 1),     # O_EG8041X6 (con serial)
        ("4-4-656", 6),     # O_EG8041X6 (con serial)
        ("4-4-646", 2),     # R_K562E_10 (con serial)
        ("4-4-647", 2),     # R_AS5113 (con serial)
        ("8-1-902", 2),     # A_W541_2.4 (con serial)
        ("8-1-903", 2),     # A_W541_5.8 (con serial)
        ("8-1-904", 8)      # A_W531_WIFI (con serial)
    ],
    "PAQUETE B": [
        ("1-4-61", 5),      # PLACAS_F_O
        ("1-8-40", 60),     # FAJILLA_8
        ("2-5-02", 30),     # GRAPAS
        ("2-7-07", 30),     # CALCAMONIA
        ("2-7-11", 7),      # COLILLA
        ("4-2-41", 7),      # TOALLAS
        ("4-3-18", 16),     # CONEC_MECA
        ("4-3-42", 60),     # TENSOR_FO
        ("U4-4-633", 1),    # HG8247W5 (con serial)
        ("4-4-644", 1),     # ONT HUAWEI EchoLife EG8145V5 (con serial)
        ("4-4-654", 1),     # O_EG8041X6 (con serial)
        ("4-4-656", 6),     # O_EG8041X6 (con serial)
        ("4-4-646", 2),     # R_K562E_10 (con serial)
        ("4-4-647", 2),     # R_AS5113 (con serial)
        ("8-1-902", 2),     # A_W541_2.4 (con serial)
        ("8-1-903", 2),     # A_W541_5.8 (con serial)
        ("8-1-904", 8)      # A_W531_WIFI (con serial)
    ]
}

# Materiales que se comparten entre paquetes (ej: fibra, cables bulk)
# No se dividen, sino que muestran el total disponible en el móvil en todos los paquetes.
MATERIALES_COMPARTIDOS = [
    "5-2-443",  # MOLDU (Moldura)
    "2-5-03",   # G_C_PARED6 (Clip de pared)
    "10-1-04",  # CONEC_RJ45 (Conectores)
    "7-1-171"   # C_UTP_CAT6 (Cable UTP)
]

# Default initial package for logic compatibility
PAQUETE_INSTALACION = dict(PAQUETES_MATERIALES["PAQUETE A"])

# Global State Variables (moved from main)
ULTIMO_LLENADO_SALIDA = {}
PRESTAMOS_SANTIAGO = []

# LISTA CORREGIDA - SIN DUPLICADOS
# LISTA CORREGIDA - NOMBRES DESDE EXCEL
# LISTA CORREGIDA - NOMBRES EXACTOS SEGÚN REPORT EXCEL

# List of SKUs that have physical barcodes on the device
PRODUCTOS_CON_CODIGO_BARRA = [
    "U4-4-633", "4-4-644", "4-4-654", "4-4-656", 
    "4-4-646", "4-4-647", "8-1-902", "8-1-903", "8-1-904"
]

PRODUCTOS_INICIALES = [
    # (Nombre Excel/Formulario, SKU, Secuencia)
    ("FIBUNHILO", "1-2-16", "001"),          # FIBRA OPTICA SM 1 HILOS
    ("C_UTP_CAT6", "7-1-171", "002"),        # CABLE COBRE UTP CM
    ("CONEC_RJ45", "10-1-04", "003"),        # CONECTOR SENCILLO MACHO RJ-45
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
    ("O_EG8145V5", "4-4-644", "018"),        # ONT HUAWEI EchoLife EG8145V5
    ("O_EG8041X6", "4-4-654", "019"),        # ONT HUAWEI EchoLife EGX6
    ("O_EG8041X6", "4-4-656", "020"),        # Huawei OptiXstar EG8041X6-10 (Nota: Mismo nombre corto en imagen)
    ("R_K562E_10", "4-4-646", "021"),        # Huawei OptiXstar K562e-10
    ("WIFI_NET", "4-4-647", "022"),          # Broadband Network Terminal
    ("T_PLAYPRO", "8-1-902", "024"),         # STB OTT RETAIL Z11B
    ("T_PLAY", "8-1-903", "025"),            # STBs OTT AOSP DUAL BAND Z4
    ("E_T_PLAY", "8-1-904", "023"),          # Dongle OTT Retail Z11D
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

# =================================================================
# DYNAMIC BRANCH CONTEXT
# =================================================================
CURRENT_CONTEXT = {
    'BRANCH': 'CHIRIQUI', # Default
    'DB_NAME': DATABASE_NAME,
    'MYSQL_DB': MYSQL_DB,
    'MOVILES': MOVILES_DISPONIBLES
}

def set_branch_context(branch_code):
    """
    Configura el contexto global según la sucursal seleccionada.
    """
    global CURRENT_CONTEXT
    branch_code = branch_code.upper()
    
    print(f"[{branch_code}] Cambiando Contexto de Sucursal...")
    
    if branch_code == 'SANTIAGO':
        CURRENT_CONTEXT['BRANCH'] = 'SANTIAGO'
        CURRENT_CONTEXT['MOVILES'] = MOVILES_SANTIAGO
        
        # Switch DB
        if DB_TYPE == 'MYSQL':
            if MYSQL_DB_SANTIAGO:
                CURRENT_CONTEXT['MYSQL_DB'] = MYSQL_DB_SANTIAGO
                print(f" -> DB MySQL cambiada a: {MYSQL_DB_SANTIAGO}")
        else:
            # Local SQLite: Separamos Santiago a otro archivo? 
            # Si el usuario quiere Separation TOTAL, debería ser otro archivo.
            # Por ahora, usamos el mismo archivo pero filtramos datos, 
            # O podemos usar 'inventario_santiago.db'
            santiago_db = os.path.join(application_path, "inventario_santiago.db")
            CURRENT_CONTEXT['DB_NAME'] = santiago_db
            print(f" -> DB SQLite cambiada a: {santiago_db}")
            
    else: # CHIRIQUI (Default)
        CURRENT_CONTEXT['BRANCH'] = 'CHIRIQUI'
        CURRENT_CONTEXT['MOVILES'] = MOVILES_DISPONIBLES
        CURRENT_CONTEXT['DB_NAME'] = DATABASE_NAME
        CURRENT_CONTEXT['MYSQL_DB'] = MYSQL_DB
        print(f" -> Contexto CHIRIQUI activo.")

def get_current_db_name():
    if DB_TYPE == 'MYSQL':
        return CURRENT_CONTEXT.get('MYSQL_DB', MYSQL_DB)
    return CURRENT_CONTEXT.get('DB_NAME', DATABASE_NAME)

# =================================================================
# PERSISTENCIA DE CONFIGURACIÓN (NUEVO)
# =================================================================
import json

PREFS_FILE = os.path.join(application_path, "user_preferences.json")

def load_branch_preference():
    """Carga la sucursal preferida del usuario desde JSON."""
    try:
        if os.path.exists(PREFS_FILE):
            with open(PREFS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('branch', 'CHIRIQUI')
    except Exception as e:
        print(f"Error cargando preferencias: {e}")
    return 'CHIRIQUI'

def save_branch_preference(branch_code):
    """Guarda la sucursal preferida en JSON."""
    try:
        data = {'branch': branch_code}
        with open(PREFS_FILE, 'w') as f:
            json.dump(data, f)
        print(f"Preferencia de sucursal guardada: {branch_code}")
    except Exception as e:
        print(f"Error guardando preferencias: {e}")

# Modificar para cargar preferencia si no se pasa argumento explícito (no cambios aqui, logica en app)


