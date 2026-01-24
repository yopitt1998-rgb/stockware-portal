import os
import datetime
from tkinter import messagebox

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def generar_vale_despacho_pdf(movil, productos, config, filename):
    """
    Genera un Vale de Despacho profesional en PDF (Punto 2).
    productos: Lista de tuplas (SKU, Nombre, Cantidad)
    config: Diccionario con datos de la empresa (Nombre, RUT, logo_path, etc.)
    """
    if not REPORTLAB_AVAILABLE:
        return False, "La librería 'reportlab' no está instalada. Ejecute 'pip install reportlab' para habilitar esta función."

    try:
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # --- CABECERA ---
        header_data = []
        
        # Logo side
        logo_path = config.get('logo_path')
        if logo_path and os.path.exists(logo_path):
            img = Image(logo_path, width=1.5*inch, height=0.6*inch)
            header_data.append([img, ""])
        else:
            header_data.append(["[LOGO]", ""])

        # Company Info side
        company_info = f"<b>{config.get('nombre_empresa', 'Mi Empresa')}</b><br/>"
        company_info += f"RUT: {config.get('rut', 'N/A')}<br/>"
        company_info += f"{config.get('direccion', '')}"
        
        p_info = Paragraph(company_info, styles['Normal'])
        header_data[0][1] = p_info

        header_table = Table(header_data, colWidths=[2.5*inch, 4*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 20))

        # --- TITULO DEL DOCUMENTO ---
        title = Paragraph("<center><h1>VALE DE DESPACHO DE MATERIALES</h1></center>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 10))

        # --- INFORMACION DEL MOVIMIENTO ---
        info_text = f"<b>DESTINO / MÓVIL:</b> {movil}<br/>"
        info_text += f"<b>FECHA:</b> {datetime.date.today().strftime('%d/%m/%Y')}<br/>"
        info_text += f"<b>DOCUMENTO:</b> VD-{datetime.datetime.now().strftime('%y%m%d%H%M')}"
        
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 20))

        # --- TABLA DE PRODUCTOS ---
        table_data = [["SKU", "DESCRIPCIÓN DEL PRODUCTO", "CANTIDAD"]]
        for sku, nombre, cantidad in productos:
            table_data.append([sku, nombre, str(cantidad)])

        t = Table(table_data, colWidths=[1.2*inch, 4*inch, 1.3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (1,1), (1,-1), 'LEFT'), # Descripciones a la izquierda
        ]))
        elements.append(t)
        elements.append(Spacer(1, 50))

        # --- ESPACIO PARA FIRMAS ---
        firma_data = [
            ["_________________________", "_________________________"],
            ["ENTREGADO POR", "RECIBIDO POR (CONDUCTOR)"],
            ["", f"Nombre: _________________"]
        ]
        
        firma_table = Table(firma_data, colWidths=[3*inch, 3*inch])
        firma_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
        ]))
        elements.append(firma_table)

        # Generar archivo
        doc.build(elements)
        return True, f"Vale de despacho generado exitosamente en:\n{filename}"

    except Exception as e:
        return False, f"Error al generar PDF: {str(e)}"
