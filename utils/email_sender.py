import os
import json
import urllib.request
import urllib.error
import threading
import datetime
import traceback
from utils.logger import get_logger

logger = get_logger('email_sender')

# Historial en memoria de los últimos envíos de correo para depuración
EMAIL_LOGS = []

def send_consumption_email_async(data, materiales_detalles):
    """
    Envía un correo mediante la API HTTP de Resend de forma asíncrona en un hilo.
    """
    # Clonar datos para evitar modificaciones concurrentes
    try:
        data_copy = json.loads(json.dumps(data))
        materiales_copy = json.loads(json.dumps(materiales_detalles))
    except Exception:
        data_copy = str(data)
        materiales_copy = str(materiales_detalles)

    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "data": data_copy,
        "materiales": materiales_copy,
        "status": "pending",
        "error": None,
        "error_body": None,
        "traceback": None,
        "response": None
    }
    
    EMAIL_LOGS.append(log_entry)
    if len(EMAIL_LOGS) > 20:
        EMAIL_LOGS.pop(0)

    def send_email_thread():
        # Leer API Key desde variables de entorno
        resend_api_key = os.environ.get('RESEND_API_KEY')
        receiver_email_raw = os.environ.get('NOTIFICATION_EMAIL', 'bodega.eesoluciones@gmail.com')
        
        # Soportar múltiples destinatarios separados por coma
        receiver_emails = [e.strip() for e in receiver_email_raw.split(',') if e.strip()]
        
        if not resend_api_key:
            msg = "RESEND_API_KEY no configurada en variables de entorno. No se enviará el correo de notificación."
            logger.warning(msg)
            log_entry["status"] = "skipped"
            log_entry["error"] = msg
            return
        
        logger.info(f"[EMAIL] Preparando envío a {receiver_emails} vía Resend...")

        try:
            subject = f"NUEVO CONSUMO: Móvil {data.get('movil')} - Ticket: {data.get('contrato')}"

            # Construir tabla HTML
            html_rows = ""
            for item in materiales_detalles:
                sku = item.get('sku', '')
                cantidad = item.get('cantidad', 1)
                seriales = item.get('seriales', [])
                nombre = item.get('nombre', sku)
                detalles = f"Seriales: {', '.join(seriales)}" if seriales else "-"
                
                html_rows += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{sku}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{nombre}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{cantidad}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{detalles}</td>
                </tr>
                """

            html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 5px;">
                        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">Nuevo Consumo Registrado</h2>
                        
                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                            <p><b>Móvil:</b> {data.get('movil')}</p>
                            <p><b>Técnico:</b> {data.get('tecnico')}</p>
                            <p><b>Ticket/Contrato:</b> {data.get('contrato')}</p>
                            <p><b>Colilla:</b> {data.get('colilla', '-')}</p>
                            <p><b>Fecha:</b> {data.get('fecha')}</p>
                        </div>

                        <h3 style="color: #2c3e50;">Materiales Registrados</h3>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                            <thead>
                                <tr style="background-color: #f2f2f2;">
                                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">SKU</th>
                                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Producto</th>
                                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Cantidad</th>
                                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Detalles</th>
                                </tr>
                            </thead>
                            <tbody>
                                {html_rows}
                            </tbody>
                        </table>
                        
                        <p style="margin-top: 30px; font-size: 12px; color: #7f8c8d; border-top: 1px solid #eaeaea; padding-top: 10px;">
                            Este es un mensaje automático de StockWare Web Portal. No responda a este correo.
                        </p>
                    </div>
                </body>
            </html>
            """

            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "StockWare-App/1.0"
            }
            
            payload = {
                "from": "StockWare <onboarding@resend.dev>",
                "to": receiver_emails,
                "subject": subject,
                "html": html
            }

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                logger.info(f"[EMAIL] Correo enviado exitosamente vía Resend. ID: {response_data.get('id')} para {receiver_emails}")
                log_entry["status"] = "success"
                log_entry["response"] = response_data

        except urllib.error.HTTPError as http_err:
            error_body = http_err.read().decode("utf-8")
            logger.error(f"Error HTTP de Resend API ({http_err.code}): {error_body}")
            log_entry["status"] = "failed"
            log_entry["error"] = f"HTTP Error {http_err.code}: {http_err.reason}"
            log_entry["error_body"] = error_body

        except Exception as e:
            logger.error(f"Error al enviar correo de notificación mediante Resend API: {e}")
            log_entry["status"] = "error"
            log_entry["error"] = str(e)
            log_entry["traceback"] = traceback.format_exc()

    # Iniciar en un hilo de fondo
    t = threading.Thread(target=send_email_thread, daemon=True)
    t.start()
