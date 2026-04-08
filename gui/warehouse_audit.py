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
    registrar_billing_excel
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

        title_lbl = tk.Label(header, text="📋 Auditoría de Bodega Central", 
                           font=('Segoe UI', 16, 'bold'), bg=Styles.LIGHT_BG, fg=Styles.PRIMARY_COLOR)
        title_lbl.pack(side='left')

        # Botones de Acción
        btn_frame = ttk.Frame(header, style='Modern.TFrame')
        btn_frame.pack(side='right')

        ttk.Button(btn_frame, text="🚚 Ingresar Abastos (Imagen)", 
                  command=self.abrir_abastos_ocr, style='Modern.TButton').pack(side='left', padx=5)
        
        ttk.Button(btn_frame, text="📄 Cargar Billing (Excel)", 
                  command=self.abrir_billing_excel, style='Modern.TButton').pack(side='left', padx=5)

        ttk.Button(btn_frame, text="🔄 Refrescar", 
                  command=self.cargar_datos, style='Info.TButton').pack(side='left', padx=5)

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

        # Tags para colores
        self.tree.tag_configure('error', foreground='white', background=Styles.DANGER_COLOR)
        self.tree.tag_configure('success', foreground='white', background=Styles.SUCCESS_COLOR)

        # Evento de doble click para edición inline
        self.tree.bind("<Double-1>", self.on_double_click)

    def cargar_datos(self):
        self.id_sesion = obtener_o_crear_sesion_auditoria(self.sucursal)
        items = obtener_items_auditoria(self.id_sesion)
        
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        if not items:
            # Aquí podríamos precargar los productos que están en bodega ahora mismo
            from data_layer.inventory import obtener_todos_los_skus_para_movimiento
            stock_actual = obtener_todos_los_skus_para_movimiento(sucursal_context=self.sucursal)
            for p in stock_actual:
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
                if manual > 0:
                    tag = 'success' if diferencia == 0 else 'error'
                
                self.tree.insert('', 'end', values=(
                    sku, data['nombre'], inicio, abastos, billing, sistema, manual, diferencia
                ), tags=(tag,))

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
                if guardar_cambio_item(self.id_sesion, sku, field, val_int):
                    self.cargar_datos() # Recargar para actualizar cálculos
            except ValueError:
                pass
                
        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", lambda e: entry.destroy())

    def abrir_abastos_ocr(self):
        AbastoOCRDialog(self.main_frame, self.id_sesion, self.cargar_datos)

    def abrir_billing_excel(self):
        BillingExcelDialog(self.main_frame, self.id_sesion, self.cargar_datos)
class AbastoOCRDialog:
    def __init__(self, parent, id_sesion, callback):
        self.window = tk.Toplevel(parent)
        self.window.title("🚚 Registro Asistido de Abastos")
        self.window.geometry("1100x650")
        self.id_sesion = id_sesion
        self.callback = callback
        self.img_path = ""
        self.photo = None
        
        from config import PRODUCTOS_INICIALES
        self.opciones_productos = [f"{item[1]} - {item[0]}" for item in PRODUCTOS_INICIALES]
        self.sku_map = {f"{item[1]} - {item[0]}": item[1] for item in PRODUCTOS_INICIALES}
        
        self.setup_ui()

    def setup_ui(self):
        pane = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        pane.pack(fill='both', expand=True, padx=10, pady=10)
        
        # PANEL IZQUIERDO: Data Entry
        left_frame = ttk.Frame(pane)
        pane.add(left_frame, weight=1)
        
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
        
        btn_add = ttk.Button(form_frame, text="Agregar a la Tabla (Enter)", command=self.agregar_fila)
        btn_add.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.cmb_sku.bind("<Return>", lambda e: self.ent_cant.focus_set())
        self.ent_cant.bind("<Return>", lambda e: self.agregar_fila())
        
        # Botones inferiores
        self.btn_guardar = ttk.Button(left_frame, text="✅ Guardar Documento y Cargar Abastos", style='Success.TButton', command=self.guardar_todo)
        self.btn_guardar.pack(side=tk.BOTTOM, pady=10, fill='x')
        
        ttk.Label(left_frame, text="* Presiona 'Suprimir' o 'Delete' para borrar una fila seleccionada.", foreground="gray").pack(side=tk.BOTTOM, anchor='w')

        # Tabla (ahora puede expandirse sin ocultar el botón arriba)
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
        sb.pack(side='right', fill='y')
        
        self.tree.bind("<Delete>", self.eliminar_fila)
        
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

    def cargar_imagen(self):
        path = filedialog.askopenfilename(filetypes=[("Imágenes", "*.png *.jpg *.jpeg")])
        if not path: return
        
        self.img_path = path
        self.lbl_archivo.config(text=os.path.basename(path), foreground="green")
        
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
        try:
            for item_id in items:
                sku, _, cant = self.tree.item(item_id, 'values')
                registrar_abasto_ocr(self.id_sesion, sku, int(cant), self.img_path)
                guardados += 1
                
            messagebox.showinfo("Éxito", f"Se registraron {guardados} ítems del documento correctamente.")
            self.callback()
            self.window.destroy()
        except Exception as e:
            logger.error(f"Error guardando abastos multiline: {e}")
            messagebox.showerror("Error", f"Ocurrió un error al guardar: {e}")

class BillingExcelDialog:
    def __init__(self, parent, id_sesion, callback):
        self.window = tk.Toplevel(parent)
        self.window.title("📄 Cargar Billing desde Excel")
        self.window.geometry("700x500")
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

        # Mapeo Container
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

        # Bottom Frame
        bottom_frame = ttk.Frame(main)
        bottom_frame.pack(fill='x', pady=5)

        ttk.Label(bottom_frame, text="* Doble click para editar SKU. Solo las filas con SKU mapeado se guardarán.", foreground='gray').pack(side='left')

        self.btn_guardar = ttk.Button(bottom_frame, text="Guardar Registros", command=self.guardar_registros, style='Success.TButton', state='disabled')
        self.btn_guardar.pack(side='right')

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
        excel_to_sku = {item[0].upper(): item[1] for item in PRODUCTOS_INICIALES}
        excel_to_sku['CODILLA'] = excel_to_sku.get('COLILLA', '2-7-11')
        excel_to_sku['CALCAMONIA'] = excel_to_sku.get('STICKER', '2-7-07')

        self.col_totals = {}
        ignore_cols = {'CODIGO_MOVIL', 'NOMBRE_MOVIL', 'CONTRATO', 'AVERÍA', 'AVERIA', 'N_ORDEN', 'FECHA_CIERRE', 'CLOSE_BY', 'N_TAP', 'COLILLA_TV', 'COLILLA_INTERNET', 'SERVICIOS'}

        for col in self.df.columns:
            col_upper = str(col).strip().upper()
            if col_upper in ignore_cols or "FECHA" in col_upper or "NOMBRE" in col_upper or "TITULAR" in col_upper:
                continue
            
            total = pd.to_numeric(self.df[col], errors='coerce').fillna(0).sum()
            
            if total > 0:
                sku_mapeado = excel_to_sku.get(col_upper, "")
                self.col_totals[col] = total
                self.tree.insert('', 'end', values=(col, int(total), sku_mapeado))
        
    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        
        column = self.tree.identify_column(event.x)
        if column != "#3": return 
        
        item_id = self.tree.identify_row(event.y)
        values = self.tree.item(item_id, 'values')
        
        x, y, w, h = self.tree.bbox(item_id, column)
        
        entry = ttk.Entry(self.tree)
        entry.insert(0, values[2])
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
        else:
            messagebox.showwarning("Advertencia", "No se registró ningún consumo. Asigne un SKU válido a las columnas.")
