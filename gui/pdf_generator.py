from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import datetime
import os

def generar_vale_despacho(datos_despacho, materiales, output_path):
    """
    Genera un PDF profesional de Vale de Despacho.
    datos_despacho: dict con {'folio', 'fecha', 'movil', 'tecnico', 'usuario'}
    materiales: lista de tuplas [(sku, nombre, cantidad), ...]
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilo personalizado
    style_title = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'],
        fontSize=18, alignment=1, spaceAfter=20, textColor=colors.HexColor('#2c3e50')
    )
    
    # 1. ENCABEZADO
    elements.append(Paragraph("VALE DE DESPACHO DE MATERIALES", style_title))
    elements.append(Spacer(1, 12))
    
    # 2. INFORMACIÓN GENERAL (TABLA)
    info_data = [
        [Paragraph(f"<b>Folio:</b> {datos_despacho.get('folio', 'N/A')}"), Paragraph(f"<b>Fecha:</b> {datos_despacho.get('fecha', datetime.now().strftime('%Y-%m-%d %H:%M'))}")],
        [Paragraph(f"<b>Móvil:</b> {datos_despacho.get('movil', 'N/A')}"), Paragraph(f"<b>Técnico:</b> {datos_despacho.get('tecnico', 'N/A')}")],
        [Paragraph(f"<b>Emitido por:</b> {datos_despacho.get('usuario', 'Admin')}"), ""]
    ]
    
    info_table = Table(info_data, colWidths=[250, 250])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # 3. DETALLE DE MATERIALES
    table_data = [["SKU", "DESCRIPCIÓN DEL MATERIAL", "CANTIDAD"]]
    for sku, nombre, cantidad in materiales:
        table_data.append([sku, nombre, str(cantidad)])
    
    mat_table = Table(table_data, colWidths=[100, 300, 80])
    mat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'LEFT'), # Alineación izquierda para nombre
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWHEIGHTS', (0,0), (-1,-1), 25),
    ]))
    elements.append(mat_table)
    elements.append(Spacer(1, 100)) # Espacio para firmas
    
    # 4. AREA DE FIRMAS
    firma_data = [
        ["________________________", "________________________"],
        ["FIRMA RECEPTOR (TÉCNICO)", "FIRMA ENTREGA (BODEGA)"]
    ]
    firma_table = Table(firma_data, colWidths=[250, 250])
    firma_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    elements.append(firma_table)
    
    # 5. PIE DE PÁGINA
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("<i>Documento generado automáticamente por StockWare Cloud Inventario.</i>", styles['Italic']))
    
    # GENERAR
    try:
        doc.build(elements)
        return True, output_path
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    # Test
    test_datos = {'folio': '0001', 'movil': 'Movil 201', 'tecnico': 'Juan Perez', 'usuario': 'Admin'}
    test_mats = [('1-2-16', 'FIBRA OPTICA SM', 100), ('4-4-644', 'ONT HUAWEI EG8145V5', 2)]
    res, path = generar_vale_despacho(test_datos, test_mats, "test_vale.pdf")
    print(f"Generated: {res}, Path: {path}")
