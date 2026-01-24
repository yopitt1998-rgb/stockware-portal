from flask import Flask, render_template, request, jsonify
import socket
from database import (
    registrar_consumo_pendiente, 
    obtener_nombres_moviles, 
    obtener_todos_los_skus_para_movimiento,
    obtener_detalles_moviles
)
from datetime import date
import threading
import json

app = Flask(__name__) # Regresamos al estándar (busca en carpeta 'templates')

@app.route('/')
def index():
    status = "OK"
    engine = DB_TYPE
    error_detail = ""
    count_m = 0
    count_p = 0
    
    try:
        moviles = obtener_nombres_moviles()
        productos = obtener_todos_los_skus_para_movimiento()
        details_moviles = obtener_detalles_moviles()
        
        count_m = len(moviles)
        count_p = len(productos)
        
        if count_m == 0 and count_p == 0:
            status = "SISTEMA VACÍO"
            error_detail = "Se conectó a la base de datos, pero no encontró productos ni móviles."
            
    except Exception as e:
        status = "ERROR DE CONEXIÓN"
        error_detail = str(e)
        moviles = []
        productos = []
        details_moviles = {}

    try:
        # Intentar renderizar la plantilla normal
        return render_template('index.html', 
                                 hoy=date.today().isoformat(), 
                                 moviles=moviles, 
                                 productos=productos,
                                 details_moviles=json.dumps(details_moviles),
                                 db_status=status,
                                 db_engine=engine,
                                 error_detail=error_detail,
                                 count_m=count_m,
                                 count_p=count_p)
    except Exception as template_err:
        # Fallback si falla la plantilla (por si no encuentran el archivo index.html)
        return f"<h1>⚠️ Error de Servidor</h1><p>No se pudo cargar el diseño (index.html). Verifica que el archivo esté dentro de una carpeta llamada 'templates' en GitHub.</p><p>Detalle: {str(template_err)}</p>"

@app.route('/debug')
def debug():
    import os
    from config import MYSQL_HOST, MYSQL_USER, DB_TYPE
    from database import get_db_connection
    
    test_conn = "SIN PROBAR"
    test_error = ""
    
    try:
        conn = get_db_connection()
        conn.close()
        test_conn = "ÉXITO"
    except Exception as e:
        test_conn = "FALLO"
        test_error = str(e)
    
    info = {
        "MODO_ACTUAL": DB_TYPE,
        "MYSQL_HOST": MYSQL_HOST,
        "MYSQL_USER": MYSQL_USER,
        "CONEXION_REAL": test_conn,
        "ERROR_CONEXION": test_error,
        "ENV_EXISTS": os.path.exists('.env'),
        "DIRECTORIO": os.getcwd()
    }
    return jsonify(info)

@app.route('/registrar_bulk', methods=['POST'])
def registrar_bulk():
    data = request.json
    if not data:
        return jsonify({"exito": False, "mensaje": "Sin datos"})

    try:
        exitos = 0
        errores = 0
        
        for item in data.get('materiales', []):
            ok, msg = registrar_consumo_pendiente(
                movil=data['movil'],
                sku=item['sku'],
                cantidad=item['cantidad'],
                tecnico=data['tecnico'],
                ticket=data['contrato'],
                fecha=data['fecha'],
                colilla=data['colilla'],
                contrato=data['contrato'],
                ayudante=data['ayudante']
            )
            if ok: exitos += 1
            else: errores += 1
        
        return jsonify({"exito": True, "mensaje": f"Procesados: {exitos} exitos, {errores} errores"})

    except Exception as e:
        return jsonify({"exito": False, "mensaje": str(e)})

def start_server():
    # Detectar IP local
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    
    # Iniciar Flask en hilo separado
    port = 5000
    print(f"🌐 Portal Web iniciado en http://{IP}:{port}")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    start_server()
