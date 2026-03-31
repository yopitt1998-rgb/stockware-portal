import tkinter as tk
from tkinter import ttk, messagebox, Canvas, Scrollbar
from datetime import date, datetime, timedelta
import os
import threading


from ..styles import Styles
from ..utils import darken_color, mostrar_mensaje_emergente
from utils.logger import get_logger

logger = get_logger(__name__)

from config import DATABASE_NAME, PRODUCTOS_CON_CODIGO_BARRA
from database import (
    obtener_inventario, obtener_todos_los_skus_para_movimiento,
    anadir_producto, registrar_movimiento_gui, eliminar_producto,
    obtener_asignacion_movil, registrar_prestamo_santiago,
    obtener_prestamos_activos, registrar_devolucion_santiago,
    obtener_historial_producto, limpiar_productos_duplicados,
    limpiar_duplicados_asignacion_moviles,
    TIPO_MOVIMIENTO_DESCARTE, obtener_stock_actual_y_moviles,
    obtener_abastos_resumen, obtener_detalle_abasto, actualizar_movimiento_abasto,
    obtener_nombres_moviles,
    obtener_consumos_pendientes,
    obtener_info_serial, actualizar_ubicacion_serial
)
import pandas as pd
from tkinter import filedialog
# Note: Some imports might be missing, I'll add them as I discover needs during implementation (e.g. exportar_a_csv)

from ..reconciliation import abrir_ventana_conciliacion_excel
from ..abasto import AbastoWindow
from ..abasto_scanner import AbastoScannerWindow  # NUEVO: Sistema de escaneo universal
from ..mobile_output_scanner import MobileOutputScannerWindow  # NUEVO: Salida móvil por escaneo
from ..mobiles import MobilesManager
from ..consumption import ConsumoTecnicoWindow
from ..pdf_generator import generar_vale_despacho
from database import obtener_configuracion
from config import PRODUCTOS_INICIALES
from .movements import (
    IndividualOutputWindow,
    MobileOutputWindow,
    ConciliacionPaquetesWindow
)
from .faltantes_dashboard import FaltantesDashboardWindow
from ..utils import mostrar_cargando_async

class InventoryTab:
    def __init__(self, notebook, main_app):
        self.notebook = notebook
        self.main_app = main_app
        self.master = main_app.master
        
        self.ubicacion_var = tk.StringVar()
        self.tabla = None
        
        self.create_widgets()

    def _mostrar_cargando_async(self, ventana, funcion_carga, callback_exito):
        """Muestra pantalla de carga y ejecuta carga de datos en hilo"""
        frame_carga = tk.Frame(ventana, bg=ventana.cget('bg'))
        frame_carga.pack(fill='both', expand=True)
        
        # Centered loading content
        content_frame = tk.Frame(frame_carga, bg=ventana.cget('bg'))
        content_frame.pack(expand=True)
        
        tk.Label(content_frame, text="🔄", font=('Segoe UI', 30), 
                bg=ventana.cget('bg'), fg='#7f8c8d').pack(pady=10)
        tk.Label(content_frame, text="Cargando datos...", font=('Segoe UI', 12), 
                bg=ventana.cget('bg'), fg='#7f8c8d').pack()
        
        def run_thread():
            try:
                # Simular un pequeño delay para que la UI se renderice bien si la carga es muuuy rápida (opcional, pero ayuda al UX)
                import time; time.sleep(0.1) 
                datos = funcion_carga()
                if ventana.winfo_exists():
                    self.master.after(0, lambda: self._finalizar_carga(ventana, frame_carga, callback_exito, datos))
            except Exception as e:
                logger.error(f"Error async: {e}")
                import traceback; traceback.print_exc()
                if ventana.winfo_exists():
                    self.master.after(0, lambda: self._manejar_error_carga(ventana, e))

        threading.Thread(target=run_thread, daemon=True).start()

    def _finalizar_carga(self, ventana, frame_carga, callback_exito, datos):
        if not ventana.winfo_exists(): return
        frame_carga.destroy()
        callback_exito(datos)
        
    def _manejar_error_carga(self, ventana, error):
        mostrar_mensaje_emergente(ventana, "Error", f"Error cargando datos: {error}", "error")
        ventana.destroy()

    def abrir_conciliacion(self):
        self.conciliacion_window = abrir_ventana_conciliacion_excel(self.main_app, mode='excel')

    def mostrar_stock_critico(self):
        """Muestra productos con stock bajo el mínimo"""
        ventana = tk.Toplevel(self.master)
        ventana.title("⚠️ Stock Crítico")
        ventana.geometry("700x500")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header
        header_frame = tk.Frame(ventana, bg=Styles.ACCENT_COLOR, height=70)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="⚠️ PRODUCTOS CON STOCK CRÍTICO", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.ACCENT_COLOR, fg='white').pack(pady=20)
        
        # Info
        info_frame = tk.Frame(ventana, bg='#FFF3E0', padx=10, pady=8)
        info_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(info_frame, text="📊 Productos con cantidad inferior al stock mínimo configurado",
                font=('Segoe UI', 9), bg='#FFF3E0', fg='#E65100').pack()
        
        # Tabla
        table_frame = tk.Frame(ventana, bg='#f8f9fa')
        table_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('Producto', 'SKU', 'Stock Actual', 'M\u00ednimo', 'Diferencia')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        tree.heading('Producto', text='PRODUCTO')
        tree.heading('SKU', text='SKU')
        tree.heading('Stock Actual', text='STOCK ACTUAL')
        tree.heading('Mínimo', text='MÍNIMO')
        tree.heading('Diferencia', text='FALTANTE')
        
        tree.column('Producto', width=250)
        tree.column('SKU', width=100, anchor='center')
        tree.column('Stock Actual', width=100, anchor='center')
        tree.column('Mínimo', width=100, anchor='center')
        tree.column('Diferencia', width=100, anchor='center')
        
        scroll_y = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll_y.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        
        # Cargar datos
        datos = obtener_inventario()
        criticos = [(nombre, sku, cantidad, min_stock, min_stock - cantidad) 
                    for id, nombre, sku, cantidad, ubicacion, categoria, marca, min_stock in datos
                    if ubicacion == 'BODEGA' and cantidad < min_stock]
        
        if not criticos:
            tree.insert('', 'end', values=('', '', '✅ Sin productos críticos', '', ''))
        else:
            for nombre, sku, stock,  minimo, faltante in sorted(criticos, key=lambda x: x[4], reverse=True):
                tree.insert('', 'end', values=(nombre, sku, stock, minimo, faltante), tags=('critico',))
        
        # Tag para resaltar
        tree.tag_configure('critico', background='#FFCDD2')
        
        # Botón cerrar
        tk.Button(ventana, text="Cerrar", command=ventana.destroy,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=8).pack(pady=20)

    def create_widgets(self):
        """Crear pestaña de Gestión de Inventario"""
        inventory_frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(inventory_frame, text="📦 Gestión de Inventario")
        
        # Controles superiores
        controls_frame = ttk.Frame(inventory_frame, style='Modern.TFrame')
        controls_frame.pack(fill='x', padx=20, pady=20)
        
        # Botones de gestión - SIMPLIFICADO
        management_buttons = [
            ("➕ Nuevo Producto", self.abrir_ventana_anadir, Styles.SUCCESS_COLOR),
            ("🏷️ Gestionar Códigos", self.abrir_gestion_codigos, '#4CAF50'),
            ("🔫 Abasto por Escaneo", self.abrir_ventana_abasto_scanner, '#00C853'),
            ("🔫 Salida Móvil Scanner", self.abrir_ventana_salida_movil_scanner, '#FF6F00'),
            ("❌ Eliminar Producto", self.abrir_ventana_eliminar, Styles.ACCENT_COLOR),
            ("🔄 Traslado", self.abrir_ventana_traslado, Styles.SECONDARY_COLOR),
            ("🚚 Gestionar Móviles", self.abrir_ventana_gestion_moviles, '#E91E63'),
            ("🚩 Historial Faltantes", self.abrir_historial_faltantes, '#d32f2f'), # NUEVO
            ("⏪ Reversar Consumo", self.abrir_reverso_consumo, '#00BCD4'), # NUEVA FUNCION
            ("🧹 Limpieza Avanzada", self.mostrar_herramientas_limpieza, '#9C27B0')
        ]
        
        for i, (text, command, color) in enumerate(management_buttons):
            row = i // 4
            col = i % 4
            btn = tk.Button(controls_frame, text=text, command=command,
                          bg=color, fg='white', font=('Segoe UI', 10, 'bold'),
                          relief='flat', bd=0, padx=15, pady=10, cursor='hand2')
            btn.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
            
            # Use functools.partial or lambda with default args for safe closure binding
            # Simplified manual binding here
            def on_enter(e, b=btn): b.configure(bg=darken_color(b.cget('bg')))
            def on_leave(e, b=btn, c=color): b.configure(bg=c)
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            
            controls_frame.columnconfigure(col, weight=1)

        # Filtros
        filters_frame = ttk.Frame(inventory_frame, style='Modern.TFrame')
        filters_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(filters_frame, text="Filtrar por Ubicación:", style='Subtitle.TLabel').pack(side='left', padx=(0, 10))
        self.ubicacion_var.set("TODAS")
        ubicaciones = ["TODAS", "BODEGA", "DESCARTE"]
        self.ubicacion_combo = ttk.Combobox(filters_frame, textvariable=self.ubicacion_var, values=ubicaciones, state="readonly", width=15)
        self.ubicacion_combo.pack(side='left', padx=(0, 20))
        self.ubicacion_combo.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtro_tabla())

        ttk.Label(filters_frame, text="Buscar:", style='Subtitle.TLabel').pack(side='left', padx=(0, 10))
        self.filtro_entry = ttk.Entry(filters_frame, width=40, style='Modern.TEntry')
        self.filtro_entry.pack(side='left', padx=5, fill='x', expand=True)
        self.filtro_entry.bind('<KeyRelease>', lambda e: self.aplicar_filtro_tabla())
        
        # Botón de actualizar
        refresh_btn = tk.Button(filters_frame, text="🔄 Actualizar", command=self.cargar_datos_tabla,
                              bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                              relief='flat', bd=0, padx=15, pady=5)
        refresh_btn.pack(side='right', padx=5)
        def on_enter_refresh(e): refresh_btn.configure(bg=darken_color(Styles.INFO_COLOR))
        def on_leave_refresh(e): refresh_btn.configure(bg=Styles.INFO_COLOR)
        refresh_btn.bind("<Enter>", on_enter_refresh)
        refresh_btn.bind("<Leave>", on_leave_refresh)

        # Botón de limpieza de duplicados
        limpiar_btn = tk.Button(filters_frame, text="🧹 Limpiar Duplicados", command=self.ejecutar_limpieza_duplicados,
                              bg=Styles.WARNING_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                              relief='flat', bd=0, padx=15, pady=5)
        limpiar_btn.pack(side='right', padx=5)
        def on_enter_limpiar(e): limpiar_btn.configure(bg=darken_color(Styles.WARNING_COLOR))
        def on_leave_limpiar(e): limpiar_btn.configure(bg=Styles.WARNING_COLOR)
        limpiar_btn.bind("<Enter>", on_enter_limpiar)
        limpiar_btn.bind("<Leave>", on_leave_limpiar)

        # Tabla de inventario
        table_frame = ttk.Frame(inventory_frame, style='Modern.TFrame')
        table_frame.pack(fill='both', expand=True, padx=20, pady=10)
        # Tabla Principal de Inventario
        columns = ("ID", "Nombre", "SKU", "Cantidad", "Ubicación", "Categoría", "Marca", "Min. Stock")
        self.tabla = ttk.Treeview(table_frame, columns=columns, show='headings', style='Modern.Treeview')
        
        # Configuración de columnas
        self.tabla.heading("ID", text="ID")
        self.tabla.heading("Nombre", text="NOMBRE DEL PRODUCTO")
        self.tabla.heading("SKU", text="SKU")
        self.tabla.heading("Cantidad", text="CANTIDAD")
        self.tabla.heading("Ubicación", text="UBICACIÓN")
        self.tabla.heading("Categoría", text="CATEGORÍA")
        self.tabla.heading("Marca", text="MARCA")
        self.tabla.heading("Min. Stock", text="MIN. STOCK")
        
        self.tabla.column("ID", width=40, anchor='center')
        self.tabla.column("Nombre", width=250)
        self.tabla.column("SKU", width=120, anchor='center')
        self.tabla.column("Cantidad", width=100, anchor='center')
        self.tabla.column("Ubicación", width=120, anchor='center')
        self.tabla.column("Categoría", width=120, anchor='center')
        self.tabla.column("Marca", width=120, anchor='center')
        self.tabla.column("Min. Stock", width=80, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        
        self.tabla.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Configurar scroll suave del mouse
        def on_mousewheel(event):
            self.tabla.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        # Vincular el scroll del mouse
        self.tabla.bind("<MouseWheel>", on_mousewheel)
        
        # Bindeo para ver el historial al hacer doble click
        self.tabla.bind("<Double-1>", self.on_item_double_click)
        
        # Cargar datos iniciales
        self.cargar_datos_tabla()

    def on_item_double_click(self, event):
        """Muestra historial al hacer doble click"""
        selection = self.tabla.selection()
        if not selection:
            return
        
        item = self.tabla.item(selection[0])
        valores = item['values']
        if valores and len(valores) > 2:
            sku = valores[2] # columna SKU es index 2
            self.abrir_ventana_historial(sku)
            
    def cargar_datos_tabla(self):
        """Carga datos en la tabla de inventario en un hilo separado"""
        def run_load():
            try:
                # Obtener datos de la base de datos (Pesado)
                datos = obtener_inventario()
                
                # Programar actualización de la UI en el hilo principal
                self.master.after(0, lambda: self._aplicar_datos_tabla_ui(datos))
            except Exception as e:
                logger.critical(f"❌ Error crítico cargando tabla de inventario: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=run_load, daemon=True).start()

    def _aplicar_datos_tabla_ui(self, datos):
        """Aplica los datos obtenidos a la tabla (Treeview)"""
        if not self.tabla.winfo_exists():
            return

        # Guardar para filtros locales
        self.datos_completos = datos
        
        # Limpiar tabla actual
        for item in self.tabla.get_children():
            self.tabla.delete(item)
            
        if not datos:
            self.tabla.insert('', tk.END, values=("", "No hay datos de inventario", "", "", "", "", "", ""))
            return

        # Aplicar filtros si existen (esto inserta en la tabla)
        self.aplicar_filtro_tabla()
        
    def aplicar_filtro_tabla(self):
        """Filtra la tabla según criterio de búsqueda y ubicación"""
        if not hasattr(self, 'datos_completos') or not self.datos_completos:
            return
            
        busqueda = self.filtro_entry.get().lower()
        ubicacion_filtro = self.ubicacion_var.get()
        
        # Limpiar tabla
        for item in self.tabla.get_children():
            self.tabla.delete(item)
            
        for id, nombre, sku, cantidad, ubicacion, categoria, marca, min_stock in self.datos_completos:
            match_texto = busqueda in nombre.lower() or busqueda in str(sku).lower()
            
            match_ubicacion = True
            if ubicacion_filtro != "TODAS":
                if ubicacion_filtro == "BODEGA" and ubicacion != "BODEGA":
                    match_ubicacion = False
                elif ubicacion_filtro == "DESCARTE" and ubicacion != "DESCARTE":
                    match_ubicacion = False
                # Aquí podríamos añadir más lógica para móviles si fuera necesario
            
            if match_texto and match_ubicacion:
                # Llenar la tabla
                tags = ()
                if ubicacion == 'BODEGA':
                    if cantidad < min_stock and cantidad > 0:
                        tags = ('bajo_stock',)
                    elif cantidad == 0:
                        tags = ('agotado',)
                elif ubicacion == 'DESCARTE':
                    tags = ('descarte',)
                    
                self.tabla.insert('', tk.END, values=(id, nombre, sku, cantidad, ubicacion, categoria, marca, min_stock), tags=tags)
                
    def ejecutar_limpieza_duplicados(self):
        """Ejecuta la limpieza completa de duplicados"""
        # Limpiar productos duplicados
        eliminados_prod, mensaje_prod = limpiar_productos_duplicados()
        
        # Limpiar duplicados en asignación móviles
        exito_asign, mensaje_asign = limpiar_duplicados_asignacion_moviles()
        
        # Mostrar resultados
        mensaje_final = f"Limpieza completada:\n\n"
        mensaje_final += f"📦 Productos: {mensaje_prod}\n"
        mensaje_final += f"🚚 Asignación Móviles: {mensaje_asign}"
        
        mostrar_mensaje_emergente(self.master, "Limpieza de Duplicados", mensaje_final, "success")
        self.cargar_datos_tabla()
        # Actualizar dashboard si es posible
        if hasattr(self.main_app, 'dashboard_tab'):
             self.main_app.dashboard_tab.actualizar_metricas()

    def abrir_historial_faltantes(self):
        """Abre la ventana del historial de faltantes"""
        from .faltantes_dashboard import FaltantesDashboardWindow
        FaltantesDashboardWindow(self.main_app)

    def abrir_ventana_gestion_moviles(self):
        """Abre la ventana de gestión de móviles"""
        MobilesManager(self.master)
        # No recargamos nada aquí, pero las ventanas de movimientos se recargaran al abrirse.

    def abrir_ventana_consumo(self):
        """Abre la ventana de registro de consumo de técnico"""
        ConsumoTecnicoWindow(self.master, refresh_callback=self.cargar_datos_tabla)

    def abrir_ventana_anadir(self):
        """Abre ventana para añadir producto"""
        ventana = tk.Toplevel(self.master)
        ventana.title("➕ Añadir Nuevo Producto")
        ventana.geometry("600x650")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="➕ AÑADIR NUEVO PRODUCTO", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # --- Barcode Scanner ---
        scan_frame = tk.Frame(ventana, bg='#f8f9fa', pady=5)
        scan_frame.pack(fill='x', padx=20)
        
        tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(side='left')
        scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor=Styles.ACCENT_COLOR)
        scan_entry.pack(side='left', padx=10)
        
        tk.Label(scan_frame, text="(Presiona Enter)", font=('Segoe UI', 9), bg='#f8f9fa', fg='gray').pack(side='left')
        
        # --- Frame Lista con Scrollbar ---por si los campos no caben
        canvas = tk.Canvas(ventana, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=canvas.yview)
        frame_principal = tk.Frame(canvas, padx=20, pady=20, bg='#f8f9fa')
        
        canvas.create_window((0, 0), window=frame_principal, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(1, width=event.width) # Adjust inner frame width
        canvas.bind("<Configure>", on_configure)
        
        # Campos del formulario
        tk.Label(frame_principal, text="Nombre del Producto:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        nombre_entry = tk.Entry(frame_principal, width=50, font=('Segoe UI', 10))
        nombre_entry.pack(fill='x', pady=(0, 15))
        
        tk.Label(frame_principal, text="SKU:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        sku_entry = tk.Entry(frame_principal, width=20, font=('Segoe UI', 10))
        sku_entry.pack(fill='x', pady=(0, 15))
        
        tk.Label(frame_principal, text="Cantidad Inicial:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        cantidad_entry = tk.Entry(frame_principal, width=10, font=('Segoe UI', 10))
        cantidad_entry.insert(0, "0")
        cantidad_entry.pack(fill='x', pady=(0, 15))
        
        tk.Label(frame_principal, text="Secuencia de Vista:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        secuencia_entry = tk.Entry(frame_principal, width=10, font=('Segoe UI', 10))
        secuencia_entry.pack(fill='x', pady=(0, 15))

        tk.Label(frame_principal, text="Categoría:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        categoria_entry = ttk.Combobox(frame_principal, values=["General", "FIBRA", "HERRAMIENTAS", "EQUIPOS", "CONECTIVIDAD", "FERRETERIA", "VARIOS"], font=('Segoe UI', 10))
        categoria_entry.set("General")
        categoria_entry.pack(fill='x', pady=(0, 15))

        tk.Label(frame_principal, text="Marca:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        marca_entry = tk.Entry(frame_principal, width=50, font=('Segoe UI', 10))
        marca_entry.insert(0, "N/A")
        marca_entry.pack(fill='x', pady=(0, 15))

        tk.Label(frame_principal, text="Mínimo Stock (Alerta):", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 5))
        minimo_entry = tk.Entry(frame_principal, width=10, font=('Segoe UI', 10))
        minimo_entry.insert(0, "10")
        minimo_entry.pack(fill='x', pady=(0, 15))
        
        def guardar_producto():
            nombre = nombre_entry.get().strip()
            sku = sku_entry.get().strip()
            cantidad_text = cantidad_entry.get().strip()
            secuencia = secuencia_entry.get().strip()
            
            if not nombre:
                mostrar_mensaje_emergente(ventana, "Error", "El nombre del producto es obligatorio.", "error")
                return
                
            if not sku:
                mostrar_mensaje_emergente(ventana, "Error", "El SKU es obligatorio.", "error")
                return
                
            if not secuencia:
                mostrar_mensaje_emergente(ventana, "Error", "La secuencia de vista es obligatoria.", "error")
                return
                
            try:
                cantidad = int(cantidad_text)
                if cantidad < 0:
                    mostrar_mensaje_emergente(ventana, "Error", "La cantidad no puede ser negativa.", "error")
                    return
            except ValueError:
                mostrar_mensaje_emergente(ventana, "Error", "La cantidad debe ser un número válido.", "error")
                return
            
            try:
                minimo_stock = int(minimo_entry.get().strip() or "10")
                if minimo_stock < 1: minimo_stock = 1
            except ValueError:
                minimo_stock = 10
            
            categoria = categoria_entry.get().strip() or "General"
            marca = marca_entry.get().strip() or "N/A"

            # Guardar el producto
            exito, mensaje = anadir_producto(nombre, sku, cantidad, "BODEGA", secuencia, minimo_stock, categoria, marca)
            
            if exito:
                mostrar_mensaje_emergente(self.master, "Éxito", mensaje, "success")
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
            else:
                mostrar_mensaje_emergente(ventana, "Error", mensaje, "error")
        
        # Botones
        frame_botones = tk.Frame(frame_principal, bg='#f8f9fa')
        frame_botones.pack(fill='x', pady=20)
        
        tk.Button(frame_botones, text="Guardar Producto", command=guardar_producto,
                bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                relief='flat', bd=0, padx=20, pady=10).pack(side=tk.LEFT, padx=10)
        
        tk.Button(frame_botones, text="Cancelar", command=ventana.destroy,
                bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                relief='flat', bd=0, padx=20, pady=10).pack(side=tk.RIGHT, padx=10)

    def abrir_ventana_salida_individual(self):
        """Abre ventana para salida individual desde bodega (Refactored)"""
        IndividualOutputWindow(self.main_app, on_close_callback=self.cargar_datos_tabla, mode='SALIDA')


    def abrir_ventana_eliminar(self):
        """Abre ventana para eliminar producto con interfaz moderna (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("❌ Eliminar Producto")
        ventana.geometry("600x500")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        def construir_ui(productos):
            if not productos:
                mostrar_mensaje_emergente(ventana, "Información", "No hay productos registrados.", "info")
                ventana.destroy()
                return

            # Header moderno
            header_frame = tk.Frame(ventana, bg=Styles.ACCENT_COLOR, height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="❌ ELIMINAR PRODUCTO", 
                    font=('Segoe UI', 16, 'bold'), bg=Styles.ACCENT_COLOR, fg='white').pack(pady=20)
            
            # Frame de contenido
            frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
            frame_contenido.pack(fill='both', expand=True)
            
            # Selección de producto
            tk.Label(frame_contenido, text="Seleccionar Producto a Eliminar:", 
                    font=('Segoe UI', 12, 'bold'), bg='#f8f9fa').pack(anchor='w', pady=(0, 10))
            
            productos_dict = {f"{nombre} ({sku}) - Stock: {stock}": sku for nombre, sku, stock in productos}
            
            sku_var = tk.StringVar(ventana)
            producto_combo = ttk.Combobox(frame_contenido, textvariable=sku_var, 
                                        values=list(productos_dict.keys()), 
                                        state="readonly", width=70, font=('Segoe UI', 10))
            producto_combo.pack(fill='x', pady=(0, 20))
            
            # Información de advertencia
            warning_frame = tk.Frame(frame_contenido, bg='#FFEBEE', relief='raised', borderwidth=1, padx=15, pady=15)
            warning_frame.pack(fill='x', pady=(0, 20))
            
            tk.Label(warning_frame, text="⚠️ ADVERTENCIA", font=('Segoe UI', 12, 'bold'), 
                    bg='#FFEBEE', fg='#D32F2F').pack(anchor='w')
            tk.Label(warning_frame, text="Esta acción eliminará permanentemente el producto de todas las ubicaciones,", 
                    font=('Segoe UI', 9), bg='#FFEBEE', fg='#D32F2F', justify='left').pack(anchor='w')
            tk.Label(warning_frame, text="incluyendo su historial de movimientos y asignaciones a móviles.", 
                    font=('Segoe UI', 9), bg='#FFEBEE', fg='#D32F2F', justify='left').pack(anchor='w')
            tk.Label(warning_frame, text="Esta acción NO se puede deshacer.", 
                    font=('Segoe UI', 10, 'bold'), bg='#FFEBEE', fg='#D32F2F').pack(anchor='w', pady=(5, 0))
            
            # Botones
            frame_botones = tk.Frame(frame_contenido, bg='#f8f9fa')
            frame_botones.pack(fill='x', pady=20)
            
            def confirmar_eliminacion():
                producto_seleccionado = sku_var.get()
                if not producto_seleccionado:
                    mostrar_mensaje_emergente(ventana, "Error", "Debe seleccionar un producto para eliminar.", "error")
                    return
                
                # Confirmación final
                confirmacion = messagebox.askyesno(
                    "Confirmar Eliminación", 
                    f"¿Está seguro que desea eliminar permanentemente:\n\n{producto_seleccionado}\n\nEsta acción NO se puede deshacer.",
                    icon='warning',
                    parent=ventana
                )
                
                if confirmacion:
                    sku = productos_dict[producto_seleccionado]
                    exito, mensaje = eliminar_producto(sku)
                    
                    if exito:
                        mostrar_mensaje_emergente(self.master, "Éxito", mensaje, "success")
                        self.cargar_datos_tabla()
                        if hasattr(self.main_app, 'dashboard_tab'):
                            self.main_app.dashboard_tab.actualizar_metricas()
                        ventana.destroy()
                    else:
                        mostrar_mensaje_emergente(ventana, "Error", mensaje, "error")
            
            tk.Button(frame_botones, text="🗑️ Confirmar Eliminación", command=confirmar_eliminacion,
                    bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                    relief='flat', bd=0, padx=20, pady=10).pack(side=tk.LEFT, padx=10)
            
            tk.Button(frame_botones, text="Cancelar", command=ventana.destroy,
                    bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                    relief='flat', bd=0, padx=20, pady=10).pack(side=tk.RIGHT, padx=10)

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, obtener_todos_los_skus_para_movimiento, construir_ui)

    def abrir_ventana_descarte(self):
        """Abre ventana para descarte (Refactored)"""
        IndividualOutputWindow(self.main_app, on_close_callback=self.cargar_datos_tabla, mode='DESCARTE')

    def abrir_ventana_traslado(self):
        """Abre ventana para traslado entre móviles con interfaz moderna (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("🔄 Traslado entre Móviles")
        ventana.geometry("900x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        def construir_ui(moviles_db):
            # Header moderno
            header_frame = tk.Frame(ventana, bg=Styles.SECONDARY_COLOR, height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="🔄 TRASLADO ENTRE MÓVILES", 
                    font=('Segoe UI', 16, 'bold'), bg=Styles.SECONDARY_COLOR, fg='white').pack(pady=20)
            
            # Frame de selectores
            frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#E3F2FD')
            frame_selector.pack(fill='x')
            
            # Móvil origen
            tk.Label(frame_selector, text="Móvil Origen:", font=('Segoe UI', 10, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT)
            movil_origen_combo = ttk.Combobox(frame_selector, values=moviles_db, state="readonly", width=15)
            movil_origen_combo.set("--- Seleccionar ---")
            movil_origen_combo.pack(side=tk.LEFT, padx=10)
            
            # Móvil destino
            tk.Label(frame_selector, text="Móvil Destino:", font=('Segoe UI', 10, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(20, 5))
            movil_destino_combo = ttk.Combobox(frame_selector, values=moviles_db, state="readonly", width=15)
            movil_destino_combo.set("--- Seleccionar ---")
            movil_destino_combo.pack(side=tk.LEFT, padx=10)
            
            # Fecha
            tk.Label(frame_selector, text="Fecha (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(20, 5))
            fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
            fecha_entry.insert(0, date.today().isoformat())
            fecha_entry.pack(side=tk.LEFT, padx=10)

            # --- Barcode Scanner ---
            scan_frame = tk.Frame(ventana, bg='#f8f9fa', pady=5)
            scan_frame.pack(fill='x', padx=20)
            
            tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg=Styles.SECONDARY_COLOR).pack(side='left')
            scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor=Styles.SECONDARY_COLOR)
            scan_entry.pack(side='left', padx=10)
            
            tk.Label(scan_frame, text="(Presiona Enter)", font=('Segoe UI', 9), bg='#f8f9fa', fg='gray').pack(side='left')
            
            # Tabla de productos
            canvas = tk.Canvas(ventana)
            scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=canvas.yview)
            frame_productos = tk.Frame(canvas)
            canvas.create_window((0, 0), window=frame_productos, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=10)
            scrollbar.pack(side="right", fill="y")
            
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            canvas.bind("<MouseWheel>", on_mousewheel)
            frame_productos.bind("<MouseWheel>", on_mousewheel)
            
            ventana.entry_vars = {} # Use ventana.entry_vars for scanner access
            
            # Encabezados (these are static, will be cleared and re-added)
            header_labels = []
            header_labels.append(tk.Label(frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')))
            header_labels.append(tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')))
            header_labels.append(tk.Label(frame_productos, text="MAC / Serial", font=('Segoe UI', 10, 'bold'), fg='blue'))
            header_labels.append(tk.Label(frame_productos, text="Seleccionar", font=('Segoe UI', 10, 'bold')))
            
            for i, label in enumerate(header_labels):
                label.grid(row=0, column=i, padx=5, pady=5, sticky='w')

            # Store products data for scanner validation
            productos_en_movil_origen = []

            def cargar_productos_movil(event=None):
                nonlocal productos_en_movil_origen # Declare intent to modify outer scope variable
                movil_origen = movil_origen_combo.get()
                if movil_origen == "--- Seleccionar ---":
                    # Clear all product entries and scanner data if no mobile is selected
                    for widget in frame_productos.winfo_children():
                        if int(widget.grid_info().get("row", 0)) > 0:
                            widget.destroy()
                    ventana.entry_vars.clear()
                    productos_en_movil_origen.clear()
                    return
                
                # Limpiar tabla (except headers)
                for widget in frame_productos.winfo_children():
                    if int(widget.grid_info().get("row", 0)) > 0:
                        widget.destroy()
                
                ventana.entry_vars.clear()
                productos_en_movil_origen.clear() # Clear previous data
                
                def renderizar_productos(productos_asignados):
                    from config import PRODUCTOS_CON_CODIGO_BARRA
                    if not productos_asignados:
                        tk.Label(frame_productos, text="No hay productos asignados a este móvil", 
                                font=('Segoe UI', 10), fg='red').grid(row=1, column=0, columnspan=4, padx=10, pady=10)
                        return
                    
                    # Filtrar solo equipos que tengan serial/MAC
                    equipos_asignados = [p for p in productos_asignados if p[1] in PRODUCTOS_CON_CODIGO_BARRA]
                    
                    if not equipos_asignados:
                        tk.Label(frame_productos, text="No hay equipos (con MAC) asignados a este móvil", 
                                font=('Segoe UI', 10), fg='orange').grid(row=1, column=0, columnspan=4, padx=10, pady=10)
                        return

                    fila = 1
                    for nombre, sku, cantidad in equipos_asignados:
                        # Obtener las series/MACs individuales para este SKU en este móvil
                        from database import obtener_series_por_sku_y_ubicacion
                        series = obtener_series_por_sku_y_ubicacion(sku, movil_origen)
                        
                        if not series:
                            # Caso borde: SKU es equipo pero no hay series registradas en tabla series_registradas
                            tk.Label(frame_productos, text=nombre, anchor='w', font=('Segoe UI', 9)).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
                            tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
                            tk.Label(frame_productos, text="Sin series en BD", font=('Segoe UI', 9, 'italic'), fg='gray').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
                            fila += 1
                            continue

                        for s_num, m_num in series:
                            # Identificador prioritario: MAC, si no hay MAC, Serial
                            display_id = m_num if m_num and m_num != 'N/A' else s_num
                            
                            tk.Label(frame_productos, text=nombre, anchor='w', font=('Segoe UI', 9)).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
                            tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
                            tk.Label(frame_productos, text=display_id, anchor='center', font=('Segoe UI', 9), fg='blue').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
                            
                            var = tk.BooleanVar()
                            chk = tk.Checkbutton(frame_productos, variable=var, bg='white')
                            chk.grid(row=fila, column=3, padx=5, pady=2)
                            
                            # Guardar info para procesamiento: (sku, id_serie)
                            ventana.entry_vars[f"{sku}_{display_id}"] = (var, sku, display_id)
                            fila += 1
                    
                    frame_productos.update_idletasks()
                    canvas.config(scrollregion=canvas.bbox("all"))

                # Convertido a async para evitar bloqueos UI
                self._mostrar_cargando_async(ventana, lambda: obtener_asignacion_movil(movil_origen), renderizar_productos)
            
            movil_origen_combo.bind("<<ComboboxSelected>>", cargar_productos_movil)
            frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

            # Scanner logic (Modificado para alternar checkboxes)
            def real_scan_handler(event):
                codigo = scan_entry.get().strip().upper()
                if not codigo: return

                encontrado = False
                for key, data in ventana.entry_vars.items():
                    var, sku, display_id = data
                    if codigo == display_id:
                        var.set(not var.get()) # Alternar selección
                        encontrado = True
                        break
                
                if not encontrado:
                    messagebox.showwarning("No Encontrado", f"El equipo con MAC/Serial '{codigo}' no está listado para este móvil.", master=ventana)
                
                scan_entry.delete(0, tk.END)

            scan_entry.bind('<Return>', real_scan_handler)
            scan_entry.focus_set()
            
            def procesar_traslado():
                movil_origen = movil_origen_combo.get()
                movil_destino = movil_destino_combo.get()
                fecha_evento = fecha_entry.get().strip()
                
                if movil_origen == "--- Seleccionar ---" or movil_destino == "--- Seleccionar ---":
                    mostrar_mensaje_emergente(ventana, "Error", "Debe seleccionar ambos móviles (origen y destino).", "error")
                    return
                    
                if movil_origen == movil_destino:
                    mostrar_mensaje_emergente(ventana, "Error", "El móvil origen y destino no pueden ser el mismo.", "error")
                    return
                    
                if not fecha_evento:
                    mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
                    return
    
                exitos = 0
                errores = 0
                mensaje_error = ""
    
                from database import registrar_movimiento_gui, actualizar_ubicacion_serial

                for key, data in ventana.entry_vars.items():
                    var, sku, display_id = data
                    if var.get(): # Si está seleccionado
                        try:
                            # 1. Actualizar ubicación física del serial en la BD
                            exito_u, msg_u = actualizar_ubicacion_serial(display_id, movil_destino)
                            
                            if not exito_u:
                                errores += 1
                                mensaje_error += f"\n- {display_id}: {msg_u}"
                                continue

                            # 2. Registrar movimientos de inventario por cantidad
                            # Retorno desde origen
                            exito1, mensaje1 = registrar_movimiento_gui(
                                sku, 'RETORNO_MOVIL', 1, movil_origen, fecha_evento, 
                                None, f"TRASLADO A {movil_destino}", seriales=[display_id]
                            )
                            # Salida a destino
                            exito2, mensaje2 = registrar_movimiento_gui(
                                sku, 'SALIDA_MOVIL', 1, movil_destino, fecha_evento, 
                                None, f"TRASLADO DESDE {movil_origen}", seriales=[display_id]
                            )
                            
                            if exito1 and exito2:
                                exitos += 1
                            else:
                                errores += 1
                                if not exito1: mensaje_error += f"\n- {display_id} (Origen): {mensaje1}"
                                if not exito2: mensaje_error += f"\n- {display_id} (Destino): {mensaje2}"

                        except Exception as e:
                            errores += 1
                            mensaje_error += f"\n- {display_id} (Error): {e}"
    
                if exitos > 0 or errores > 0:
                    if errores > 0:
                        mostrar_mensaje_emergente(ventana, "Proceso Finalizado con Errores", 
                                                    f"Se completaron {exitos} traslados y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                    "warning")
                    else:
                        mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} traslados exitosamente.", "success")
                elif exitos == 0 and errores == 0:
                    mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")
    
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
    
            tk.Button(ventana, text="Procesar Traslado", 
                    command=procesar_traslado, 
                    bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)
        
        # Iniciar carga async de moviles
        self._mostrar_cargando_async(ventana, obtener_nombres_moviles, construir_ui)

    def abrir_ventana_prestamo_bodega(self):
        """Abre ventana para transferencia a Santiago con interfaz moderna (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📤 Transferencia a Santiago")
        ventana.geometry("800x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        def construir_ui(productos):
            if not productos:
                mostrar_mensaje_emergente(ventana, "Información", "No hay productos registrados.", "info")
                ventana.destroy()
                return

            # Header moderno
            header_frame = tk.Frame(ventana, bg='#607D8B', height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="📤 TRANSFERENCIA A SANTIAGO", 
                    font=('Segoe UI', 16, 'bold'), bg='#607D8B', fg='white').pack(pady=20)
            
            # Frame de selectores
            frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#ECEFF1')
            frame_selector.pack(fill='x')
            
            tk.Label(frame_selector, text="Fecha Transferencia (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#ECEFF1').pack(side=tk.LEFT)
            fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
            fecha_entry.insert(0, date.today().isoformat())
            fecha_entry.pack(side=tk.LEFT, padx=10)
            
            tk.Label(frame_selector, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#ECEFF1').pack(side=tk.LEFT, padx=(20, 5))
            observaciones_entry = tk.Entry(frame_selector, width=30, font=('Segoe UI', 10))
            observaciones_entry.pack(side=tk.LEFT, padx=10)

            # --- Barcode Scanner ---
            scan_frame = tk.Frame(ventana, bg='#f8f9fa', pady=5)
            scan_frame.pack(fill='x', padx=20)
            
            tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg='#607D8B').pack(side='left')
            scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor='#607D8B')
            scan_entry.pack(side='left', padx=10)
            
            tk.Label(scan_frame, text="(Presiona Enter)", font=('Segoe UI', 9), bg='#f8f9fa', fg='gray').pack(side='left')
            
            # Tabla de productos
            canvas = tk.Canvas(ventana)
            scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=canvas.yview)
            frame_productos = tk.Frame(canvas)
            canvas.create_window((0, 0), window=frame_productos, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=10)
            scrollbar.pack(side="right", fill="y")
            
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            canvas.bind("<MouseWheel>", on_mousewheel)
            frame_productos.bind("<MouseWheel>", on_mousewheel)
            
            ventana.entry_vars = {} # Use ventana.entry_vars for scanner access
            
            # Encabezados
            tk.Label(frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Stock Bodega", font=('Segoe UI', 10, 'bold'), fg='red').grid(row=0, column=2, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Cant. a Transferir", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
            
            fila = 1
            for nombre, sku, stock_actual in productos:
                tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9), wraplength=300).grid(row=fila, column=0, padx=5, pady=2, sticky='w')
                tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='w')
                tk.Label(frame_productos, text=str(stock_actual), anchor='center', font=('Segoe UI', 9), fg='red').grid(row=fila, column=2, padx=5, pady=2, sticky='w')
                entry = tk.Entry(frame_productos, width=10, font=('Segoe UI', 9))
                entry.grid(row=fila, column=3, padx=5, pady=2)
                ventana.entry_vars[sku] = entry # Store entry widget by SKU
                fila += 1
                
            frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

            # Scanner logic
            PRODUCTOS_CON_CODIGO_BARRA = [p[1] for p in productos] # Assuming all products can be scanned
            
            def real_scan_handler(event):
                codigo = scan_entry.get().strip().upper()
                if not codigo: return

                if codigo not in PRODUCTOS_CON_CODIGO_BARRA:
                    messagebox.showwarning("Código No Permitido", f"El código '{codigo}' no está en la lista permitida.", master=ventana)
                    scan_entry.delete(0, tk.END)
                    return

                if codigo in ventana.entry_vars:
                    entry_widget = ventana.entry_vars[codigo]
                    try:
                        curr = entry_widget.get().strip()
                        val = int(curr) + 1 if curr else 1
                        
                        # Validate stock
                        max_stock = next((st for n, s, st in productos if s == codigo), 0)
                        
                        if val > max_stock:
                             messagebox.showwarning("Stock Insuficiente", f"No hay suficiente stock para {codigo}. Max: {max_stock}", master=ventana)
                        else:
                            entry_widget.delete(0, tk.END)
                            entry_widget.insert(0, str(val))
                            entry_widget.config(bg=Styles.SUCCESS_COLOR, fg='white')
                            ventana.after(500, lambda: entry_widget.config(bg='white', fg='black'))

                    except ValueError: pass
                else:
                    messagebox.showwarning("No Encontrado", f"Producto {codigo} no listado.", master=ventana)
                
                scan_entry.delete(0, tk.END)

            scan_entry.bind('<Return>', real_scan_handler)
            scan_entry.focus_set()
            
            def procesar_prestamo():
                fecha_evento = fecha_entry.get().strip()
                observaciones = observaciones_entry.get().strip()
                
                if not fecha_evento:
                    mostrar_mensaje_emergente(ventana, "Error", "La fecha de transferencia es obligatoria.", "error")
                    return
    
                exitos = 0
                errores = 0
                mensaje_error = ""
    
                for sku, entry in ventana.entry_vars.items(): # Use ventana.entry_vars
                    try:
                        cantidad_text = entry.get().strip()
                        if cantidad_text:
                            cantidad = int(cantidad_text)
                            if cantidad > 0:
                                exito, mensaje = registrar_prestamo_santiago(sku, cantidad, fecha_evento, observaciones)
                                if exito:
                                    exitos += 1
                                else:
                                    errores += 1
                                    mensaje_error += f"\n- SKU {sku}: {mensaje}"
                    except ValueError:
                        if cantidad_text:
                            errores += 1
                            mensaje_error += f"\n- SKU {sku}: Cantidad no válida"
                    except Exception as e:
                        errores += 1
                        mensaje_error += f"\n- SKU {sku} (Error Inesperado): {e}"
    
                if exitos > 0 or errores > 0:
                    if errores > 0:
                        mostrar_mensaje_emergente(ventana, "Proceso Finalizado con Errores", 
                                                    f"Se completaron {exitos} transferencias y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                    "warning")
                    else:
                        mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} transferencias exitosamente.", "success")
                elif exitos == 0 and errores == 0:
                    mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")
    
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
    
            tk.Button(ventana, text="Procesar Transferencia", 
                    command=procesar_prestamo, 
                    bg='#607D8B', fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, obtener_todos_los_skus_para_movimiento, construir_ui)

    def abrir_ventana_devolucion_santiago(self):
        """Abre ventana para devolución desde Santiago con interfaz moderna (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📥 Devolución desde Santiago")
        ventana.geometry("800x600")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        def construir_ui(prestamos_activos):
            # Header moderno
            header_frame = tk.Frame(ventana, bg='#795548', height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="📥 DEVOLUCIÓN DESDE SANTIAGO", 
                    font=('Segoe UI', 16, 'bold'), bg='#795548', fg='white').pack(pady=20)
            
            # Frame de contenido
            frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
            frame_contenido.pack(fill='both', expand=True)

            if not prestamos_activos:
                tk.Label(frame_contenido, text="No hay préstamos activos para devolver", 
                        font=('Segoe UI', 12), fg='red', bg='#f8f9fa').pack(pady=50)
                return
            
            # Frame de selectores
            frame_selector = tk.Frame(frame_contenido, bg='#EFEBE9', padx=15, pady=15)
            frame_selector.pack(fill='x', pady=(0, 20))
            
            tk.Label(frame_selector, text="Fecha Devolución (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#EFEBE9').pack(side=tk.LEFT)
            fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
            fecha_entry.insert(0, date.today().isoformat())
            fecha_entry.pack(side=tk.LEFT, padx=10)
            
            tk.Label(frame_selector, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#EFEBE9').pack(side=tk.LEFT, padx=(20, 5))
            observaciones_entry = tk.Entry(frame_selector, width=30, font=('Segoe UI', 10))
            observaciones_entry.pack(side=tk.LEFT, padx=10)

            # --- Barcode Scanner ---
            scan_frame = tk.Frame(frame_contenido, bg='#f8f9fa', pady=5)
            scan_frame.pack(fill='x', padx=20)
            
            tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg='#795548').pack(side='left')
            scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor='#795548')
            scan_entry.pack(side='left', padx=10)
            
            tk.Label(scan_frame, text="(Presiona Enter)", font=('Segoe UI', 9), bg='#f8f9fa', fg='gray').pack(side='left')
            
            # Tabla de préstamos activos
            frame_tabla = tk.Frame(frame_contenido)
            frame_tabla.pack(fill='both', expand=True)
            
            columns = ("SKU", "Producto", "Total Prestado", "Primera Fecha", "Observaciones", "Cant. a Devolver")
            tabla_prestamos = ttk.Treeview(frame_tabla, columns=columns, show='headings', height=8)
            
            # Configurar columnas
            tabla_prestamos.heading("SKU", text="SKU")
            tabla_prestamos.heading("Producto", text="PRODUCTO")
            tabla_prestamos.heading("Total Prestado", text="TOTAL PRESTADO")
            tabla_prestamos.heading("Primera Fecha", text="PRIMERA FECHA")
            tabla_prestamos.heading("Observaciones", text="OBSERVACIONES")
            tabla_prestamos.heading("Cant. a Devolver", text="CANT. A DEVOLVER")
            
            tabla_prestamos.column("SKU", width=100, anchor='center')
            tabla_prestamos.column("Producto", width=200)
            tabla_prestamos.column("Total Prestado", width=120, anchor='center')
            tabla_prestamos.column("Primera Fecha", width=120, anchor='center')
            tabla_prestamos.column("Observaciones", width=200)
            tabla_prestamos.column("Cant. a Devolver", width=120, anchor='center')
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=tabla_prestamos.yview)
            tabla_prestamos.configure(yscrollcommand=scrollbar.set)
            
            tabla_prestamos.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            def on_mousewheel(event):
                tabla_prestamos.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            tabla_prestamos.bind("<MouseWheel>", on_mousewheel)
            
            ventana.entry_vars = {} # Store entry widgets for scanner
            
            # Llenar tabla
            for idx, (sku, nombre, total, primera_fecha, obs) in enumerate(prestamos_activos):
                tabla_prestamos.insert('', 'end', values=(sku, nombre, total, primera_fecha, obs, ""), iid=sku)
                # Create an entry widget for each row in the last column
                entry = tk.Entry(tabla_prestamos, width=10, font=('Segoe UI', 9), justify='center')
                tabla_prestamos.set(sku, "Cant. a Devolver", entry) # This sets the text, not the widget
                # To embed a widget, we need to use a different approach or place it outside the treeview
                # For simplicity with scanner, we'll use a separate frame for entries or map them by SKU
                # Let's create a separate scrollable frame for entries, similar to other windows
            
            # Re-structuring to allow entries for scanner
            # Remove the last column from Treeview and create a separate scrollable frame for entries
            tabla_prestamos.config(columns=("SKU", "Producto", "Total Prestado", "Primera Fecha", "Observaciones"))
            tabla_prestamos.heading("Cant. a Devolver", text="") # Clear heading if it was there
            tabla_prestamos.column("Cant. a Devolver", width=0, stretch=tk.NO) # Hide the column

            # Create a new scrollable frame for entries
            scrollable_frame_entries = tk.Frame(frame_tabla)
            scrollable_frame_entries.pack(side='right', fill='y')

            canvas_entries = tk.Canvas(scrollable_frame_entries, highlightthickness=0)
            scrollbar_entries = ttk.Scrollbar(scrollable_frame_entries, orient="vertical", command=canvas_entries.yview)
            frame_entries_inner = tk.Frame(canvas_entries)
            
            canvas_entries.create_window((0, 0), window=frame_entries_inner, anchor="nw")
            canvas_entries.configure(yscrollcommand=scrollbar_entries.set)
            
            canvas_entries.pack(side="left", fill="both", expand=True)
            scrollbar_entries.pack(side="right", fill="y")

            tk.Label(frame_entries_inner, text="Cant. a Devolver", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')

            ventana.entry_vars = {}
            for idx, (sku, nombre, total, primera_fecha, obs) in enumerate(prestamos_activos):
                entry = tk.Entry(frame_entries_inner, width=10, font=('Segoe UI', 9), justify='center')
                entry.grid(row=idx+1, column=0, padx=5, pady=2)
                ventana.entry_vars[sku] = entry
            
            frame_entries_inner.bind("<Configure>", lambda e: canvas_entries.configure(scrollregion=canvas_entries.bbox("all")))
            
            # Sync scrollbars
            def sync_scroll(*args):
                tabla_prestamos.yview(*args)
                canvas_entries.yview(*args)
            
            tabla_prestamos.configure(yscrollcommand=sync_scroll)
            canvas_entries.configure(yscrollcommand=sync_scroll)
            scrollbar.configure(command=sync_scroll)
            scrollbar_entries.configure(command=sync_scroll)

            # Scanner logic
            PRODUCTOS_CON_CODIGO_BARRA = [p[0] for p in prestamos_activos] # SKUs of active loans
            
            def real_scan_handler(event):
                codigo = scan_entry.get().strip().upper()
                if not codigo: return

                if codigo not in PRODUCTOS_CON_CODIGO_BARRA:
                    messagebox.showwarning("Código No Permitido", f"El código '{codigo}' no tiene préstamos activos.", master=ventana)
                    scan_entry.delete(0, tk.END)
                    return

                if codigo in ventana.entry_vars:
                    entry_widget = ventana.entry_vars[codigo]
                    try:
                        curr = entry_widget.get().strip()
                        val = int(curr) + 1 if curr else 1
                        
                        # Validate against total prestado
                        max_loaned = next((t for s, n, t, pf, o in prestamos_activos if s == codigo), 0)
                        
                        if val > max_loaned:
                             messagebox.showwarning("Cantidad Excedida", f"No se puede devolver más de lo prestado para {codigo}. Max: {max_loaned}", master=ventana)
                        else:
                            entry_widget.delete(0, tk.END)
                            entry_widget.insert(0, str(val))
                            entry_widget.config(bg=Styles.SUCCESS_COLOR, fg='white')
                            ventana.after(500, lambda: entry_widget.config(bg='white', fg='black'))

                    except ValueError: pass
                else:
                    messagebox.showwarning("No Encontrado", f"Producto {codigo} no listado en préstamos activos.", master=ventana)
                
                scan_entry.delete(0, tk.END)

            scan_entry.bind('<Return>', real_scan_handler)
            scan_entry.focus_set()
            
            def procesar_devolucion():
                fecha_devolucion = fecha_entry.get().strip()
                observaciones = observaciones_entry.get().strip()
                
                if not fecha_devolucion:
                    mostrar_mensaje_emergente(ventana, "Error", "La fecha de devolución es obligatoria.", "error")
                    return
                
                exitos = 0
                errores = 0
                mensaje_error = ""

                for sku, entry in ventana.entry_vars.items():
                    cantidad_text = entry.get().strip()
                    if cantidad_text:
                        try:
                            cantidad = int(cantidad_text)
                            if cantidad <= 0:
                                continue # Skip if quantity is 0 or negative
                            
                            exito, mensaje = registrar_devolucion_santiago(sku, cantidad, fecha_devolucion, observaciones)
                            
                            if exito:
                                exitos += 1
                            else:
                                errores += 1
                                mensaje_error += f"\n- SKU {sku}: {mensaje}"
                        except ValueError:
                            errores += 1
                            mensaje_error += f"\n- SKU {sku}: Cantidad no válida"
                        except Exception as e:
                            errores += 1
                            mensaje_error += f"\n- SKU {sku} (Error Inesperado): {e}"
                
                if exitos > 0 or errores > 0:
                    if errores > 0:
                        mostrar_mensaje_emergente(ventana, "Proceso Finalizado con Errores", 
                                                    f"Se completaron {exitos} devoluciones y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                    "warning")
                    else:
                        mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} devoluciones exitosamente.", "success")
                elif exitos == 0 and errores == 0:
                    mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")
    
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
    
            tk.Button(frame_contenido, text="Procesar Devolución", 
                    command=procesar_devolucion, 
                    bg='#795548', fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, obtener_prestamos_activos, construir_ui)

    def abrir_ventana_prestamos_activos(self):
        """Abre ventana para ver préstamos activos con interfaz moderna (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📋 Préstamos Activos")
        ventana.geometry("1000x600")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        def construir_ui(prestamos_activos):
            # Header moderno
            header_frame = tk.Frame(ventana, bg='#009688', height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="📋 PRÉSTAMOS ACTIVOS", 
                    font=('Segoe UI', 16, 'bold'), bg='#009688', fg='white').pack(pady=20)
            
            # Frame de contenido
            frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
            frame_contenido.pack(fill='both', expand=True)

            if not prestamos_activos:
                tk.Label(frame_contenido, text="No hay préstamos activos", 
                        font=('Segoe UI', 14), fg='gray', bg='#f8f9fa').pack(expand=True)
                return
            
            # Tabla de préstamos activos
            columns = ("SKU", "Producto", "Total Prestado", "Primera Fecha", "Observaciones")
            tabla_prestamos = ttk.Treeview(frame_contenido, columns=columns, show='headings', height=15)
            
            # Configurar columnas
            tabla_prestamos.heading("SKU", text="SKU")
            tabla_prestamos.heading("Producto", text="PRODUCTO")
            tabla_prestamos.heading("Total Prestado", text="TOTAL PRESTADO")
            tabla_prestamos.heading("Primera Fecha", text="PRIMERA FECHA")
            tabla_prestamos.heading("Observaciones", text="OBSERVACIONES")
            
            tabla_prestamos.column("SKU", width=100, anchor='center')
            tabla_prestamos.column("Producto", width=300)
            tabla_prestamos.column("Total Prestado", width=120, anchor='center')
            tabla_prestamos.column("Primera Fecha", width=120, anchor='center')
            tabla_prestamos.column("Observaciones", width=300)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(frame_contenido, orient="vertical", command=tabla_prestamos.yview)
            tabla_prestamos.configure(yscrollcommand=scrollbar.set)
            
            tabla_prestamos.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            def on_mousewheel(event):
                tabla_prestamos.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            tabla_prestamos.bind("<MouseWheel>", on_mousewheel)
            
            # Llenar tabla
            for sku, nombre, total, primera_fecha, obs in prestamos_activos:
                tabla_prestamos.insert('', 'end', values=(sku, nombre, total, primera_fecha, obs))

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, obtener_prestamos_activos, construir_ui)

    def abrir_ventana_salida_movil(self):
        """Abre ventana para salida a móvil (Refactored)"""
        MobileOutputWindow(self.main_app, on_close_callback=self.cargar_datos_tabla)

    def abrir_ventana_consiliacion(self):
        """Abre ventana para conciliación (Refactored)"""
        ConciliacionPaquetesWindow(self.main_app, on_close_callback=self.cargar_datos_tabla)

    def abrir_ventana_retorno_movil(self):
        """Abre ventana de Auditoría y Retorno de Móvil"""
        try:
            from .movements import MobileReturnWindow
            MobileReturnWindow(self.main_app, on_close_callback=self.cargar_datos_tabla)
        except Exception as e:
            import traceback
            traceback.print_exc()
            from tkinter import messagebox
            messagebox.showerror("Error", f"No se pudo abrir Retorno de Móvil:\n{e}")

    def mostrar_stock_critico(self):
        """Filtra y resalta los productos con bajo stock en la tabla principal"""
        try:
            from tkinter import messagebox
            import tkinter as tk
            # Refrescar tabla con filtro de bajo stock
            self.cargar_datos_tabla()
            messagebox.showinfo(
                "Stock Crítico",
                "Se han resaltado los productos con stock bajo en la tabla.\n\n"
                "Revisa los items marcados en rojo.",
                parent=self.master
            )
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"No se pudo mostrar stock crítico:\n{e}")

    def abrir_ventana_abasto(self):
        """Abre ventana para registro de abasto"""
        AbastoWindow(self.main_app, mode='registrar')
    
    def abrir_ventana_abasto_scanner(self):
        """Abre ventana de abasto por escaneo universal (NUEVO)"""
        AbastoScannerWindow(self.main_app)
    
    def abrir_reverso_consumo(self):
        """Abre ventana para reversar consumos erróneos"""
        from gui.inventory.reverso import ReversoConsumoScannerWindow
        ReversoConsumoScannerWindow(self.main_app)
    def abrir_ventana_salida_movil_scanner(self):
        """Abre ventana de salida a móvil por escaneo con paquete (NUEVO)"""
        try:
            # Importación local para evitar ciclos
            import gui.mobile_output_scanner as mos
            
            # Verificar si existe la clase
            if not hasattr(mos, 'MobileOutputScannerWindow'):
                messagebox.showerror("Error", "Clase MobileOutputScannerWindow no encontrada en el módulo.")
                return

            mos.MobileOutputScannerWindow(self.main_app, mode='SALIDA_MOVIL')
        except Exception as e:
            error_msg = f"Error opening scanner window: {e}"
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error Crítico", f"{error_msg}\n\nVer consola para más detalles.")

    def abrir_ventana_traslado_scanner(self):
        """Abre ventana de traslado interno (NUEVO)"""
        try:
            MobileOutputScannerWindow(self.main_app, mode='TRASLADO')
        except Exception as e:
            logger.error(f"Error opening traslado window: {e}")
            messagebox.showerror("Error", f"No se pudo abrir traslado: {e}")

    def abrir_ventana_prestamo_santiago_scanner(self):
        """Abre ventana de transferencia a Santiago (NUEVO)"""
        try:
            MobileOutputScannerWindow(self.main_app, mode='PRESTAMO_SANTIAGO')
        except Exception as e:
            logger.error(f"Error opening santiago window: {e}")
            messagebox.showerror("Error", f"No se pudo abrir Santiago: {e}")

    def abrir_ventana_devolucion_santiago_scanner(self):
        """Abre ventana de devolución desde Santiago (seriales distintos permitidos)"""
        try:
            MobileOutputScannerWindow(self.main_app, mode='DEVOLUCION_SANTIAGO')
        except Exception as e:
            logger.error(f"Error opening devolucion santiago window: {e}")
            messagebox.showerror("Error", f"No se pudo abrir Devolución Santiago: {e}")

    def abrir_ventana_gestion_abastos(self):
        """Abre ventana para gestionar (revisar/editar) abastos realizados"""
        AbastoWindow(self.main_app, mode='gestionar')
        
    def abrir_ventana_inicial(self):
        """Abre ventana para ingreso de Inventario Inicial"""
        win = AbastoWindow(self.main_app, mode='registrar')
        # Pre-fill for Initial Inventory context
        win.ref_entry.delete(0, tk.END)
        win.ref_entry.insert(0, "INVENTARIO INICIAL")
        win.obs_entry.delete(0, tk.END)
        win.obs_entry.insert(0, "Carga Inicial de Inventario")

    def abrir_ventana_historial(self, sku_preseleccionado=None):
        """Abre ventana para historial"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📜 Historial de Movimientos")
        ventana.geometry("1000x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📜 HISTORIAL DE MOVIMIENTOS", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Frame de selección
        frame_seleccion = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
        frame_seleccion.pack(fill='x')
        
        productos = obtener_todos_los_skus_para_movimiento()
        productos_dict = {f"{nombre} ({sku})": sku for nombre, sku, _ in productos}
        
        tk.Label(frame_seleccion, text="Seleccionar Producto:", font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT)
        sku_var = tk.StringVar(ventana)
        sku_combo = ttk.Combobox(frame_seleccion, textvariable=sku_var, 
                                values=list(productos_dict.keys()), 
                                state="readonly", width=60)
        sku_combo.pack(side=tk.LEFT, padx=10)
    
        def exportar_a_excel():
            if not tabla_historial.get_children():
                messagebox.showwarning("Sin Datos", "No hay historial para exportar.")
                return

            from datetime import datetime
            import pandas as pd
            from tkinter import filedialog
            import threading
            from utils.logger import get_logger
            logger = get_logger(__name__)

            fecha_str = datetime.now().strftime("%Y%m%d_%H%M")
            producto_name = sku_combo.get().split(' (')[0].replace(' ', '_') if sku_combo.get() else 'Producto'
            # Sanear nombre
            import re
            producto_name = re.sub(r'[^a-zA-Z0-9_\-]', '', producto_name)
            default_name = f"Historial_{producto_name}_{fecha_str}.xlsx"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=default_name,
                title="Guardar Historial"
            )

            if not file_path:
                return

            def process_export():
                try:
                    columnas = [tabla_historial.heading(c)['text'] for c in tabla_historial['columns']]
                    items = tabla_historial.get_children()
                    
                    rows_data = []
                    for item_id in items:
                        values = tabla_historial.item(item_id, 'values')
                        rows_data.append(values)
                    
                    df = pd.DataFrame(rows_data, columns=columnas)
                    
                    # --- APLICAR ESTILOS CON OPENPYXL ---
                    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Historial')
                        workbook = writer.book
                        worksheet = writer.sheets['Historial']
                        
                        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                        
                        # Estilos
                        header_font = Font(bold=True, color="FFFFFF")
                        header_fill = PatternFill(start_color="0056b3", end_color="0056b3", fill_type="solid")
                        center_alignment = Alignment(horizontal="left", vertical="center")
                        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                             top=Side(style='thin'), bottom=Side(style='thin'))
                        
                        # Dar estilo a las cabeceras
                        for col_num, cell in enumerate(worksheet[1], 1):
                            cell.font = header_font
                            cell.fill = header_fill
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                            cell.border = thin_border
                        
                        # Dar estilo a los datos y ajustar anchos
                        for col in worksheet.columns:
                            max_length = 0
                            column = col[0].column_letter
                            
                            for cell in col:
                                if cell.row > 1:
                                    cell.alignment = center_alignment
                                    cell.border = thin_border
                                    
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except:
                                    pass
                            
                            worksheet.column_dimensions[column].width = min(max_length + 2, 50)
                    
                    ventana.after(0, lambda: messagebox.showinfo("Exportación Exitosa", f"El historial ha sido exportado a:\n{file_path}"))
                except Exception as e:
                    logger.error(f"Error exportando a Excel: {e}")
                    ventana.after(0, lambda: messagebox.showerror("Error", f"No se pudo exportar a Excel:\n{e}"))

            threading.Thread(target=process_export, daemon=True).start()

        # Botón Exportar a Excel
        btn_export = tk.Button(frame_seleccion, text="📥 EXPORTAR A EXCEL", command=exportar_a_excel,
                               bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                               relief='flat', padx=15, pady=5)
        btn_export.pack(side=tk.RIGHT, padx=10)
        
        # Si hay SKU preseleccionado, establecerlo
        if sku_preseleccionado:
            for display, sku in productos_dict.items():
                if sku == sku_preseleccionado:
                    sku_combo.set(display)
                    break
        
        # Tabla de historial
        frame_tabla = tk.Frame(ventana)
        frame_tabla.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ("Fecha Evento", "Tipo Movimiento", "Cantidad", "Móvil", "Paquete", "Observaciones")
        tabla_historial = ttk.Treeview(frame_tabla, columns=columns, show='headings', height=15)
        
        # Configurar columnas
        tabla_historial.heading("Fecha Evento", text="FECHA EVENTO")
        tabla_historial.heading("Tipo Movimiento", text="TIPO MOVIMIENTO")
        tabla_historial.heading("Cantidad", text="CANTIDAD")
        tabla_historial.heading("Móvil", text="MÓVIL")
        tabla_historial.heading("Paquete", text="PAQUETE")
        tabla_historial.heading("Observaciones", text="OBSERVACIONES")
        
        tabla_historial.column("Fecha Evento", width=120, anchor='center')
        tabla_historial.column("Tipo Movimiento", width=150, anchor='center')
        tabla_historial.column("Cantidad", width=100, anchor='center')
        tabla_historial.column("Móvil", width=100, anchor='center')
        tabla_historial.column("Paquete", width=120, anchor='center')
        tabla_historial.column("Observaciones", width=300)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=tabla_historial.yview)
        tabla_historial.configure(yscrollcommand=scrollbar.set)
        
        tabla_historial.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def on_mousewheel(event):
            tabla_historial.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        tabla_historial.bind("<MouseWheel>", on_mousewheel)
        
        def cargar_historial():
            producto_seleccionado = sku_var.get()
            if not producto_seleccionado:
                return
            
            # Limpiar tabla
            for item in tabla_historial.get_children():
                tabla_historial.delete(item)
            
            # Obtener SKU
            sku = productos_dict[producto_seleccionado]
            
            # Obtener historial
            historial = obtener_historial_producto(sku)
            
            if not historial:
                tabla_historial.insert('', 'end', values=("No hay movimientos registrados", "", "", "", "", ""))
                return
            
            # Llenar tabla
            for nombre, tipo, cantidad, movil, paquete, fecha_mov, fecha_evento, observaciones in historial:
                movil_display = movil if movil else ""
                paquete_display = paquete if paquete else ""
                tabla_historial.insert('', 'end', values=(fecha_evento, tipo, cantidad, movil_display, paquete_display, observaciones))
        
        sku_combo.bind("<<ComboboxSelected>>", lambda e: cargar_historial())
        
        # Cargar historial inicial si hay SKU preseleccionado
        if sku_preseleccionado:
            cargar_historial()

    
    def abrir_gestion_codigos(self):
        """Abre la pestaña de productos para gestionar códigos de barra"""
        # Cambiar a la pestaña de productos
        for i in range(self.main_app.main_notebook.index("end")):
            if "Productos" in self.main_app.main_notebook.tab(i, "text"):
                self.main_app.main_notebook.select(i)
                messagebox.showinfo("Gestión de Códigos", 
                    "Para asignar un código de barra:\n\n" +
                    "1. Busca el producto en la tabla\n" +
                    "2. Doble click en el producto\n" +
                    "3. Escanea o escribe el código\n" +
                    "4. Guarda",
                    parent=self.master)
                return
        
        # Si no existe la pestaña, mostrar mensaje
        messagebox.showwarning("Pestaña no disponible", 
            "La pestaña de Productos no está disponible", parent=self.master)
    
    def mostrar_herramientas_limpieza(self):
        """Muestra ventana con herramientas avanzadas de limpieza"""
        ventana = tk.Toplevel(self.master)
        ventana.title("🧹 Herramientas de Limpieza Avanzada")
        ventana.geometry("600x400")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header
        header_frame = tk.Frame(ventana, bg=Styles.WARNING_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="🧹 HERRAMIENTAS DE LIMPIEZA", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.WARNING_COLOR, fg='white').pack(pady=20)
        
        # Contenido
        frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
        frame_contenido.pack(fill='both', expand=True)
        
        # Función para diagnóstico detallado
        def ejecutar_diagnostico():
            resultado_text.delete(1.0, tk.END)
            resultado_text.insert(1.0, "🔍 Ejecutando diagnóstico...\n")
            ventana.update()
            
            # Ejecutar verificación
            try:
                # Importar aquí para evitar circularidad
                from database import verificar_y_corregir_duplicados_completo
                verificar_y_corregir_duplicados_completo()
                resultado_text.insert(tk.END, "✅ Diagnóstico completado.\n")
                resultado_text.insert(tk.END, "Los duplicados han sido corregidos.\n")
            except Exception as e:
                resultado_text.insert(tk.END, f"❌ Error: {e}\n")
        
        # Botones
        frame_botones = tk.Frame(frame_contenido, bg='#f8f9fa')
        frame_botones.pack(fill='x', pady=10)
        
        tk.Button(frame_botones, text="🔍 Ejecutar Diagnóstico Completo", 
                 command=ejecutar_diagnostico,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8).pack(pady=5)
        
        # Área de resultados
        tk.Label(frame_contenido, text="Resultados:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').pack(anchor='w', pady=(10, 5))
        
        resultado_text = tk.Text(frame_contenido, height=10, width=70, 
                               font=('Consolas', 9), bg='#f0f0f0')
        resultado_text.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(resultado_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        resultado_text.config(yscrollcommand=scrollbar.set)

