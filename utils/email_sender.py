import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.logger import get_logger

logger = get_logger('email_sender')

def send_consumption_email_async(data, materiales_detalles):
    """
    Envía un correo de forma asíncrona (en un hilo separado) para no bloquear
    la respuesta de la API del portal web.
    
    data: dict con información del consumo (movil, tecnico, contrato, etc.)
    materiales_detalles: list de dicts con información de cada material
    """
    # Leer configuración desde variables de entorno
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    
    # Destinatario por defecto o desde variable de entorno
    receiver_email = os.environ.get('NOTIFICATION_EMAIL', 'bodega.eesoluciones@gmail.com')
    
    if not smtp_user or not smtp_password:
        logger.warning("Credenciales SMTP no configuradas. No se enviará el correo de notificación.")
        return

    def send_email_thread():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"NUEVO CONSUMO: Móvil {data.get('movil')} - Ticket: {data.get('contrato')}"
            msg["From"] = smtp_user
            msg["To"] = receiver_email

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

            part = MIMEText(html, "html")
            msg.attach(part)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, receiver_email, msg.as_string())
                
            logger.info(f"Correo de consumo enviado a {receiver_email} para ticket {data.get('contrato')}.")

        except Exception as e:
            logger.error(f"Error al enviar correo de notificación: {e}")

    # Iniciar hilo secundario
    t = threading.Thread(target=send_email_thread, daemon=True)
    t.start()
