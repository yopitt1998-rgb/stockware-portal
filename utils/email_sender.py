import os
import json
import urllib.request
from utils.logger import get_logger

logger = get_logger('email_sender')

def send_consumption_email_async(data, materiales_detalles):
    """
    Envía un correo mediante la API HTTP de Resend.
    Es compatible con entornos donde los puertos SMTP (587, 465) están bloqueados (como Render Free).
    
    data: dict con información del consumo (movil, tecnico, contrato, etc.)
    materiales_detalles: list de dicts con información de cada material
    """
    # Leer API Key desde variables de entorno
    resend_api_key = os.environ.get('RESEND_API_KEY')
    
    # Destinatario desde variable de entorno o fallback
    receiver_email = os.environ.get('NOTIFICATION_EMAIL', 'bodega.eesoluciones@gmail.com')
    
    if not resend_api_key:
        logger.warning("RESEND_API_KEY no configurada. No se enviará el correo de notificación.")
        return

    try:
        subject = f"NUEVO CONSUMO: Móvil {data.get('movil')} - Ticket: {data.get('contrato')}"

        # Construir tabla HTML
        html_rows = ""
        for item in materiales_detalles:
            sku = item.get('sku', '')
            cantidad = item.get('cantidad', 1)
            seriales = item.get('seriales', [])
            
            # Nombre del material o SKU si no hay nombre
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

        # Estructurar la solicitud HTTP a la API de Resend
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "StockWare-App/1.0"
        }
        
        # Resend requiere enviar desde un dominio verificado, o desde onboarding@resend.dev (para pruebas al mismo correo del owner)
        from_email = "StockWare <onboarding@resend.dev>"
        
        payload = {
            "from": from_email,
            "to": [receiver_email],
            "subject": subject,
            "html": html
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        # Realizar la llamada HTTP a Resend
        with urllib.request.urlopen(req, timeout=10) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            logger.info(f"Correo enviado exitosamente vía Resend. ID: {response_data.get('id')} para {receiver_email}")

    except urllib.error.HTTPError as http_err:
        import urllib.error
        error_body = http_err.read().decode("utf-8")
        logger.error(f"Error HTTP de Resend API ({http_err.code}): {error_body}")
        raise
    except Exception as e:
        logger.error(f"Error al enviar correo de notificación mediante Resend API: {e}")
        raise
