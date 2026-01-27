from flask import Flask, render_template, request, jsonify
import socket
import os
from database import (
    registrar_consumo_pendiente, 
    obtener_nombres_moviles, 
    obtener_todos_los_skus_para_movimiento,
    obtener_detalles_moviles
)
from config import DB_TYPE
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

    from database import get_db_connection, run_query
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        exitos = 0
        materiales = data.get('materiales', [])
        
        for item in materiales:
            # Ejecutamos el insert directamente aquí para usar la misma conexión/transacción
            run_query(cursor, """
                INSERT INTO consumos_pendientes 
                (movil, sku, cantidad, tecnico_nombre, ayudante_nombre, ticket, fecha, colilla, num_contrato)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['movil'],
                item['sku'],
                item['cantidad'],
                data['tecnico'],
                data.get('ayudante', ''),
                data['contrato'], # ticket
                data['fecha'],
                data['colilla'],
                data['contrato']  # num_contrato
            ))
            exitos += 1
        
        conn.commit()
        return jsonify({"exito": True, "mensaje": f"Reporte enviado con éxito ({exitos} materiales)"})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"exito": False, "mensaje": f"Error de base de datos: {str(e)}"})
    finally:
        if conn: conn.close()

def start_server():
    # Detectar puerto (Render asigna uno dinámicamente)
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Portal Web iniciado en puerto: {port}")
    app.run(host='0.0.0.0', port=port)

def get_local_ip():
    """Obtiene la IP local de la máquina"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def start_server_thread():
    """Inicia el servidor Flask en un thread separado y retorna la IP local"""
    local_ip = get_local_ip()
    
    def run_server():
        try:
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        except Exception as e:
            print(f"Error al iniciar servidor web: {e}")
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    return local_ip

if __name__ == "__main__":
    start_server()
