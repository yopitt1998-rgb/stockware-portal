import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import threading
import os

# Pillow y Pytesseract (opcionales al inicio para evitar crash si no están instalados)
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

import pandas as pd

from gui.styles import Styles
from gui.utils import darken_color
from data_layer.warehouse_audit import (
    obtener_o_crear_sesion_auditoria,
    obtener_items_auditoria,
    guardar_cambio_item,
    registrar_abasto_ocr,
    eliminar_abasto_registro,
    registrar_billing_excel,
    limpiar_billing_sesion
)
from config import CURRENT_CONTEXT, PRODUCTOS_INICIALES
from utils.logger import get_logger

logger = get_logger(__name__)

class WarehouseAuditTab:
    def __init__(self, parent, root_app):
        self.parent = parent
        self.root_app = root_app
        self.sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
        self.id_sesion = None
        
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        # Frame Principal
        self.main_frame = ttk.Frame(self.parent, style='Modern.TFrame')
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Header con info y botones
        header = ttk.Frame(self.main_frame, style='Modern.TFrame')
        header.pack(fill='x', pady=(0, 20))

        title_lbl = tk.Label(header, text="📋 Auditoría de Bodega", 
                           font=('Segoe UI', 16, 'bold'), bg=Styles.LIGHT_BG, fg=Styles.PRIMARY_COLOR)
        title_lbl.pack(side='left')

        # Botones de Acción
        btn_frame = ttk.Frame(header, style='Modern.TFrame')
        btn_frame.pack(side='right')

        ttk.Button(btn_frame, text="🚚 Abastos", 
                  command=self.abrir_abastos_ocr, style='Modern.TButton').pack(side='left', padx=3)
        
        ttk.Button(btn_frame, text="📄 Billing", 
                  command=self.abrir_billing_excel, style='Modern.TButton').pack(side='left', padx=3)

        ttk.Button(btn_frame, text="🧼 Limpiar", 
                  command=self.ejecutar_limpiar_billing, style='Danger.TButton').pack(side='left', padx=3)

        ttk.Button(btn_frame, text="🕒 Historial", 
                  command=self.ver_historial_completo, style='Info.TButton').pack(side='left', padx=3)

        ttk.Button(btn_frame, text="📊 Exportar", 
                  command=self.exportar_excel, style='Success.TButton').pack(side='left', padx=3)
        
        ttk.Button(btn_frame, text="🔄", 
                  command=self.cargar_datos, style='Info.TButton').pack(side='left', padx=3)

        # Tabla de Auditoría
        table_frame = tk.Frame(self.main_frame, bg='white', highlightbackground=Styles.BORDER_COLOR, highlightthickness=1)
        table_frame.pack(fill='both', expand=True)

        cols = ("SKU", "Producto", "Inicio (E)", "Abastos (+)", "Billing (-)", "Sistema (Calc)", "Manual (E)", "Diferencia")
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings', style='Modern.Treeview')
        
        # Estilo para columnas
        widths = {"SKU": 80, "Producto": 250, "Inicio (E)": 80, "Abastos (+)": 80, "Billing (-)": 80, "Sistema (Calc)": 100, "Manual (E)": 100, "Diferencia": 100}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths.get(col, 100), anchor='center' if col != "Producto" else 'w')

        # Scrollbar
        sb = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # Tags para colores (Semáforo Suave)
        self.tree.tag_configure('error', foreground='#9C0006', background='#FFD1D1')      # Rojo suave
        self.tree.tag_configure('success', foreground='#114F1D', background='#DDF2D1')    # Verde suave
        self.tree.tag_configure('warning', foreground='#856404', background='#FFF9C4')    # Amarillo suave
        
        # Alternating rows (lines simulation)
        self.tree.tag_configure('odd', background='#F2F2F2')
        self.tree.tag_configure('even', background='white')

        # Evento de doble click para edición inline
        self.tree.bind("<Double-1>", self.on_double_click)

    def cargar_datos(self):
        self.root_app.set_status("🔄 Cargando auditoría...", is_busy=True)
        
        def run_load():
            try:
                self.id_sesion = obtener_o_crear_sesion_auditoria(self.sucursal)
                items = obtener_items_auditoria(self.id_sesion)
                
                # Pre-cargar stock actual si no hay ítems en la sesión
                stock_actual_legacy = []
                if not items:
                    from data_layer.inventory import obtener_todos_los_skus_para_movimiento
                    stock_actual_legacy = obtener_todos_los_skus_para_movimiento(sucursal_context=self.sucursal)
                
                # Actualizar UI en el hilo principal
                self.parent.after(0, lambda: self._actualizar_tabla_ui(items, stock_actual_legacy))
            except Exception as e:
                logger.error(f"Error cargando datos de auditoría: {e}")
                self.parent.after(0, lambda: self.root_app.set_status(f"⚠️ Error: {e}", timeout=5000))

        threading.Thread(target=run_load, daemon=True).start()

    def _actualizar_tabla_ui(self, items, stock_actual_legacy):
        """Actualiza el Treeview con los datos cargados."""
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        if not items:
            for p in stock_actual_legacy:
                nombre, sku, cant = p[0], p[1], p[2]
                self.agregar_item_a_tabla(sku, nombre, 0, 0, 0, 0)
        else:
            for sku, data in items.items():
                inicio = data.get('inicio', 0)
                abastos = data.get('abastos', 0)
                billing = data.get('billing', 0)
                sistema = inicio + abastos - billing
                manual = data.get('manual', 0)
                diferencia = manual - sistema
                
                tag = ''
                if diferencia == 0 and manual > 0:
                    tag = 'success'
                elif diferencia < 0:
                    tag = 'error'
                elif diferencia > 0:
                    tag = 'warning'
                
                row_parity = 'even' if len(self.tree.get_children()) % 2 == 0 else 'odd'
                self.tree.insert('', 'end', values=(
                    sku, data['nombre'], inicio, abastos, billing, sistema, manual, diferencia
                ), tags=(tag, row_parity))
        
        self.root_app.set_status("Listo", timeout=1000)

    def agregar_item_a_tabla(self, sku, nombre, inicio, abasto, billing, manual):
        sistema = inicio + abasto - billing
        dif = manual - sistema
        self.tree.insert('', 'end', values=(sku, nombre, inicio, abasto, billing, sistema, manual, dif))

    def on_double_click(self, event):
        """Maneja la edición inline de las columnas marcadas con (E)."""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        
        column = self.tree.identify_column(event.x) # "#1", "#2"...
        item_id = self.tree.identify_row(event.y)
        
        # Solo permitimos editar Inicio (#3) y Manual (#7)
        if column not in ("#3", "#7"): return
        
        col_index = int(column[1:]) - 1
        values = self.tree.item(item_id, 'values')
        sku = values[0]
        
        # Crear entrada flotante
        x, y, w, h = self.tree.bbox(item_id, column)
        
        entry = ttk.Entry(self.tree)
        entry.insert(0, values[col_index])
        entry.select_range(0, tk.END)
        entry.focus_set()
        
        entry.place(x=x, y=y, width=w, height=h)
        
        def save_edit(e=None):
            new_val = entry.get()
            entry.destroy()
            try:
                val_int = int(new_val)
                field = "cantidad_inicio" if column == "#3" else "cantidad_manual"

                # Guardar en DB de forma asíncrona para evitar LAG en la UI
                def async_save():
                    try:
                        guardar_cambio_item(self.id_sesion, sku, field, val_int)
                    except Exception as e:
                        logger.error(f"Error guardando cambio asíncrono: {e}")

                threading.Thread(target=async_save, daemon=True).start()

                # Actualizar valores locales en el Treeview SIN RECARGAR TODO (INSTANTÁNEO)
                new_values = list(values)
                new_values[col_index] = val_int
                
                # Recalcular cálculos derivados
                inicio = int(new_values[2])
                abastos = int(new_values[3])
                billing = int(new_values[4])
                sistema = inicio + abastos - billing
                manual = int(new_values[6])
                diferencia = manual - sistema
                
                new_values[5] = sistema
                new_values[7] = diferencia
                
                # Semáforo persistente tras edición
                tag = ''
                if diferencia == 0 and manual > 0:
                    tag = 'success'
                elif diferencia < 0:
                    tag = 'error'
                elif diferencia > 0:
                    tag = 'warning'
                
                # Mantener paridad
                row_index = self.tree.index(item_id)
                row_parity = 'even' if row_index % 2 == 0 else 'odd'
                self.tree.item(item_id, values=new_values, tags=(tag, row_parity))
            except ValueError:
                pass
                
        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", lambda e: entry.destroy())

    def abrir_abastos_ocr(self):
        AbastoOCRDialog(self.main_frame, self.id_sesion, self.cargar_datos)

    def abrir_billing_excel(self):
        BillingExcelDialog(self.main_frame, self.id_sesion, self.cargar_datos)

    def ver_historial_completo(self):
        SessionHistoryDialog(self.main_frame, self.id_sesion)

    def exportar_excel(self):
        """Exporta la tabla de auditoría actual a un archivo Excel premium."""
        items = []
        for child in self.tree.get_children():
            items.append(self.tree.item(child, 'values'))
        
        if not items:
            messagebox.showwarning("StockWare", "No hay datos para exportar.")
            return
            
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                          filetypes=[("Excel", "*.xlsx")],
                                          initialfile=f"Auditoria_{self.sucursal}_{datetime.now().strftime('%Y%m%d')}.xlsx")
        if not path: return
        
        try:
            # Lista de columnas REALES del Treeview para el DataFrame
            cols = ["SKU", "Producto", "Inicio (E)", "Abastos (+)", "Billing (-)", "Sistema (Calc)", "Manual (E)", "Diferencia"]
            df = pd.DataFrame(items, columns=cols)
            
            # Convertir columnas numéricas de forma segura (Controlando errores de tipos)
            numeric_cols = ["Inicio (E)", "Abastos (+)", "Billing (-)", "Sistema (Calc)", "Manual (E)", "Diferencia"]
            for col in numeric_cols:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                except Exception as type_err:
                    logger.warning(f"Error convirtiendo columna {col} a numérico: {type_err}")
                    df[col] = 0

            # Motor de exportación robusto
            writer = pd.ExcelWriter(path, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='INFORME_AUDITORIA')
            
            workbook  = writer.book
            worksheet = writer.sheets['INFORME_AUDITORIA']
            
            # --- ESTILOS PROFESIONALES ---
            header_fmt = workbook.add_format({
                'bold': True, 'text_wrap': True, 'valign': 'middle', 'align': 'center',
                'fg_color': '#2C3E50', 'font_color': 'white', 'border': 1
            })
            cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'font_name': 'Segoe UI'})
            prod_fmt = workbook.add_format({'border': 1, 'align': 'left', 'font_name': 'Segoe UI'})
            
            # Semáforo de Colores
            fmt_success = workbook.add_format({'bg_color': '#DDF2D1', 'font_color': '#114F1D', 'bold': True, 'border': 1, 'align': 'center'})
            fmt_danger = workbook.add_format({'bg_color': '#FFD1D1', 'font_color': '#9C0006', 'bold': True, 'border': 1, 'align': 'center'})
            fmt_warning = workbook.add_format({'bg_color': '#FFF9C4', 'font_color': '#856404', 'bold': True, 'border': 1, 'align': 'center'})

            # Aplicar anchos
            worksheet.set_column('A:A', 10) # SKU
            worksheet.set_column('B:B', 40) # Producto
            worksheet.set_column('C:H', 15) # Valores

            # Escribir encabezados con estilo
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_fmt)

            # Escribir datos con formato condicional en la columna Diferencia (H=7)
            for row_num in range(1, len(df) + 1):
                # Escribir filas normales
                sku, prod = df.iloc[row_num-1, 0], df.iloc[row_num-1, 1]
                worksheet.write(row_num, 0, sku, cell_fmt)
                worksheet.write(row_num, 1, prod, prod_fmt)
                
                # Escribir valores numéricos
                for c in range(2, 7): # C a G
                    worksheet.write(row_num, c, df.iloc[row_num-1, c], cell_fmt)
                
                # Formato condicional para Diferencia (Col H)
                dif_val = df.iloc[row_num-1, 7]
                manual_val = df.iloc[row_num-1, 6]
                
                if manual_val == 0: 
                    worksheet.write(row_num, 7, dif_val, cell_fmt) # Sin auditar
                elif dif_val == 0:
                    worksheet.write(row_num, 7, dif_val, fmt_success) # Cuadra
                elif dif_val < 0:
                    worksheet.write(row_num, 7, dif_val, fmt_danger) # Falta
                else:
                    worksheet.write(row_num, 7, dif_val, fmt_warning) # Sobra
                
            writer.close()
            messagebox.showinfo("Éxito", f"📊 Reporte Premium guardado en:\n{path}")
            
            if messagebox.askyesno("Finalizar Auditoría", "¿Desea cerrar la sesión actual y limpiar los datos para una nueva auditoría?"):
                from data_layer.warehouse_audit import finalizar_sesion_auditoria
                if finalizar_sesion_auditoria(self.id_sesion):
                    self.cargar_datos() 
                    messagebox.showinfo("Limpieza", "Auditoría reseteada correctamente.")
            
            os.startfile(os.path.dirname(path))
            
        except Exception as e:
            logger.error(f"Fallo crítico exportando Excel: {e}")
            messagebox.showerror("Error", f"No se pudo exportar el archivo.\nDetalle: {str(e)}")

    def ejecutar_limpiar_billing(self):
        """Borra todos los registros de billing de la sesión actual."""
        if messagebox.askyesno("Confirmar Limpieza", "¿Desea limpiar todos los datos de Billing (Excel) de la sesión actual?\nEsto pondrá la columna 'Billing (-)' en 0."):
            self.root_app.set_status("🧼 Limpiando datos...", is_busy=True)
            
            def run_clear():
                if limpiar_billing_sesion(self.id_sesion):
                    self.parent.after(0, lambda: messagebox.showinfo("Éxito", "Datos de Billing limpiados correctamente."))
                    self.cargar_datos() 
                else:
                    self.parent.after(0, lambda: messagebox.showerror("Error", "No se pudieron limpiar los datos."))
                    self.parent.after(0, lambda: self.root_app.set_status("Listo"))

            threading.Thread(target=run_clear, daemon=True).start()

class AbastoOCRDialog:
    def __init__(self, parent, id_sesion, callback):
        self.window = tk.Toplevel(parent)
        self.window.title("🚚 Registro Asistido de Abastos")
        self.window.geometry("1100x700")
        self.window.state('zoomed') # PANTALLA COMPLETA
        self.window.grab_set() # Modal
        self.id_sesion = id_sesion
        self.callback = callback
        self.img_path = ""
        self.photo = None
        self.historial_cargado = False
        
        from config import PRODUCTOS_INICIALES
        self.opciones_productos = [f"{item[1]} - {item[0]}" for item in PRODUCTOS_INICIALES]
        self.sku_map = {f"{item[1]} - {item[0]}": item[1] for item in PRODUCTOS_INICIALES}
        
        self.setup_ui()

    def setup_ui(self):
        pane = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        pane.pack(fill='both', expand=True, padx=10, pady=10)
        
        # PANEL IZQUIERDO: Data Entry e Historial
        left_frame = ttk.Frame(pane)
        pane.add(left_frame, weight=2) # Aumentado el peso para que el historial sea más visible
        
        header = ttk.Frame(left_frame)
        header.pack(fill='x', pady=5)
        ttk.Button(header, text="Cargar Imagen del Documento", command=self.cargar_imagen).pack(side='left')
        self.lbl_archivo = ttk.Label(header, text="Ningún archivo adjuntado...", foreground="gray")
        self.lbl_archivo.pack(side='left', padx=10)
        
        form_frame = ttk.LabelFrame(left_frame, text="Agregar Ítem", padding=10)
        form_frame.pack(fill='x', pady=10)
        
        ttk.Label(form_frame, text="Producto:").grid(row=0, column=0, sticky='w', pady=2)
        self.cmb_sku = ttk.Combobox(form_frame, values=self.opciones_productos, width=40)
        self.cmb_sku.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        
        ttk.Label(form_frame, text="Cantidad:").grid(row=1, column=0, sticky='w', pady=2)
        self.ent_cant = ttk.Entry(form_frame, width=15)
        self.ent_cant.grid(row=1, column=1, sticky='w', padx=5, pady=2)

        # NUEVOS CAMPOS: Factura y Fecha
        ttk.Label(form_frame, text="N° Factura:").grid(row=2, column=0, sticky='w', pady=2)
        self.ent_factura = ttk.Entry(form_frame, width=25)
        self.ent_factura.grid(row=2, column=1, sticky='ew', padx=5, pady=2)

        ttk.Label(form_frame, text="Fecha Doc:").grid(row=3, column=0, sticky='w', pady=2)
        self.ent_fecha = ttk.Entry(form_frame, width=25)
        self.ent_fecha.grid(row=3, column=1, sticky='ew', padx=5, pady=2)
        self.ent_fecha.insert(0, datetime.now().strftime("%Y-%m-%d")) # Default hoy
        
        btn_add = ttk.Button(form_frame, text="Agregar a la Tabla (Enter)", command=self.agregar_fila)
        btn_add.grid(row=4, column=0, columnspan=2, pady=10)
        
        self.cmb_sku.bind("<Return>", lambda e: self.ent_cant.focus_set())
        self.ent_cant.bind("<Return>", lambda e: self.ent_factura.focus_set())
        self.ent_factura.bind("<Return>", lambda e: self.ent_fecha.focus_set())
        self.ent_fecha.bind("<Return>", lambda e: self.agregar_fila())
        
        # Botones Superiores (NUEVO: Guardar arriba para visibilidad)
        self.btn_guardar = ttk.Button(left_frame, text="✅ Guardar Todo y Cargar Abastos", style='Success.TButton', command=self.guardar_todo)
        self.btn_guardar.pack(side=tk.TOP, pady=10, fill='x')
        
        ttk.Label(left_frame, text="* Presiona 'Suprimir' o 'Delete' para borrar una fila seleccionada.", foreground="gray").pack(side=tk.TOP, anchor='w')

        # Tabla de Selección Actual
        table_frame = ttk.Frame(left_frame)
        table_frame.pack(side=tk.TOP, fill='both', expand=True, pady=5)
        
        cols = ("SKU", "Producto", "Cant")
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings', style='Modern.Treeview')
        self.tree.heading("SKU", text="SKU")
        self.tree.column("SKU", width=80, anchor='center')
        self.tree.heading("Producto", text="Producto")
        self.tree.column("Producto", width=150, anchor='w')
        self.tree.heading("Cant", text="Cant")
        self.tree.column("Cant", width=60, anchor='center')
        self.tree.pack(side='left', fill='both', expand=True)
        
        sb = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
           # SECCIÓN DE HISTORIAL (Agrupado por Referencia)
        hist_frame = ttk.LabelFrame(left_frame, text="🕒 Historial de Paquetes (Agrupado)", padding=5)
        hist_frame.pack(side=tk.BOTTOM, fill='x', pady=5)
        
        cols_h = ("Fecha", "Producto", "Cant", "Factura")
        self.tree_hist = ttk.Treeview(hist_frame, columns=cols_h, show='headings', height=10, style='Modern.Treeview')
        self.tree_hist.heading("Fecha", text="Fecha Reg.")
        self.tree_hist.column("Fecha", width=120, anchor='center')
        self.tree_hist.heading("Producto", text="Producto Ingresado")
        self.tree_hist.column("Producto", width=250, anchor='w')
        self.tree_hist.heading("Cant", text="Cant")
        self.tree_hist.column("Cant", width=50, anchor='center')
        self.tree_hist.heading("Factura", text="Factura")
        self.tree_hist.column("Factura", width=100, anchor='center')
        self.tree_hist.pack(side='left', fill='both', expand=True)
        
        sb_h = ttk.Scrollbar(hist_frame, orient='vertical', command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=sb_h.set)
        sb_h.pack(side='right', fill='y')
        
        # Eventos del historial
        self.tree_hist.bind("<<TreeviewSelect>>", self.on_historial_select)
        self.tree_hist.bind("<Double-1>", self.on_double_click_historial)
        
        self.tree.bind("<Delete>", self.eliminar_fila)
        
        self.cargar_historial()
        
        # PANEL DERECHO: Visor
        right_frame = ttk.Frame(pane)
        pane.add(right_frame, weight=2)
        
        visor_frame = ttk.LabelFrame(right_frame, text="Visor (Documento Original)")
        visor_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(visor_frame, bg='darkgray')
        
        hbar = ttk.Scrollbar(visor_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = ttk.Scrollbar(visor_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(side=tk.LEFT, fill='both', expand=True)
        
        self.info_lbl = tk.Label(right_frame, text="Visor de Documentos", 
                                font=('Segoe UI', 10, 'bold'), fg='white', bg=Styles.PRIMARY_COLOR)
        self.info_lbl.pack(fill='x', side=tk.TOP)
        
        btn_hist_frame = ttk.Frame(left_frame)
        btn_hist_frame.pack(side=tk.BOTTOM, fill='x', pady=5)
        
        ttk.Button(btn_hist_frame, text="🔄 Refrescar Historial", 
                   command=self.cargar_historial).pack(side='left', padx=5)

    def cargar_imagen(self):
        path = filedialog.askopenfilename(filetypes=[("Imágenes", "*.png *.jpg *.jpeg")])
        if not path: return
        
        self.img_path = path
        self.lbl_archivo.config(text=os.path.basename(path), foreground="green")
        self.window.lift() # Asegurar que la ventana vuelva al frente tras el diálogo de archivos
        
        if HAS_PIL:
            img = Image.open(path)
            w, h = img.size
            if w > 800:
                ratio = 800 / float(w)
                if hasattr(Image, 'Resampling'):
                    resample_filter = Image.Resampling.LANCZOS
                elif hasattr(Image, 'LANCZOS'):
                    resample_filter = Image.LANCZOS
                else:
                    resample_filter = 1
                img = img.resize((800, int(h * ratio)), resample_filter)
            
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.config(scrollregion=(0, 0, img.size[0], img.size[1]))
            self.canvas.create_image(0, 0, image=self.photo, anchor='nw')

    def on_historial_select(self, event):
        """Carga la imagen asociada al registro del historial seleccionado."""
        seleccion = self.tree_hist.selection()
        if not seleccion: 
            return
        
        item_id = seleccion[0]
        # tags[0] = path, tags[1] = id_registro
        tags = self.tree_hist.item(item_id, 'tags')
        path = tags[0] if tags else ""
        
        if path and os.path.exists(path):
            self.mostrar_imagen_por_path(path)
            self.lbl_archivo.config(text=f"📜 Histórico: {os.path.basename(path)}", foreground="blue")
        else:
            self.canvas.delete("all")
            self.lbl_archivo.config(text="⚠️ Imagen no disponible", foreground="red")

    def eliminar_seleccionado(self):
        """Elimina el registro de abasto seleccionado después de confirmar."""
        seleccion = self.tree_hist.selection()
        if not seleccion: return
        
        item_id = seleccion[0]
        tags = self.tree_hist.item(item_id, 'tags')
        if not tags or len(tags) < 2: return
        
        id_db = tags[1] # El ID real de la base de datos
        sku_info = self.tree_hist.item(item_id, 'values')[1]
        
        if messagebox.askyesno("Confirmar Eliminación", f"¿Desea eliminar el registro de '{sku_info}'?\nEsta acción no se puede deshacer.", parent=self.window):
            if eliminar_abasto_registro(id_db):
                messagebox.showinfo("Éxito", "Registro eliminado correctamente.", parent=self.window)
                self.cargar_historial()
                self.callback() # Actualizar tabla principal
            else:
                messagebox.showerror("Error", "No se pudo eliminar el registro.", parent=self.window)

    def mostrar_imagen_por_path(self, path):
        """Carga y muestra una imagen en el canvas dado su path."""
        if not HAS_PIL: return
        try:
            img = Image.open(path)
            w, h = img.size
            # Redimensionado inteligente para el visor
            ratio = 800 / float(w) if w > 800 else 1.0
            new_size = (int(w * ratio), int(h * ratio))
            
            if hasattr(Image, 'Resampling'):
                resample_filter = Image.Resampling.LANCZOS
            else:
                resample_filter = Image.LANCZOS if hasattr(Image, 'LANCZOS') else 1
                
            img = img.resize(new_size, resample_filter)
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))
            self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        except Exception as e:
            logger.error(f"Error cargando imagen del historial: {e}")

    def agregar_fila(self):
        seleccion = self.cmb_sku.get().strip()
        cantidad = self.ent_cant.get().strip()
        
        if not seleccion or not cantidad:
            messagebox.showwarning("Válido", "Seleccione un producto e ingrese una cantidad.")
            return
            
        try:
            cant_int = int(cantidad)
            if cant_int <= 0: raise ValueError
        except:
            messagebox.showerror("Error", "Cantidad debe ser un entero positivo.")
            return
            
        sku = self.sku_map.get(seleccion, seleccion.split(" - ")[0] if " - " in seleccion else seleccion)
        producto = seleccion.split(" - ")[1] if " - " in seleccion else seleccion
        
        self.tree.insert('', 'end', values=(sku, producto, cant_int))
        
        self.cmb_sku.set('')
        self.ent_cant.delete(0, tk.END)
        self.cmb_sku.focus_set()

    def eliminar_fila(self, event=None):
        seleccion = self.tree.selection()
        if seleccion:
            for item in seleccion:
                self.tree.delete(item)

    def guardar_todo(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("Atención", "No hay elementos para guardar.")
            return
            
        if not self.img_path:
            resp = messagebox.askyesno("Sin Imagen", "No ha adjuntado ninguna imagen de respaldo. ¿Desea continuar de todos modos?")
            if not resp: return
            
        guardados = 0
        factura = self.ent_factura.get().strip()
        fecha_doc = self.ent_fecha.get().strip()
        
        try:
            for item_id in items:
                sku, _, cant = self.tree.item(item_id, 'values')
                registrar_abasto_ocr(
                    self.id_sesion, sku, int(cant), self.img_path, 
                    factura=factura, fecha_doc=fecha_doc if fecha_doc else None
                )
                guardados += 1
                
            messagebox.showinfo("Éxito", f"Se registraron {guardados} ítems de la Factura '{factura}' correctamente.")
            self.cargar_historial() # Actualizar mini-tabla
            self.callback() # Actualizar tabla principal
            # No cerramos la ventana automáticamente para que pueda seguir mapeando o ver el historial
            self.tree.delete(*self.tree.get_children()) # Limpiar tabla de trabajo
            # Mantener factura y fecha para el próximo set si es del mismo documento
        except Exception as e:
            logger.error(f"Error guardando abastos multiline: {e}")
            messagebox.showerror("Error", f"Ocurrió un error al guardar: {e}")

    def cargar_historial(self):
        """Carga el historial de abastos detallado."""
        from data_layer.warehouse_audit import obtener_detalles_abastos
        for i in self.tree_hist.get_children():
            self.tree_hist.delete(i)
        
        try:
            detalles = obtener_detalles_abastos(self.id_sesion)
            if not detalles: return
            
            for item in detalles:
                # schema: fecha_reg, sku, nombre, cant, img, factura, fecha_doc, id_db
                f_reg, sku, nombre, cant, img, fact, f_doc, id_db = item
                
                reg_time = f_reg.strftime("%d/%m %H:%M") if hasattr(f_reg, 'strftime') else str(f_reg)[:16]
                fact_disp = fact if fact else "S/Fact"
                
                # Guardamos el id_db en el segundo tag y la factura en el tercero
                self.tree_hist.insert('', 'end', values=(reg_time, f"{sku} - {nombre}", cant, fact_disp), 
                                     tags=(img, id_db, fact_disp))
                
        except Exception as e:
            logger.error(f"Error cargando historial abastos: {e}")

    def on_double_click_historial(self, event):
        """Maneja la edición de un registro del historial."""
        item_id = self.tree_hist.identify_row(event.y)
        if not item_id: return
        
        values = self.tree_hist.item(item_id, 'values')
        tags = self.tree_hist.item(item_id, 'tags')
        
        if not tags or len(tags) < 2: return
        id_db = tags[1]
        
        producto = values[1]
        cant_actual = values[2]
        fact_actual = values[3]
        
        # Diálogo simple de edición
        from tkinter import simpledialog
        nueva_cant = simpledialog.askinteger("Editar Cantidad", f"Producto: {producto}\nNueva cantidad:", 
                                            initialvalue=cant_actual, parent=self.window)
        
        if nueva_cant is not None and nueva_cant > 0:
            from data_layer.warehouse_audit import actualizar_abasto_ocr
            if actualizar_abasto_ocr(id_db, nueva_cant):
                messagebox.showinfo("Éxito", "Registro actualizado correctamente.")
                self.cargar_historial()
                self.callback()
            else:
                messagebox.showerror("Error", "No se pudo actualizar el registro.")

    def eliminar_factura(self):
        """Elimina todos los registros asociados a la factura del registro seleccionado."""
        seleccion = self.tree_hist.selection()
        if not seleccion: return
        
        item_id = seleccion[0]
        values = self.tree_hist.item(item_id, 'values')
        tags = self.tree_hist.item(item_id, 'tags')
        
        factura = tags[2] if len(tags) > 2 else values[3]
        
        if factura == "S/Fact":
            messagebox.showwarning("Aviso", "No se puede eliminar por lote si no hay número de factura.")
            return

        if messagebox.askyesno("Confirmar Eliminación Masiva", 
                              f"¿Desea eliminar TODOS los registros asociados a la Factura '{factura}'?\n"
                              "Esta acción afectará a múltiples productos detectados en este lote.", parent=self.window):
            from data_layer.warehouse_audit import eliminar_abastos_por_factura
            if eliminar_abastos_por_factura(self.id_sesion, factura):
                messagebox.showinfo("Éxito", "Lote de factura eliminado correctamente.", parent=self.window)
                self.cargar_historial()
                self.callback()
            else:
                messagebox.showerror("Error", "No se pudieron eliminar los registros del lote.", parent=self.window)
        
class BillingExcelDialog:
    def __init__(self, parent, id_sesion, callback):
        self.window = tk.Toplevel(parent)
        self.window.title("📄 Cargar Billing desde Excel")
        self.window.state('zoomed') # PANTALLA COMPLETA PARA MAPEADO FÁCIL
        self.window.grab_set()
        self.id_sesion = id_sesion
        self.callback = callback
        self.df = None
        self.col_totals = {}
        self.setup_ui()

    def setup_ui(self):
        main = ttk.Frame(self.window, padding=20)
        main.pack(fill='both', expand=True)

        header_frame = ttk.Frame(main)
        header_frame.pack(fill='x', pady=5)

        tk.Label(header_frame, text="1. Seleccione el reporte de consumo (Excel)", font=('Segoe UI', 10, 'bold')).pack(side='left', pady=5)
        
        ttk.Button(header_frame, text="Seleccionar Archivo", command=self.procesar_excel).pack(side='left', padx=10)
        
        self.status_lbl = tk.Label(header_frame, text="", fg=Styles.SECONDARY_COLOR)
        self.status_lbl.pack(side='left', padx=10)

        # Bottom Frame (Siempre visible al final)
        bottom_frame = ttk.Frame(main, padding=(0, 10, 0, 0))
        bottom_frame.pack(fill='x', side=tk.BOTTOM)

        ttk.Label(bottom_frame, text="* Doble click para editar SKU o Cantidad manualmente.", foreground='gray').pack(side='left')

        self.btn_guardar = ttk.Button(bottom_frame, text="✅ GUARDAR CONSUMOS EN AUDITORIA", 
                                       command=self.guardar_registros, 
                                       style='Success.TButton', 
                                       state='disabled')
        self.btn_guardar.pack(side='right', ipadx=10, ipady=5)
        
        ttk.Button(bottom_frame, text="🧼 Limpiar Billing Actual", 
                   command=self.limpiar_datos_actuales, 
                   style='Danger.TButton').pack(side='right', padx=10)

        # Mapeo Container (Ocupa el resto del espacio)
        self.mapping_frame = ttk.LabelFrame(main, text="2. Mapeo de Columnas", padding=10)
        self.mapping_frame.pack(fill='both', expand=True, pady=10)

        cols = ("Columna Excel", "Total Detectado", "SKU Mapeado")
        self.tree = ttk.Treeview(self.mapping_frame, columns=cols, show='headings', style='Modern.Treeview')
        
        self.tree.heading("Columna Excel", text="Columna Excel")
        self.tree.column("Columna Excel", width=200, anchor='w')
        
        self.tree.heading("Total Detectado", text="Total Detectado")
        self.tree.column("Total Detectado", width=120, anchor='center')
        
        self.tree.heading("SKU Mapeado", text="SKU Mapeado")
        self.tree.column("SKU Mapeado", width=120, anchor='center')
        
        self.tree.pack(side='left', fill='both', expand=True)

        scrollbar = ttk.Scrollbar(self.mapping_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind("<Double-1>", self.on_double_click)

    def procesar_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if not path: return
        self.archivo_path = path

        try:
            self.df = pd.read_excel(path)
            self.status_lbl.config(text=f"Cargado: {os.path.basename(path)}", fg='green')
            self.poblar_mapeo()
            self.btn_guardar.config(state='normal')
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al procesar Excel: {e}")

    def poblar_mapeo(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        from config import PRODUCTOS_INICIALES
        # Mapeo: Nombre (Upper) -> SKU
        name_to_sku = {str(item[0]).strip().upper(): item[1] for item in PRODUCTOS_INICIALES}
        
        # Optimización: Sumar solo columnas numéricas de un solo golpe
        # Esto es mucho más rápido que iterar y sumar una por una
        numeric_df = self.df.select_dtypes(include=['number']).fillna(0)
        resumen_sumas = numeric_df.sum()

        for col in self.df.columns:
            col_str = str(col).strip()
            col_upper = col_str.upper().replace("  ", " ").strip()
            
            # Ignorar columnas comunes que no son materiales
            if col_str not in resumen_sumas.index or any(ig in col_upper for ig in ignore_cols) or "FECHA" in col_upper or "NOMBRE" in col_upper or "TITULAR" in col_upper:
                continue
            
            total = resumen_sumas[col_str]
            
            if total > 0:
                # Intentar mapear por nombre exacto
                sku_mapeado = name_to_sku.get(col_upper, "")
                
                # Si no hay match exacto, intentar match parcial o alias comunes
                if not sku_mapeado:
                    # Match parcial si el nombre del excel contiene el nombre interno o viceversa
                    for internal_name, sku_internal in name_to_sku.items():
                        if internal_name in col_upper or col_upper in internal_name:
                            sku_mapeado = sku_internal
                            break
                    
                    # Alias específicos
                    if not sku_mapeado:
                        if col_upper == 'CODILLA': sku_mapeado = name_to_sku.get('COLILLA', '2-7-11')
                        elif col_upper == 'CALCAMONIA': sku_mapeado = name_to_sku.get('STICKER', '2-7-07')

                self.col_totals[col_str] = total
                self.tree.insert('', 'end', values=(col_str, int(total), sku_mapeado))
        
    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        
        column = self.tree.identify_column(event.x)
        if column not in ("#2", "#3"): return # Permitir editar total o SKU
        
        item_id = self.tree.identify_row(event.y)
        values = self.tree.item(item_id, 'values')
        
        col_idx = int(column[1:]) - 1
        x, y, w, h = self.tree.bbox(item_id, column)
        
        entry = ttk.Entry(self.tree)
        entry.insert(0, values[col_idx])
        entry.select_range(0, tk.END)
        entry.focus_set()
        
        entry.place(x=x, y=y, width=w, height=h)
        
        def save_edit(e=None):
            new_val = entry.get().strip()
            self.tree.item(item_id, values=(values[0], values[1], new_val))
            entry.destroy()
            
        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def guardar_registros(self):
        count = 0
        from data_layer.warehouse_audit import registrar_billing_excel
        
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, 'values')
            col_name, total, sku = values
            total = int(total)
            sku = str(sku).strip()
            
            if sku and total > 0:
                registrar_billing_excel(self.id_sesion, sku, total, os.path.basename(self.archivo_path))
                count += 1
                
        if count > 0:
            messagebox.showinfo("Éxito", f"Se registraron {count} productos en la auditoría.")
            self.callback()
            self.window.destroy()
    def limpiar_datos_actuales(self):
        """Borra todos los registros de billing de la sesión actual."""
        if messagebox.askyesno("Confirmar Limpieza", "¿Desea limpiar todos los datos de Billing (Excel) de la sesión actual?\nEsto pondrá la columna 'Billing (-)' en 0."):
            if limpiar_billing_sesion(self.id_sesion):
                messagebox.showinfo("Éxito", "Datos de Billing limpiados correctamente.")
                self.callback()
                # Limpiar tabla visual si hay datos cargados
                for i in self.tree.get_children():
                    self.tree.delete(i)
                self.btn_guardar.config(state='disabled')
            else:
                messagebox.showerror("Error", "No se pudieron limpiar los datos.")

class SessionHistoryDialog:
    def __init__(self, parent, id_sesion):
        self.window = tk.Toplevel(parent)
        self.window.title("🕒 Historial Detallado de Sesión")
        self.window.geometry("1200x800")
        self.window.state('zoomed')
        self.window.grab_set()
        self.id_sesion = id_sesion
        self.abastos_data = []
        self.billing_data = []
        
        self.setup_ui()
        self.cargar_datos()

    def setup_ui(self):
        main = ttk.Frame(self.window, padding=10)
        main.pack(fill='both', expand=True)
        
        # Header
        header = ttk.Frame(main)
        header.pack(fill='x', pady=(0, 10))
        tk.Label(header, text="📋 Historial de Auditoría (Documentos)", font=('Segoe UI', 14, 'bold'), fg=Styles.PRIMARY_COLOR).pack(side='left')
        
        # PanedWindow for Master-Detail
        self.pane = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        self.pane.pack(fill='both', expand=True)
        
        # --- LADO IZQUIERDO: MAESTRO (Facturas / Archivos) ---
        left_frame = ttk.Frame(self.pane)
        self.pane.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="Facturas / Documentos", font=('Segoe UI', 10, 'bold')).pack(pady=5)
        
        cols_master = ("Tipo", "Referencia", "Items")
        self.tree_master = ttk.Treeview(left_frame, columns=cols_master, show='headings', style='Modern.Treeview')
        self.tree_master.heading("Tipo", text="Tipo")
        self.tree_master.column("Tipo", width=70, anchor='center')
        self.tree_master.heading("Referencia", text="Factura / Archivo")
        self.tree_master.column("Referencia", width=180, anchor='w')
        self.tree_master.heading("Items", text="Ítems")
        self.tree_master.column("Items", width=50, anchor='center')
        self.tree_master.pack(fill='both', expand=True)
        
        sb_master = ttk.Scrollbar(left_frame, orient='vertical', command=self.tree_master.yview)
        self.tree_master.configure(yscrollcommand=sb_master.set)
        sb_master.pack(side='right', fill='y')
        
        self.tree_master.bind("<<TreeviewSelect>>", self.on_master_select)
        self.tree_master.bind("<Double-1>", lambda e: self.eliminar_lote_completo())
        
        # --- LADO DERECHO: DETALLE (Productos en esa factura) ---
        right_frame = ttk.Frame(self.pane)
        self.pane.add(right_frame, weight=2)
        
        self.detail_label = ttk.Label(right_frame, text="Seleccione un documento para ver detalles", font=('Segoe UI', 10, 'italic'), foreground='gray')
        self.detail_label.pack(pady=5)
        
        cols_detail = ("SKU", "Producto", "Cantidad", "Fecha Reg.")
        self.tree_detail = ttk.Treeview(right_frame, columns=cols_detail, show='headings', style='Modern.Treeview')
        self.tree_detail.heading("SKU", text="SKU")
        self.tree_detail.column("SKU", width=80, anchor='center')
        self.tree_detail.heading("Producto", text="Producto")
        self.tree_detail.column("Producto", width=250, anchor='w')
        self.tree_detail.heading("Cantidad", text="Cant.")
        self.tree_detail.column("Cantidad", width=70, anchor='center')
        self.tree_detail.heading("Fecha Reg.", text="Registrado")
        self.tree_detail.column("Fecha Reg.", width=120, anchor='center')
        self.tree_detail.pack(fill='both', expand=True)
        
        sb_detail = ttk.Scrollbar(right_frame, orient='vertical', command=self.tree_detail.yview)
        self.tree_detail.configure(yscrollcommand=sb_detail.set)
        sb_detail.pack(side='right', fill='y')

        # --- SEGUNDO NIVEL: VISOR DE IMAGEN (Debajo del detalle) ---
        self.visor_frame = ttk.LabelFrame(right_frame, text="Visor de Documento", padding=5)
        self.visor_frame.pack(fill='both', expand=True, pady=5)
        
        self.canvas = tk.Canvas(self.visor_frame, bg='darkgray')
        
        hbar = ttk.Scrollbar(self.visor_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = ttk.Scrollbar(self.visor_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(side=tk.LEFT, fill='both', expand=True)

        self.tree_detail.bind("<<TreeviewSelect>>", self.on_detail_select)
        self.tree_detail.bind("<Double-1>", self.on_detail_double_click)

    def cargar_datos(self):
        # Mostrar indicador de carga en el Treeview Maestro
        for i in self.tree_master.get_children(): self.tree_master.delete(i)
        self.tree_master.insert('', 'end', values=("", "⌛ Cargando historial...", ""), tags=('loading',))
        
        def run_load():
            try:
                from data_layer.warehouse_audit import obtener_detalles_abastos, obtener_historial_completo_sesion
                
                # 1. Obtener Abastos detallados
                abastos = obtener_detalles_abastos(self.id_sesion)
                # 2. Obtener Billing (Excel)
                hist_completo = obtener_historial_completo_sesion(self.id_sesion)
                billing = [h for h in hist_completo if h[2] == 'BILLING']
                
                # Actualizar UI en el hilo principal
                self.window.after(0, lambda: self._poblar_historial_ui(abastos, billing))
            except Exception as e:
                logger.error(f"Error cargando historial de sesión: {e}")
                self.window.after(0, lambda: messagebox.showerror("Error", f"No se pudo cargar el historial: {e}"))

        threading.Thread(target=run_load, daemon=True).start()

    def _poblar_historial_ui(self, abastos_data, billing_data):
        self.abastos_data = abastos_data
        self.billing_data = billing_data
        
        for i in self.tree_master.get_children(): self.tree_master.delete(i)
        
        # Agrupar abastos por factura
        facturas = {}
        for item in self.abastos_data:
            fact = item[5] if item[5] else "S/Factura"
            if fact not in facturas: facturas[fact] = []
            facturas[fact].append(item)
            
        for fact, items in facturas.items():
            self.tree_master.insert('', 'end', values=("ABASTO", fact, len(items)), tags=('abasto',))
            
        # Agrupar billing por fuente (archivo)
        archivos = {}
        for item in self.billing_data:
            fuente = item[4] if item[4] else "Desconocido"
            if fuente not in archivos: archivos[fuente] = []
            archivos[fuente].append(item)
            
        for archivo, items in archivos.items():
            self.tree_master.insert('', 'end', values=("BILLING", archivo, len(items)), tags=('billing',))
            
        self.tree_master.tag_configure('abasto', foreground=Styles.PRIMARY_COLOR)
        self.tree_master.tag_configure('billing', foreground=Styles.ACCENT_COLOR)
        self.tree_master.tag_configure('loading', foreground='gray')

    def on_master_select(self, event):
        selection = self.tree_master.selection()
        if not selection: return
        
        item_id = selection[0]
        tipo, ref, _ = self.tree_master.item(item_id, 'values')
        
        # Limpiar detalle
        for i in self.tree_detail.get_children(): self.tree_detail.delete(i)
        self.detail_label.config(text=f"Detalle de {tipo}: {ref}", font=('Segoe UI', 10, 'bold'), foreground='black')
        
        if tipo == "ABASTO":
            # Filtrar abastos_data por esta factura
            img_to_show = None
            for item in self.abastos_data:
                # fecha_reg, sku, nombre, cant, img, factura, fecha_doc, id_db
                fact = item[5] if item[5] else "S/Factura"
                if fact == ref:
                    f_reg = str(item[0])[:16]
                    self.tree_detail.insert('', 'end', values=(item[1], item[2], item[3], f_reg), tags=(item[4],))
                    if not img_to_show: img_to_show = item[4]
            
            if img_to_show:
                self.mostrar_imagen(img_to_show)
            else:
                self.canvas.delete("all")
        else:
            # Filtrar billing_data por este archivo
            self.canvas.delete("all") # No hay imágenes para billing excel
            for item in self.billing_data:
                # fecha_reg, sku, tipo, cant, fuente, nombre
                if item[4] == ref:
                    f_reg = str(item[0])[:16]
                    nombre = item[5] if len(item) > 5 else "Consumo Excel"
                    # item[2] es tipo, item[4] es fuente, item[7] no existe aquí pero podemos pasar el ID si lo tuviéramos
                    # En billing_data de obtener_historial_completo_sesion no viene el ID de tabla
                    self.tree_detail.insert('', 'end', values=(item[1], nombre, item[3], f_reg), tags=('billing_item', item[1]))

        # Habilitar selección de visor si hay selección
        pass

    def on_detail_select(self, event):
        selection = self.tree_detail.selection()
        if not selection: return
        
        item_id = selection[0]
        tags = self.tree_detail.item(item_id, 'tags')
        if tags and tags[0]:
            self.mostrar_imagen(tags[0])

    def mostrar_imagen(self, path):
        """Muestra una imagen en el canvas del historial."""
        if not HAS_PIL or not path or not os.path.exists(path):
            self.canvas.delete("all")
            return
            
        try:
            img = Image.open(path)
            w, h = img.size
            # Redimensionado inteligente
            ratio = 800 / float(w) if w > 800 else 1.0
            new_size = (int(w * ratio), int(h * ratio))
            
            if hasattr(Image, 'Resampling'):
                resample_filter = Image.Resampling.LANCZOS
            else:
                resample_filter = Image.LANCZOS if hasattr(Image, 'LANCZOS') else 1
                
            img = img.resize(new_size, resample_filter)
            self.photo = ImageTk.PhotoImage(img) # Mantener referencia
            self.canvas.delete("all")
            self.canvas.config(scrollregion=(0, 0, new_size[0], new_size[1]))
            self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        except Exception as e:
            logger.error(f"Error cargando imagen en historial: {e}")

    def on_detail_double_click(self, event):
        """Maneja la edición de un ítem individual desde el historial general."""
        item_id = self.tree_detail.identify_row(event.y)
        if not item_id: return
        
        values = self.tree_detail.item(item_id, 'values')
        tags = self.tree_detail.item(item_id, 'tags')
        
        # Detectar qué factura/lote estamos editando
        sel_master = self.tree_master.selection()
        if not sel_master: return
        tipo_lote, ref_lote, _ = self.tree_master.item(sel_master[0], 'values')
        
        if tipo_lote == "ABASTO":
            # Para abastos, necesitamos el ID de la base de datos (id_db)
            # En display_details de AbastoOCRDialog lo teníamos, aquí debemos buscarlo en abastos_data
            sku = values[0]
            id_db = None
            for item in self.abastos_data:
                # fecha_reg, sku, nombre, cant, img, factura, fecha_doc, id_db
                fact = item[5] if item[5] else "S/Factura"
                if fact == ref_lote and item[1] == sku:
                    id_db = item[7]
                    break
            
            if id_db:
                from tkinter import simpledialog
                nueva_cant = simpledialog.askinteger("Editar Cantidad", f"Producto: {values[1]}\nNueva cantidad:", 
                                                    initialvalue=values[2], parent=self.window)
                if nueva_cant is not None and nueva_cant > 0:
                    from data_layer.warehouse_audit import actualizar_abasto_ocr
                    if actualizar_abasto_ocr(id_db, nueva_cant):
                        messagebox.showinfo("Éxito", "Registro actualizado.")
                        self.cargar_datos() # Recargar todo el historial
                        self.on_master_select(None) # Refrescar detalle
                    else:
                        messagebox.showerror("Error", "No se pudo actualizar.")
        else:
            messagebox.showinfo("Aviso", "La edición directa de ítems de Excel no está disponible aquí.\nUsa 'Limpiar Billing' en la pestaña principal para recargar el archivo.")

    def eliminar_lote_completo(self):
        """Elimina todos los registros del documento/archivo seleccionado."""
        selection = self.tree_master.selection()
        if not selection: return
        
        tipo, ref, cant = self.tree_master.item(selection[0], 'values')
        
        if messagebox.askyesno("Confirmar Eliminación Masiva", 
                              f"¿Desea eliminar TODOS los registros ({cant}) de {tipo}: '{ref}'?\n"
                              "Esta acción no se puede deshacer.", parent=self.window):
            
            exito = False
            if tipo == "ABASTO":
                from data_layer.warehouse_audit import eliminar_abastos_por_factura
                # En la BD, S/Factura se guarda como NULL o vacío, pero aquí lo mostramos como S/Factura
                fact_search = "" if ref == "S/Factura" else ref
                exito = eliminar_abastos_por_factura(self.id_sesion, fact_search)
            else:
                # Para Billing, no tenemos eliminar_por_archivo en data_layer aún, 
                # pero podemos añadirlo o usar una consulta directa.
                from utils.db_connector import db_session, run_query
                try:
                    with db_session() as (conn, cursor):
                        run_query(cursor, "DELETE FROM auditoria_bodega_billing WHERE id_sesion = ? AND fuente_archivo = ?", 
                                 (self.id_sesion, ref))
                    exito = True
                except Exception as e:
                    logger.error(f"Error eliminando lote billing: {e}")
                    exito = False
                    
            if exito:
                messagebox.showinfo("Éxito", f"Lote de {tipo} eliminado correctamente.", parent=self.window)
                self.cargar_datos()
                # Limpiar detalle
                for i in self.tree_detail.get_children(): self.tree_detail.delete(i)
                self.canvas.delete("all")
            else:
                messagebox.showerror("Error", f"No se pudo eliminar el lote de {tipo}.", parent=self.window)

