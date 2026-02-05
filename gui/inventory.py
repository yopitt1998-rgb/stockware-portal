import tkinter as tk
from tkinter import ttk, messagebox, Canvas, Scrollbar
from datetime import date, datetime, timedelta
import os
import threading


from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente

from config import TIPOS_MOVIMIENTO, DATABASE_NAME, PRODUCTOS_CON_CODIGO_BARRA
from database import (
    obtener_inventario, obtener_todos_los_skus_para_movimiento,
    anadir_producto, registrar_movimiento_gui, eliminar_producto,
    obtener_ultima_salida_movil, obtener_asignacion_movil,
    obtener_asignacion_movil_con_paquetes, registrar_prestamo_santiago,
    obtener_prestamos_activos, registrar_devolucion_santiago,
    obtener_historial_producto, limpiar_productos_duplicados,
    limpiar_duplicados_asignacion_moviles,
    TIPO_MOVIMIENTO_DESCARTE, obtener_stock_actual_y_moviles,
    obtener_abastos_resumen, obtener_detalle_abasto, actualizar_movimiento_abasto,
    obtener_nombres_moviles, verificar_stock_disponible,
    obtener_consumos_pendientes, eliminar_consumo_pendiente, # NUEVOS IMPORTS
    obtener_info_serial, actualizar_ubicacion_serial, incrementar_asignacion_movil # Para Salida a Móvil con Seriales
)
import pandas as pd
from tkinter import filedialog
# Note: Some imports might be missing, I'll add them as I discover needs during implementation (e.g. exportar_a_csv)

from .reconciliation import abrir_ventana_conciliacion_excel
from .abasto import AbastoWindow
from .mobiles import MobilesManager
from .consumption import ConsumoTecnicoWindow
from .pdf_generator import generar_vale_despacho
from database import obtener_configuracion, procesar_auditoria_consumo # NUEVO IMPORT
from config import PRODUCTOS_INICIALES # NUEVO IMPORT

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
                print(f"Error async: {e}")
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

    def create_widgets(self):
        """Crear pestaña de Gestión de Inventario"""
        inventory_frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(inventory_frame, text="📦 Gestión de Inventario")
        
        # Controles superiores
        controls_frame = ttk.Frame(inventory_frame, style='Modern.TFrame')
        controls_frame.pack(fill='x', padx=20, pady=20)
        
        # Botones de gestión
        management_buttons = [
            ("➕ Nuevo Producto", self.abrir_ventana_anadir, Styles.SUCCESS_COLOR),
            ("📥 Registrar Abasto", self.abrir_ventana_abasto, '#2E7D32'),
            ("📜 Gestionar Abastos", self.abrir_ventana_gestion_abastos, '#43A047'),
            ("🏁 Inventario Inicial", self.abrir_ventana_inicial, '#1B5E20'),
            # ("📂 Conciliación Excel", self.abrir_conciliacion, Styles.PRIMARY_COLOR),
            ("➖ Salida Individual", self.abrir_ventana_salida_individual, Styles.WARNING_COLOR),
            ("❌ Eliminar Producto", self.abrir_ventana_eliminar, Styles.ACCENT_COLOR),
            ("🗑️ Descarte", self.abrir_ventana_descarte, Styles.INFO_COLOR),
            ("🔄 Traslado", self.abrir_ventana_traslado, Styles.SECONDARY_COLOR),
            ("📤 Transferencia Santiago", self.abrir_ventana_prestamo_bodega, '#607D8B'),
            ("📥 Devolución", self.abrir_ventana_devolucion_santiago, '#795548'),
            ("📋 Ver Préstamos", self.abrir_ventana_prestamos_activos, '#009688'),
            ("📥 Registro Consumo", self.abrir_ventana_consumo, Styles.INFO_COLOR),
            ("🚚 Gestionar Móviles", self.abrir_ventana_gestion_moviles, '#E91E63'),
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
                print(f"❌ Error crítico cargando tabla de inventario: {e}")
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
        """Abre ventana para salida individual desde bodega (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("➖ Salida Individual desde Bodega")
        ventana.geometry("900x700")
        try: 
            ventana.state('zoomed')
        except tk.TclError: 
            ventana.wm_attributes('-fullscreen', True)
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        def construir_ui(productos):
            if not productos:
                mostrar_mensaje_emergente(ventana, "Información", "No hay productos registrados.", "info")
                ventana.destroy()
                return

            # Header moderno
            header_frame = tk.Frame(ventana, bg=Styles.WARNING_COLOR, height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="➖ SALIDA INDIVIDUAL DESDE BODEGA", 
                    font=('Segoe UI', 16, 'bold'), bg=Styles.WARNING_COLOR, fg='white').pack(pady=20)
            
            # Frame de selectores
            frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#FFF3E0')
            frame_selector.pack(fill='x')
            
            tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#FFF3E0').pack(side=tk.LEFT)
            fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
            fecha_entry.insert(0, date.today().isoformat())
            fecha_entry.pack(side=tk.LEFT, padx=10)
            
            tk.Label(frame_selector, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#FFF3E0').pack(side=tk.LEFT, padx=(20, 5))
            observaciones_entry = tk.Entry(frame_selector, width=30, font=('Segoe UI', 10))
            observaciones_entry.pack(side=tk.LEFT, padx=10)

            # --- Barcode Scanner ---
            scan_frame = tk.Frame(ventana, bg='#f8f9fa', pady=5)
            scan_frame.pack(fill='x', padx=20)
            
            tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg=Styles.WARNING_COLOR).pack(side='left')
            scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor=Styles.WARNING_COLOR)
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
            tk.Label(frame_productos, text="Cant. a Salir", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
            
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
            # Define a list of SKUs that are allowed to be scanned (e.g., those with barcodes)
            # For now, let's assume all SKUs in 'productos' are scannable.
            PRODUCTOS_CON_CODIGO_BARRA = [p[1] for p in productos]
            
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
                        # Find max stock for this sku from the 'productos' list
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
            
            def procesar_salida_individual():
                fecha_evento = fecha_entry.get().strip()
                observaciones = observaciones_entry.get().strip()
                
                if not fecha_evento:
                    mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
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
                                # VERIFICACIÓN DE STOCK (PUNTO 5)
                                disponible, stock = verificar_stock_disponible(sku, cantidad)
                                if not disponible:
                                    errores += 1
                                    mensaje_error += f"\n- {sku}: Stock insuficiente ({stock} < {cantidad})"
                                    entry.configure(bg='#FFCDD2') # Rojo claro
                                    continue
                                    
                                obs_final = f"SALIDA INDIVIDUAL - {observaciones}" if observaciones else "SALIDA INDIVIDUAL"
                                exito, mensaje = registrar_movimiento_gui(sku, 'SALIDA', cantidad, None, fecha_evento, None, obs_final)
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
                                                    f"Se completaron {exitos} salidas y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                    "warning")
                    else:
                        mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} salidas individuales exitosamente.", "success")
                elif exitos == 0 and errores == 0:
                    mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")
    
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
    
            tk.Button(ventana, text="Procesar Salida Individual", 
                    command=procesar_salida_individual, 
                    bg=Styles.WARNING_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, obtener_todos_los_skus_para_movimiento, construir_ui)

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
        """Abre ventana para descarte con interfaz moderna (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("🗑️ Registro de Descarte")
        ventana.geometry("800x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        def construir_ui(productos):
            if not productos:
                mostrar_mensaje_emergente(ventana, "Información", "No hay productos registrados.", "info")
                ventana.destroy()
                return

            # Header moderno
            header_frame = tk.Frame(ventana, bg=Styles.INFO_COLOR, height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="🗑️ REGISTRO DE DESCARTE", 
                    font=('Segoe UI', 16, 'bold'), bg=Styles.INFO_COLOR, fg='white').pack(pady=20)
            
            # Frame de selectores
            frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#E1F5FE')
            frame_selector.pack(fill='x')
            
            tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#E1F5FE').pack(side=tk.LEFT)
            fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
            fecha_entry.insert(0, date.today().isoformat())
            fecha_entry.pack(side=tk.LEFT, padx=10)
            
            tk.Label(frame_selector, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#E1F5FE').pack(side=tk.LEFT, padx=(20, 5))
            observaciones_entry = tk.Entry(frame_selector, width=30, font=('Segoe UI', 10))
            observaciones_entry.pack(side=tk.LEFT, padx=10)

            # --- Barcode Scanner ---
            scan_frame = tk.Frame(ventana, bg='#f8f9fa', pady=5)
            scan_frame.pack(fill='x', padx=20)
            
            tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg=Styles.INFO_COLOR).pack(side='left')
            scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor=Styles.INFO_COLOR)
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
            tk.Label(frame_productos, text="Cant. a Descartar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
            
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
            
            def procesar_descarte():
                fecha_evento = fecha_entry.get().strip()
                observaciones = observaciones_entry.get().strip()
                
                if not fecha_evento:
                    mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
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
                                obs_final = f"DESCARTE - {observaciones}" if observaciones else "DESCARTE"
                                exito, mensaje = registrar_movimiento_gui(sku, TIPO_MOVIMIENTO_DESCARTE, cantidad, None, fecha_evento, None, obs_final)
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
                                                    f"Se completaron {exitos} descartes y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                    "warning")
                    else:
                        mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} descartes exitosamente.", "success")
                elif exitos == 0 and errores == 0:
                    mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")
    
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
    
            tk.Button(ventana, text="Procesar Descarte", 
                    command=procesar_descarte, 
                    bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, obtener_todos_los_skus_para_movimiento, construir_ui)

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
            header_labels.append(tk.Label(frame_productos, text="Stock en Móvil", font=('Segoe UI', 10, 'bold'), fg='blue'))
            header_labels.append(tk.Label(frame_productos, text="Cant. a Trasladar", font=('Segoe UI', 10, 'bold')))
            
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
                
                # Obtener productos del móvil origen (Aun sincrono, pero on-demand)
                # TODO: Convertir esto a async si es lento tambien
                productos_asignados = obtener_asignacion_movil(movil_origen)
                if not productos_asignados:
                    tk.Label(frame_productos, text="No hay productos asignados a este móvil", 
                            font=('Segoe UI', 10), fg='red').grid(row=1, column=0, columnspan=4, padx=10, pady=10)
                    return
                
                productos_en_movil_origen = productos_asignados # Store for scanner
                
                fila = 1
                for nombre, sku, cantidad in productos_asignados:
                    tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9)).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
                    tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
                    tk.Label(frame_productos, text=str(cantidad), anchor='center', font=('Segoe UI', 9), fg='blue').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
                    entry = tk.Entry(frame_productos, width=8, font=('Segoe UI', 9))
                    entry.grid(row=fila, column=3, padx=5, pady=2)
                    ventana.entry_vars[sku] = entry # Store entry widget by SKU
                    fila += 1
                
                frame_productos.update_idletasks()
                canvas.config(scrollregion=canvas.bbox("all"))
            
            movil_origen_combo.bind("<<ComboboxSelected>>", cargar_productos_movil)
            frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

            # Scanner logic
            def real_scan_handler(event):
                codigo = scan_entry.get().strip().upper()
                if not codigo: return

                if not productos_en_movil_origen:
                    messagebox.showwarning("Error", "Primero debe seleccionar un móvil de origen para cargar los productos.", master=ventana)
                    scan_entry.delete(0, tk.END)
                    return

                # Check if the scanned code is among the products loaded for the origin mobile
                scannable_skus = [p[1] for p in productos_en_movil_origen]
                if codigo not in scannable_skus:
                    messagebox.showwarning("Código No Permitido", f"El código '{codigo}' no está asignado al móvil de origen seleccionado.", master=ventana)
                    scan_entry.delete(0, tk.END)
                    return

                if codigo in ventana.entry_vars:
                    entry_widget = ventana.entry_vars[codigo]
                    try:
                        curr = entry_widget.get().strip()
                        val = int(curr) + 1 if curr else 1
                        
                        # Validate stock against the stock in the origin mobile
                        max_stock = next((q for n, s, q in productos_en_movil_origen if s == codigo), 0)
                        
                        if val > max_stock:
                             messagebox.showwarning("Stock Insuficiente", f"No hay suficiente stock para {codigo} en el móvil de origen. Max: {max_stock}", master=ventana)
                        else:
                            entry_widget.delete(0, tk.END)
                            entry_widget.insert(0, str(val))
                            entry_widget.config(bg=Styles.SUCCESS_COLOR, fg='white')
                            ventana.after(500, lambda: entry_widget.config(bg='white', fg='black'))

                    except ValueError: pass
                else:
                    messagebox.showwarning("No Encontrado", f"Producto {codigo} no listado para este móvil.", master=ventana)
                
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
    
                for sku, entry in ventana.entry_vars.items(): # Use ventana.entry_vars
                    try:
                        cantidad_text = entry.get().strip()
                        if cantidad_text:
                            cantidad = int(cantidad_text)
                            if cantidad > 0:
                                # VERIFICACIÓN DE STOCK EN MÓVIL (PUNTO 5)
                                # Necesitamos saber cuanto hay en el movil origen
                                # Por simplicidad, ya tenemos los datos en la tabla, pero re-verificamos con la BD
                                prod_movil = obtener_asignacion_movil(movil_origen)
                                stock_en_movil = next((p[2] for p in prod_movil if str(p[1]) == str(sku)), 0)
                                
                                if stock_en_movil < cantidad:
                                    errores += 1
                                    mensaje_error += f"\n- {sku}: Stock insuficiente en {movil_origen} ({stock_en_movil} < {cantidad})"
                                    entry.configure(bg='#FFCDD2')
                                    continue
    
                                # Registrar retorno desde móvil origen
                                exito1, mensaje1 = registrar_movimiento_gui(sku, 'RETORNO_MOVIL', cantidad, movil_origen, fecha_evento, None, "TRASLADO")
                                # Registrar salida a móvil destino
                                exito2, mensaje2 = registrar_movimiento_gui(sku, 'SALIDA_MOVIL', cantidad, movil_destino, fecha_evento, None, "TRASLADO")
                                
                                if exito1 and exito2:
                                    exitos += 1
                                else:
                                    errores += 1
                                    if not exito1:
                                        mensaje_error += f"\n- SKU {sku} (Retorno): {mensaje1}"
                                    if not exito2:
                                        mensaje_error += f"\n- SKU {sku} (Salida): {mensaje2}"
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

    def crear_recordatorios_automaticos(self, fecha_salida):
        """Crea recordatorios automáticos para retorno y conciliación basados en una salida"""
        try:
            fecha_salida_date = datetime.strptime(fecha_salida, '%Y-%m-%d').date()
            
            # Fecha de retorno (día siguiente)
            fecha_retorno = fecha_salida_date + timedelta(days=1)
            # Fecha de conciliación (2 días después)
            fecha_conciliacion = fecha_salida_date + timedelta(days=2)
            
            # Importar localmente para evitar problemas de dependencias
            import sqlite3
            from database import crear_recordatorio
            
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT movil_afectado, paquete_asignado
                FROM movimientos 
                WHERE tipo_movimiento = 'SALIDA_MOVIL' 
                AND fecha_evento = ?
                AND paquete_asignado IN ('PAQUETE A', 'PAQUETE B')
                AND movil_afectado IS NOT NULL
            """, (fecha_salida,))
            
            salidas = cursor.fetchall()
            
            recordatorios_creados = 0
            for movil, paquete in salidas:
                if movil and paquete:
                    # Crear recordatorio de retorno
                    if crear_recordatorio(movil, paquete, 'RETORNO', fecha_retorno.isoformat()):
                        recordatorios_creados += 1
                    
                    # Crear recordatorio de conciliación
                    if crear_recordatorio(movil, paquete, 'CONCILIACION', fecha_conciliacion.isoformat()):
                        recordatorios_creados += 1
            
            conn.close()
            
            if recordatorios_creados > 0:
                mostrar_mensaje_emergente(self.master, "Éxito", 
                    f"Se crearon {recordatorios_creados} recordatorios automáticos para las fechas:\n"
                    f"• Retorno: {fecha_retorno}\n"
                    f"• Conciliación: {fecha_conciliacion}", 
                    "success")
                return True
            
            return False
            
        except Exception as e:
            print(f"Error al crear recordatorios automáticos: {e}")
            return False

    def abrir_ventana_salida_movil(self):
        """Abre ventana para salida a móvil con botones de rellenar y limpiar (Async)"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📤 Salida a Móvil - Con Paquetes")
        try: 
            ventana.state('zoomed')
        except tk.TclError: 
            ventana.wm_attributes('-fullscreen', True)
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        def carga_datos():
            return obtener_todos_los_skus_para_movimiento(), obtener_nombres_moviles()

        def construir_ui(datos_carga):
            productos, moviles_db = datos_carga # Renamed to avoid conflict with local 'productos' in scanner handler
            
            if not productos:
                mostrar_mensaje_emergente(ventana, "Información", "No hay productos registrados.", "info")
                ventana.destroy()
                return

            # Header moderno
            header_frame = tk.Frame(ventana, bg=Styles.PRIMARY_COLOR, height=80)
            header_frame.pack(fill='x')
            header_frame.pack_propagate(False)
            
            tk.Label(header_frame, text="📤 SALIDA A MÓVIL", 
                    font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
            
            # Frame de selectores
            frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#F8BBD0')
            frame_selector.pack(fill='x')
            
            tk.Label(frame_selector, text="Móvil Destino:", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT)
            movil_combo = ttk.Combobox(frame_selector, values=moviles_db, state="readonly", width=15)
            movil_combo.set("--- Seleccionar Móvil ---")
            movil_combo.pack(side=tk.LEFT, padx=10)
            
            # Selector de Paquete
            PAQUETES_DISPONIBLES = ["NINGUNO", "PAQUETE A", "PAQUETE B", "CARRO"]
            tk.Label(frame_selector, text="Paquete Asignado:", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT, padx=(20, 5))
            paquete_combo = ttk.Combobox(frame_selector, values=PAQUETES_DISPONIBLES, state="readonly", width=15)
            paquete_combo.set("NINGUNO")
            paquete_combo.pack(side=tk.LEFT, padx=10)
            
            tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT, padx=(20, 5))
            fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
            fecha_entry.insert(0, date.today().isoformat())
            fecha_entry.pack(side=tk.LEFT)
            
            # Frame de botones de utilidad
            frame_utilidad = tk.Frame(ventana, padx=20, pady=10, bg='#f8f9fa')
            frame_utilidad.pack(fill='x')
            
            self.salida_entries = {}

            def rellenar_desde_ultima_salida():
                movil_seleccionado = movil_combo.get()
                if movil_seleccionado == "--- Seleccionar Móvil ---":
                    mostrar_mensaje_emergente(ventana, "Error", "Debe seleccionar un móvil primero.", "error")
                    return
                    
                ultima_salida = obtener_ultima_salida_movil(movil_seleccionado)
                if not ultima_salida:
                    mostrar_mensaje_emergente(ventana, "Información", f"No se encontró una salida previa para {movil_seleccionado}.", "info")
                    return
                    
                # Limpiar todos los campos primero
                for entry in self.salida_entries.values():
                    entry.delete(0, tk.END)
                    
                # Rellenar con los datos de la última salida
                for sku, cantidad in ultima_salida:
                    if sku in self.salida_entries:
                        self.salida_entries[sku].insert(0, str(cantidad))
                        
                mostrar_mensaje_emergente(ventana, "Éxito", f"Datos de última salida cargados para {movil_seleccionado}.", "success")
            
            def limpiar_campos():
                for entry in self.salida_entries.values():
                    entry.delete(0, tk.END)
                mostrar_mensaje_emergente(ventana, "Información", "Todos los campos han sido limpiados.", "info")
            
            tk.Button(frame_utilidad, text="🔄 Rellenar desde última salida", 
                    command=rellenar_desde_ultima_salida,
                    bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                    relief='flat', bd=0, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
                    
            tk.Button(frame_utilidad, text="🧹 Limpiar campos", 
                    command=limpiar_campos,
                    bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                    relief='flat', bd=0, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
            
            # ==================== NUEVO: SISTEMA DE ESCANEO ====================
            # Frame de escaneo de seriales
            from collections import defaultdict
            seriales_escaneados = defaultdict(list)  # {sku: [serial1, serial2, ...]}
            
            frame_escaneo = tk.LabelFrame(ventana, text="🔍 ESCANEAR EQUIPOS (Opcional)", 
                                           font=('Segoe UI', 11, 'bold'), 
                                           bg='#E3F2FD', padx=15, pady=10)
            frame_escaneo.pack(fill='x', padx=20, pady=10)
            
            # Campo de entrada para escaneo
            tk.Label(frame_escaneo, text="Serial:", font=('Segoe UI', 10, 'bold'), 
                     bg='#E3F2FD').pack(side='left', padx=5)
            entry_scan = tk.Entry(frame_escaneo, font=('Segoe UI', 12), width=25, bg='white')
            entry_scan.pack(side='left', padx=5)
            
            # Label contador
            lbl_total_escaneados = tk.Label(frame_escaneo, 
                                            text="Total escaneado: 0 equipos",
                                            font=('Segoe UI', 10, 'bold'), 
                                            bg='#E3F2FD', fg=Styles.SUCCESS_COLOR)
            lbl_total_escaneados.pack(side='left', padx=20)
            
            # Botón para limpiar escaneados
            def limpiar_escaneados():
                if not seriales_escaneados:
                    return
                total = sum(len(s) for s in seriales_escaneados.values())
                if messagebox.askyesno("Limpiar", 
                                      f"¿Está seguro de limpiar todos los {total} equipos escaneados?"):
                    seriales_escaneados.clear()
                    actualizar_tabla_escaneados()
                    entry_scan.focus_set()

            btn_limpiar_scan = tk.Button(frame_escaneo, text="🗑️ Limpiar Escaneados",
                                          command=limpiar_escaneados,
                                          bg='#FF9800', fg='white', 
                                          font=('Segoe UI', 9, 'bold'),
                                          relief='flat', padx=10, pady=5)
            btn_limpiar_scan.pack(side='left', padx=10)
            
            # Tabla de equipos escaneados
            frame_tabla_escaneados = tk.LabelFrame(ventana, 
                                                   text="📋 Equipos Escaneados", 
                                                   font=('Segoe UI', 10, 'bold'))
            frame_tabla_escaneados.pack(fill='x', expand=False, padx=20, pady=5)  # Changed from fill='both' to fill='x'
            
            # Crear TreeView con altura reducida
            tree_escaneados = ttk.Treeview(frame_tabla_escaneados,
                                           columns=('Producto', 'SKU', 'Cantidad', 'Seriales'),
                                           show='headings', height=4)  # Reduced from 6 to 4
            tree_escaneados.heading('Producto', text='Producto')
            tree_escaneados.heading('SKU', text='SKU')
            tree_escaneados.heading('Cantidad', text='Cantidad')
            tree_escaneados.heading('Seriales', text='Seriales (primeros 5)')
            
            tree_escaneados.column('Producto', width=200)  # Reduced from 250
            tree_escaneados.column('SKU', width=80, anchor='center')  # Reduced from 100
            tree_escaneados.column('Cantidad', width=70, anchor='center')  # Reduced from 80
            tree_escaneados.column('Seriales', width=350)  # Reduced from 400
            
            tree_escaneados.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Scrollbar
            scrollbar_tree = ttk.Scrollbar(frame_tabla_escaneados, orient='vertical', 
                                           command=tree_escaneados.yview)
            tree_escaneados.configure(yscrollcommand=scrollbar_tree.set)
            scrollbar_tree.pack(side='right', fill='y')
            
            def actualizar_tabla_escaneados():
                """Actualiza la tabla de equipos escaneados"""
                # Limpiar tabla
                for item in tree_escaneados.get_children():
                    tree_escaneados.delete(item)
                
                total_equipos = 0
                
                # Llenar con datos actuales
                for sku in sorted(seriales_escaneados.keys()):
                    seriales_list = seriales_escaneados[sku]
                    cantidad = len(seriales_list)
                    total_equipos += cantidad
                    
                    # Obtener nombre del producto
                    nombre_producto = "Producto Desconocido"
                    for nombre, sku_prod, _ in productos:
                        if sku_prod == sku:
                            nombre_producto = nombre
                            break
                    
                    # Mostrar solo primeros 5 seriales
                    seriales_display = ", ".join(seriales_list[:5])
                    if len(seriales_list) > 5:
                        seriales_display += f" ... (+{len(seriales_list) - 5} más)"
                    
                    # Insertar en tabla
                    tree_escaneados.insert('', 'end', 
                                          values=(nombre_producto, sku, cantidad, seriales_display))
                
                # Actualizar contador
                lbl_total_escaneados.config(
                    text=f"Total escaneado: {total_equipos} equipos"
                )
            
            def procesar_serial_escaneado(event):
                """Procesa un serial escaneado"""
                serial = entry_scan.get().strip().upper()
                if not serial:
                    return
                
                # Importar funciones necesarias
                from database import obtener_info_serial
                
                # 1. Buscar serial en BD
                sku, ubicacion = obtener_info_serial(serial)
                
                # 2. Validaciones
                if not sku:
                    messagebox.showerror("Serial No Encontrado", 
                                       f"El serial '{serial}' no existe en la base de datos.\\n\\n"
                                       "Verifique que fue registrado en Abasto.")
                    entry_scan.delete(0, tk.END)
                    entry_scan.focus_set()
                    return
                
                if ubicacion != 'BODEGA':
                    messagebox.showwarning("Serial Ya Asignado", 
                                          f"El serial '{serial}' ya está asignado a: {ubicacion}\\n\\n"
                                          "No se puede asignar nuevamente.")
                    entry_scan.delete(0, tk.END)
                    entry_scan.focus_set()
                    return
                
                # 3. Verificar duplicados en esta sesión
                if serial in seriales_escaneados[sku]:
                    messagebox.showinfo("Duplicado", 
                                      f"El serial '{serial}' ya fue escaneado en esta sesión.")
                    entry_scan.delete(0, tk.END)
                    entry_scan.focus_set()
                    return
                
                # 4. Agregar a lista
                seriales_escaneados[sku].append(serial)
                
                # 5. Actualizar UI
                actualizar_tabla_escaneados()
                
                # 6. Feedback visual positivo
                entry_scan.delete(0, tk.END)
                entry_scan.config(bg='#C8E6C9')  # Verde claro
                ventana.after(200, lambda: entry_scan.config(bg='white'))
                entry_scan.focus_set()
            
            # Bind de Enter
            entry_scan.bind('<Return>', procesar_serial_escaneado)
            
            # Label informativo
            lbl_info_modo = tk.Label(ventana, 
                                     text="💡 Puede usar escaneo de códigos O ingresar cantidades manualmente abajo",
                                     font=('Segoe UI', 9, 'italic'), 
                                     fg='#666', bg='#f8f9fa')
            lbl_info_modo.pack(pady=5)
            # ==================== FIN SISTEMA DE ESCANEO ====================
            
            # Separador visual
            ttk.Separator(ventana, orient='horizontal').pack(fill='x', padx=20, pady=10)
            
            # Label informativo para sección de productos
            tk.Label(ventana, text="📦 LISTA DE PRODUCTOS - Ingreso Manual de Cantidades", 
                     font=('Segoe UI', 11, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(pady=5)
            
            # Tabla de productos - MEJORAR VISIBILIDAD
            frame_productos_container = tk.Frame(ventana, bg='#f8f9fa')
            frame_productos_container.pack(fill='both', expand=True, padx=20, pady=5)
            
            canvas = tk.Canvas(frame_productos_container, bg='#ffffff')
            scrollbar = ttk.Scrollbar(frame_productos_container, orient="vertical", command=canvas.yview)
            frame_productos = tk.Frame(canvas, bg='#ffffff')
            canvas.create_window((0, 0), window=frame_productos, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
    
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            canvas.bind("<MouseWheel>", on_mousewheel)
            frame_productos.bind("<MouseWheel>", on_mousewheel)
    
            
            # ESTRUCTURA DE COLUMNAS
            tk.Label(frame_productos, text="Nombre", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Stock Actual", font=('Segoe UI', 10, 'bold'), fg='red').grid(row=0, column=2, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Cant. a Asignar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
            
            fila = 1
            for nombre, sku, cantidad_actual in productos:
                tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9)).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
                tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
                tk.Label(frame_productos, text=str(cantidad_actual), anchor='center', font=('Segoe UI', 9), fg='red').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
                entry = tk.Entry(frame_productos, width=8, font=('Segoe UI', 9))
                entry.grid(row=fila, column=3, padx=5, pady=2)
                self.salida_entries[sku] = entry
                fila += 1
                
            frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            
            def procesar_salida():
                """Procesa la salida - MODO DUAL: Escaneo o Manual"""
                movil_seleccionado = movil_combo.get()
                fecha_evento = fecha_entry.get().strip()
                paquete = paquete_combo.get() if paquete_combo.get() != "NINGUNO" else None
                
                if movil_seleccionado == "--- Seleccionar Móvil ---":
                    mostrar_mensaje_emergente(ventana, "Error", "Debe seleccionar un Móvil.", "error")
                    return
                    
                if not fecha_evento:
                    mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
                    return
                
                # DETECTAR MODO: ¿Hay seriales escaneados?
                if seriales_escaneados:
                    # MODO ESCANEO
                    procesar_salida_con_seriales()
                else:
                    # MODO MANUAL (código existente)
                    procesar_salida_manual()
            
            def procesar_salida_con_seriales():
                """Procesa salida usando seriales escaneados"""
                movil_seleccionado = movil_combo.get()
                fecha_evento = fecha_entry.get()
                paquete = paquete_combo.get() if paquete_combo.get() != "NINGUNO" else None
                
                total_equipos = sum(len(s) for s in seriales_escaneados.values())
                
                # Confirmar con usuario
                if not messagebox.askyesno("Confirmar Asignación",
                                          f"¿Confirma asignar {total_equipos} equipos escaneados a {movil_seleccionado}?"):
                    return
                
                from database import actualizar_ubicacion_serial
                
                exitos = 0
                errores = 0
                errores_detalle = []
                
                for sku, seriales_list in seriales_escaneados.items():
                    cantidad = len(seriales_list)
                    
                    # 1. Registrar movimiento global
                    exito_mov, mensaje_mov = registrar_movimiento_gui(
                        sku, 'SALIDA_MOVIL', cantidad, movil_seleccionado, 
                        fecha_evento, paquete, f"Asignación por escaneo - {cantidad} equipos"
                    )
                    
                    if not exito_mov:
                        errores += cantidad
                        errores_detalle.append(f"SKU {sku}: {mensaje_mov}")
                        continue
                    
                    # 2. Actualizar ubicación de cada serial
                    for serial in seriales_list:
                        exito_ser, mensaje_ser = actualizar_ubicacion_serial(serial, movil_seleccionado)
                        if exito_ser:
                            exitos += 1
                        else:
                            errores += 1
                            errores_detalle.append(f"Serial {serial}: {mensaje_ser}")
                
                # Reporte final
                if errores == 0:
                    mostrar_mensaje_emergente(self.master, "Éxito", 
                                              f"Se asignaron {exitos} equipos exitosamente a {movil_seleccionado}.", 
                                              "success")
                    
                    # Ofrecer generar Vale de Despacho en PDF
                    if messagebox.askyesno("Vale de Despacho", "¿Desea generar el Vale de Despacho en PDF para este movimiento?"):
                        productos_pdf = []
                        for sku, seriales_list in seriales_escaneados.items():
                            # Buscar nombre del producto
                            nombre_p = "Producto"
                            for p in productos:
                                if str(p[1]) == str(sku):
                                    nombre_p = p[0]
                                    break
                            productos_pdf.append((sku, nombre_p, str(len(seriales_list))))
                        
                        if productos_pdf:
                            filename = filedialog.asksaveasfilename(
                                title="Guardar Vale de Despacho",
                                initialfile=f"Vale_{movil_seleccionado.replace(' ', '_')}_{date.today().isoformat()}.pdf",
                                defaultextension=".pdf",
                                filetypes=[("Archivo PDF", "*.pdf")]
                            )
                            if filename:
                                config = obtener_configuracion()
                                datos_vale = {
                                    'folio': f"{date.today().strftime('%Y%m%d')}-{movil_seleccionado.split()[-1]}",
                                    'fecha': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                    'movil': movil_seleccionado,
                                    'tecnico': 'N/A',
                                    'usuario': self.main_app.usuario_actual or 'Admin'
                                }
                                exito_pdf, msg_pdf = generar_vale_despacho(datos_vale, productos_pdf, filename)
                                if exito_pdf:
                                    mostrar_mensaje_emergente(self.master, "PDF Guardado", f"Vale de despacho generado: {filename}", "success")
                                else:
                                    mostrar_mensaje_emergente(self.master, "Error PDF", f"No se pudo generar el PDF: {msg_pdf}", "error")
                    
                    ventana.destroy()
                else:
                    mensaje = f"Éxitos: {exitos}\\nErrores: {errores}\\n\\nDetalles:\\n"
                    mensaje += "\\n".join(errores_detalle[:5])
                    if len(errores_detalle) > 5:
                        mensaje += f"\\n... y {len(errores_detalle) - 5} errores más"
                    mostrar_mensaje_emergente(ventana, "Proceso Finalizado con Errores", mensaje, "warning")
                
                # Crear recordatorios automáticos
                if exitos > 0 and paquete in ['PAQUETE A', 'PAQUETE B']:
                    self.crear_recordatorios_automaticos(fecha_evento)
                
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
            
            def procesar_salida_manual():
                """Procesa salida usando cantidades manuales (código original)"""
                movil_seleccionado = movil_combo.get()
                fecha_evento = fecha_entry.get()
                paquete = paquete_combo.get() if paquete_combo.get() != "NINGUNO" else None
    
                exitos = 0
                errores = 0
                mensaje_error = ""
    
                for sku, entry in self.salida_entries.items():
                    try:
                        cantidad_text = entry.get().strip()
                        if cantidad_text:  # Solo procesar si hay valor ingresado
                            cantidad = int(cantidad_text)
                            if cantidad > 0:
                                # VERIFICACIÓN DE STOCK (PUNTO 5)
                                disponible, stock = verificar_stock_disponible(sku, cantidad)
                                if not disponible:
                                    errores += 1
                                    mensaje_error += f"\n- {sku}: Stock insuficiente ({stock} < {cantidad})"
                                    entry.configure(bg='#FFCDD2')
                                    continue
    
                                exito, mensaje = registrar_movimiento_gui(sku, 'SALIDA_MOVIL', cantidad, movil_seleccionado, fecha_evento, paquete)
                                if exito:
                                    exitos += 1
                                else:
                                    errores += 1
                                    mensaje_error += f"\n- SKU {sku}: {mensaje}"
                    except ValueError:
                        if cantidad_text:  # Solo mostrar error si hay texto no numérico
                            errores += 1
                            mensaje_error += f"\n- SKU {sku}: Cantidad no válida"
                    except Exception as e:
                        errores += 1
                        mensaje_error += f"\n- SKU {sku} (Error Inesperado): {e}"
    
                if exitos > 0 or errores > 0:
                    if errores > 0:
                        mostrar_mensaje_emergente(ventana, "Proceso Finalizado con Errores", 
                                                    f"Se completaron {exitos} salidas y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                    "warning")
                    else:
                        mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} salidas exitosamente.", "success")
                        
                        # PUNTO 2: Ofrecer generar Vale de Despacho en PDF
                        if messagebox.askyesno("Vale de Despacho", "¿Desea generar el Vale de Despacho en PDF para este movimiento?"):
                            # Preparar lista de productos procesados
                            productos_pdf = []
                            for sku, entry in self.salida_entries.items():
                                c_text = entry.get().strip()
                                if c_text and int(c_text) > 0:
                                    # Buscar nombre del producto
                                    nombre_p = "Producto"
                                    for p in productos: # 'productos' is local to abrir_ventana_salida_movil
                                         if str(p[1]) == str(sku):
                                             nombre_p = p[0]
                                             break
                                    productos_pdf.append((sku, nombre_p, c_text))
                            
                            if productos_pdf:
                                filename = filedialog.asksaveasfilename(
                                    title="Guardar Vale de Despacho",
                                    initialfile=f"Vale_{movil_seleccionado.replace(' ', '_')}_{date.today().isoformat()}.pdf",
                                    defaultextension=".pdf",
                                    filetypes=[("Archivo PDF", "*.pdf")]
                                )
                                if filename:
                                    config = obtener_configuracion()
                                    datos_vale = {
                                        'folio': f"{date.today().strftime('%Y%m%d')}-{movil_seleccionado.split()[-1]}",
                                        'fecha': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                        'movil': movil_seleccionado,
                                        'tecnico': 'N/A', # Could be expanded later
                                        'usuario': self.main_app.usuario_actual or 'Admin'
                                    }
                                    exito_pdf, msg_pdf = generar_vale_despacho(datos_vale, productos_pdf, filename)
                                    if exito_pdf:
                                        mostrar_mensaje_emergente(self.master, "PDF Guardado", f"Vale de despacho generado: {filename}", "success")
                                    else:
                                        mostrar_mensaje_emergente(self.master, "Error PDF", f"No se pudo generar el PDF: {msg_pdf}", "error")
    
                elif exitos == 0 and errores == 0:
                    mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")
    
                # Crear recordatorios automáticos
                if exitos > 0 and paquete in ['PAQUETE A', 'PAQUETE B']:
                    self.crear_recordatorios_automaticos(fecha_evento)
    
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
    
            tk.Button(ventana, text="Procesar Salida a Móvil", 
                      command=procesar_salida, 
                      bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

        # Iniciar carga async
        self._mostrar_cargando_async(ventana, carga_datos, construir_ui)

    
    def abrir_ventana_retorno_movil(self):
        """
        Ventana Unificada de Retorno y Auditoría (Punto 5 + Correcciones User)
        Flujo:
        1. Selección de Móvil
        2. Auditoría de Consumo (Excel vs App) -> Determina "Consumo Verificado"
        3. Auditoría de Stock (Físico vs [Asignado - Consumo Verificado])
        4. Retorno Final
        """
        ventana = tk.Toplevel(self.master)
        ventana.title("🔄 Auditoría de Retorno y Cierre")
        try: 
            ventana.state('zoomed')
        except: 
            ventana.wm_attributes('-fullscreen', True)
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()

        # --- ESTRUCTURA DE DATOS DE LA SESIÓN ---
        session_data = {
            'movil': None,
            'fecha': date.today().isoformat(),
            'excel_data': [], # SKUs del Excel de Activaciones
            'stock_teorico': {}, # {sku: qty} (Base de Datos)
            'consumo_app': {}, # {sku: qty} (Reportado en App)
            'consumo_verificado': {}, # {sku: qty} (Match Excel <-> App)
            'stock_fisico_escaneado': {}, # {sku: qty}
            'discrepancias_consumo': [],
            'discrepancias_fisicas': []
        }

        # --- UI LAYOUT ---
        header = tk.Frame(ventana, bg=Styles.PRIMARY_COLOR, height=70)
        header.pack(fill='x'); header.pack_propagate(False)
        tk.Label(header, text="🛡️ AUDITORÍA DE TERRENO Y RETORNO", font=('Segoe UI', 18, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=15)

        main_frame = tk.Frame(ventana, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # SECCIÓN 1: SELECCIÓN Y CARGA (TOP)
        top_panel = tk.LabelFrame(main_frame, text="1. Configuración de Retorno", bg='white', font=('Segoe UI', 10, 'bold'))
        top_panel.pack(fill='x', pady=5)
        
        # Móvil Selector
        tk.Label(top_panel, text="Móvil / Técnico:", bg='white').pack(side='left', padx=10, pady=10)
        movil_combo = ttk.Combobox(top_panel, width=25, state='readonly')
        movil_combo.pack(side='left', padx=5)
        
        # Cargar Móviles
        def _load_moviles():
            ms = obtener_nombres_moviles()
            movil_combo['values'] = ms
        threading.Thread(target=_load_moviles, daemon=True).start()

        tk.Label(top_panel, text="Fecha:", bg='white').pack(side='left', padx=(20, 10))
        entry_fecha = tk.Entry(top_panel, width=12)
        entry_fecha.insert(0, session_data['fecha'])
        entry_fecha.pack(side='left')

        # SECCIÓN 2: AUDITORÍA DE CONSUMO (Left)
        left_panel = tk.LabelFrame(main_frame, text="2. Auditoría de Consumo (Activaciones vs App)", bg='white', font=('Segoe UI', 10, 'bold'), width=500)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10), pady=5)
        
        btn_import_excel = tk.Button(left_panel, text="📥 Cargar Excel Activaciones", bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9))
        btn_import_excel.pack(pady=5)
        
        tree_consumo = ttk.Treeview(left_panel, columns=('Producto', 'App', 'Excel', 'Dif'), show='headings')
        tree_consumo.heading('Producto', text='Producto'); tree_consumo.column('Producto', width=150)
        tree_consumo.heading('App', text='App'); tree_consumo.column('App', width=50, anchor='center')
        tree_consumo.heading('Excel', text='Activ.'); tree_consumo.column('Excel', width=50, anchor='center')
        tree_consumo.heading('Dif', text='Estado'); tree_consumo.column('Dif', width=80, anchor='center')
        tree_consumo.pack(fill='both', expand=True, padx=5, pady=5)
        
        tree_consumo.tag_configure('ok', background='#d4edda')
        tree_consumo.tag_configure('error', background='#f8d7da')

        # SECCIÓN 3: AUDITORÍA FÍSICA (Right)
        right_panel = tk.LabelFrame(main_frame, text="3. Auditoría Física (Stock Esperado vs Real)", bg='white', font=('Segoe UI', 10, 'bold'))
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0), pady=5)
        
        scan_frame = tk.Frame(right_panel, bg='white')
        scan_frame.pack(fill='x', pady=5)
        tk.Label(scan_frame, text="🔍 ESCANEAR:", fg=Styles.PRIMARY_COLOR, font=('Segoe UI', 12, 'bold'), bg='white').pack(side='left', padx=10)
        entry_scan = tk.Entry(scan_frame, font=('Segoe UI', 12), width=25, bg='#e8f0fe')
        entry_scan.pack(side='left', padx=5)
        entry_scan.focus_set()

        tree_fisico = ttk.Treeview(right_panel, columns=('SKU', 'Producto', 'Esperado', 'Escaneado', 'Estado'), show='headings')
        tree_fisico.heading('SKU', text='SKU'); tree_fisico.column('SKU', width=80)
        tree_fisico.heading('Producto', text='Producto'); tree_fisico.column('Producto', width=150)
        tree_fisico.heading('Esperado', text='Deben Tener', anchor='center')
        tree_fisico.column('Esperado', width=80)
        tree_fisico.heading('Escaneado', text='Físico', anchor='center')
        tree_fisico.column('Escaneado', width=80)
        tree_fisico.heading('Estado', text='Estado', anchor='center')
        tree_fisico.column('Estado', width=80)
        tree_fisico.pack(fill='both', expand=True, padx=5, pady=5)
        
        tree_fisico.tag_configure('found', background='#d4edda') # Verde (Ok)
        tree_fisico.tag_configure('missing', background='#f8d7da') # Rojo (Falta)
        tree_fisico.tag_configure('extra', background='#fff3cd') # Amarillo (Sobra)

        # --- ACTIONS ---
        bottom_panel = tk.Frame(ventana, bg='#f8f9fa', height=60)
        bottom_panel.pack(fill='x', side='bottom')
        
        btn_procesar = tk.Button(bottom_panel, text="✅ Finalizar Auditoría y Retorno", 
                               bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                               state='disabled', padx=20, pady=10)
        btn_procesar.pack(side='right', padx=20, pady=10)

        # --- LOGIC ---
        
        def reset_session():
            session_data['stock_teorico'] = {}
            session_data['consumo_app'] = {}
            session_data['consumo_verificado'] = {}
            session_data['stock_fisico_escaneado'] = {}
            session_data['excel_data'] = []
            # Clear trees
            for i in tree_consumo.get_children(): tree_consumo.delete(i)
            for i in tree_fisico.get_children(): tree_fisico.delete(i)
            btn_procesar.config(state='disabled')

        def on_movil_select(event):
            movil = movil_combo.get()
            if not movil: return
            session_data['movil'] = movil
            reset_session()
            
            # Load Data
            self._mostrar_cargando_async(ventana, lambda: _fetch_mobile_data(movil), _on_data_loaded)

        def _fetch_mobile_data(movil):
            # 1. Get Assigned Stock (Total Assigned - Total Returned previously)
            # Actually, `obtener_asignacion_movil_con_paquetes` gives current snapshot of `asignacion_moviles` table
            # which IS the current stock assigned.
            asignados = obtener_asignacion_movil_con_paquetes(movil) # [(name, sku, total, ...)]
            
            stock_actual = {} # {sku: {name:.., qty:..}}
            for name, sku, total, _, _, _ in asignados:
                 stock_actual[sku] = {'name': name, 'qty': total}

            # 2. Get Pending Consumption (Forms submitted in App but not audits)
            # Use `obtener_consumos_pendientes` logic but specific to this mobile
            # We need a new/reused DB function that filters by mobile efficiently?
            # Existing `obtener_consumos_pendientes` returns all. Filtering in python for now.
            from database import obtener_consumos_pendientes
            pendientes = obtener_consumos_pendientes() # (id, movil, sku, nombre, qty, ...)
            
            consumo_reportado = {} # {sku: qty}
            for p in pendientes:
                # p[1] is movil. Normalize.
                if str(p[1]).strip().upper() == movil.strip().upper():
                    sku = p[2]
                    qty = int(p[4])
                    consumo_reportado[sku] = consumo_reportado.get(sku, 0) + qty
            
            return {'stock': stock_actual, 'consumo': consumo_reportado}

        def _on_data_loaded(data):
            session_data['stock_teorico'] = data['stock'] # {sku: {name, qty}}
            session_data['consumo_app'] = data['consumo'] # {sku: qty}
            update_consumo_ui()
            update_fisico_ui()
            
        def update_consumo_ui():
            # Clear
            for i in tree_consumo.get_children(): tree_consumo.delete(i)
            
            # Union of App SKUs and Excel SKUs
            all_skus = set(session_data['consumo_app'].keys()) | set([x['sku'] for x in session_data['excel_data']])
            
            for sku in all_skus:
                # Get Name
                name = "Desconocido"
                if sku in session_data['stock_teorico']:
                    name = session_data['stock_teorico'][sku]['name']
                
                qty_app = session_data['consumo_app'].get(sku, 0)
                
                # Calculate Excel Qty for this SKU
                qty_excel = 0
                for item in session_data['excel_data']:
                    if item['sku'] == sku:
                        qty_excel += item['qty']
                
                # Compare
                diff = qty_excel - qty_app
                status = "Correcto"
                tag = 'ok'
                
                if diff != 0:
                    status = f"Dif: {diff}"
                    tag = 'error'
                    
                # Store Verified Consumption (we trust Excel/App match or take max/min? User logic: "lo que colocaron en app y fisico es igual")
                # Logic: If App says 5 used, and Excel says 5 used -> 5 consumed.
                # If App 5, Excel 0 -> 0 consumed? Or 5? 
                # User says: "comparado con excel... donde realmente lo que colocaron en esa app... y lo fisico es igual"
                # Assumption: Valid Consumption = What is in Excel (Activated). 
                # If they reported in App but didn't activate, they still have it?
                # Let's assume Valid Consumption = Excel Qty.
                session_data['consumo_verificado'][sku] = qty_excel
                
                tree_consumo.insert('', 'end', values=(name, qty_app, qty_excel, status), tags=(tag,))

            update_fisico_ui() # Recalc expected stock based on verified consumption

        def update_fisico_ui():
            for i in tree_fisico.get_children(): tree_fisico.delete(i)
            
            # Expected Stock = Current Assurance (DB) - Verified Consumption (Excel)
            # PROBLEM: DB `asignacion_moviles` already matches what they HAVE.
            # When they report consumption in App, does it deduct from DB immediately or go to pending?
            # It goes to `consumos_pendientes`. So `asignacion_moviles` is GROSS assigned.
            # So: Expected Physical = Assigned_DB - Verified_Consumption
            
            all_skus = set(session_data['stock_teorico'].keys()) | set(session_data['stock_fisico_escaneado'].keys())
            
            for sku in all_skus:
                info = session_data['stock_teorico'].get(sku, {'name': 'Material Extra', 'qty': 0})
                name = info['name']
                gross_assigned = info['qty']
                
                consumed = session_data['consumo_verificado'].get(sku, 0)
                expected = gross_assigned - consumed
                if expected < 0: expected = 0 # Should not happen unless imported excel has more activations than assigned stock
                
                scanned = session_data['stock_fisico_escaneado'].get(sku, 0)
                
                # Logic
                if scanned == expected:
                    state = "✅ OK"
                    tag = 'found'
                elif scanned < expected:
                    state = f"❌ Faltan {expected - scanned}"
                    tag = 'missing'
                else:
                    state = f"⚠️ Sobran {scanned - expected}"
                    tag = 'extra'
                
                tree_fisico.insert('', 'end', values=(sku, name, expected, scanned, state), tags=(tag,))
            
            # Enable finish if items scanned
            if session_data['stock_fisico_escaneado']:
                btn_procesar.config(state='normal')

        def load_excel_activations():
            filename = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
            if not filename: return
            
            try:
                df = pd.read_excel(filename)
                
                # Mapa de SKUs
                map_sku = {}
                for n, s, _ in PRODUCTOS_INICIALES: 
                    # Normalizar: eliminar espacios, mayus, etc
                    key = str(n).upper().strip().replace(' ', '').replace('_', '')
                    map_sku[key] = s
                    # Tambien mapear el SKU directo
                    key_sku = str(s).upper().strip().replace(' ', '').replace('_', '')
                    map_sku[key_sku] = s
                
                found_data = [] 
                
                # Iterar columnas
                for col in df.columns:
                    col_u = str(col).upper().strip().replace(' ', '').replace('_', '')
                    
                    # Logica de match fuzzy simple
                    sku_target = None
                    
                    # 1. Direct match
                    if col_u in map_sku: 
                        sku_target = map_sku[col_u]
                    else:
                        # 2. Contains match (slow but effective for weird headers)
                        for k, s in map_sku.items():
                            if k in col_u or col_u in k:
                                sku_target = s
                                break
                    
                    if sku_target:
                        # Sumar columna
                        try:
                            # Convert to numeric, forcing errors to NaN then 0
                            qty_col = pd.to_numeric(df[col], errors='coerce').fillna(0).sum()
                            if qty_col > 0:
                                found_data.append({'sku': sku_target, 'qty': int(qty_col)})
                        except:
                            pass

                session_data['excel_data'] = found_data
                update_consumo_ui()
                messagebox.showinfo("Carga Excel", f"Se detectaron {len(found_data)} productos con consumo en el Excel.")
                
            except Exception as e:
                messagebox.showerror("Error Excel", f"Fallo al leer Excel: {e}")

        def on_scan(event):
            code = entry_scan.get().strip().upper()
            if not code: return
            entry_scan.delete(0, tk.END)
            
            movil = session_data.get('movil')
            if not movil:
                messagebox.showerror("Error", "Debe seleccionar un móvil primero")
                return
            
            # Buscar información del serial en la BD
            sku, ubicacion = obtener_info_serial(code)
            
            # VALIDACIÓN 1: Verificar que el serial existe
            if not sku:
                messagebox.showerror("Serial No Encontrado", 
                                   f"El serial '{code}' no existe en la base de datos.")
                return
            
            # VALIDACIÓN 2: Verificar que pertenece al móvil que está retornando
            if ubicacion != movil:
                messagebox.showerror("Serial No Pertenece", 
                                   f"❌ El serial '{code}' NO pertenece a {movil}.\n\n"
                                   f"Ubicación actual: {ubicacion}\n"
                                   f"Móvil seleccionado: {movil}")
                return
            
            # VALIDACIÓN 3: Evitar duplicados en la misma sesión
            # Contar cuántos de este serial ya se escanearon
            seriales_escaneados_key = f"_seriales_{sku}"
            if seriales_escaneados_key not in session_data:
                session_data[seriales_escaneados_key] = []
            
            if code in session_data[seriales_escaneados_key]:
                messagebox.showwarning("Duplicado", 
                                     f"⚠️ El serial '{code}' ya fue escaneado en esta sesión.")
                return
            
            # Todo OK - Registrar escaneo
            session_data[seriales_escaneados_key].append(code)
            session_data['stock_fisico_escaneado'][sku] = session_data['stock_fisico_escaneado'].get(sku, 0) + 1
            
            # Feedback visual
            entry_scan.config(bg='#d4edda')  # Verde
            ventana.after(200, lambda: entry_scan.config(bg='#e8f0fe'))  # Volver a azul claro
            
            update_fisico_ui()

        def finalizar():
            if not messagebox.askyesno("Confirmar Cierre", 
                                       "¿Está seguro de procesar esta auditoría?\n\n"
                                       "1. Se descontarán los consumos verificados (Excel).\n"
                                       "2. Se retornarán los equipos físicos escaneados.\n"
                                       "3. Se limpiarán los pendientes de la App."):
                return

            exitos_consumo = 0
            exitos_retorno = 0
            errors = []
            
            # 1. PROCESAR CONSUMO (Lo que dijo el Excel)
            fecha_evento = entry_fecha.get()
            movil = session_data['movil']
            
            for sku, qty in session_data['consumo_verificado'].items():
                if qty > 0:
                    ok, msg = registrar_movimiento_gui(
                        sku, 'CONSUMO_MOVIL', qty, movil, 
                        fecha_evento, None, "Auditoría Automática (Excel)"
                    )
                    if ok: exitos_consumo += 1
                    else: errors.append(f"Consumo {sku}: {msg}")
            
            # 2. PROCESAR RETORNO (Lo que se escaneó)
            for sku, qty in session_data['stock_fisico_escaneado'].items():
                if qty > 0:
                    ok, msg = registrar_movimiento_gui(
                        sku, 'RETORNO_MOVIL', qty, movil,
                        fecha_evento, None, "Retorno Auditado"
                    )
                    if ok: exitos_retorno += 1
                    else: errors.append(f"Retorno {sku}: {msg}")
            
            # 3. LIMPIEZA DE PENDIENTES (Flush consumos_pendientes for this mobile)
            # Find pendings for this mobile and mark processed/deleted
            # Since we recorded the unified consumption, we can delete the individual pendings 
            # to avoid double counting if someone uses the old system, or just to keep DB clean.
            try:
                pendientes = obtener_consumos_pendientes()
                ids_to_clean = [p[0] for p in pendientes if str(p[1]).upper() == str(movil).upper()]
                from database import eliminar_consumo_pendiente
                for pid in ids_to_clean:
                    eliminar_consumo_pendiente(pid)
            except Exception as e:
                print(f"Error limpiando pendientes: {e}")

            # REPORT
            summary = f"Proceso Completado.\n\nConsumos Registrados: {exitos_consumo}\nRetornos Registrados: {exitos_retorno}"
            if errors:
                summary += f"\n\nErrores:\n" + "\n".join(errors[:5])
                messagebox.showwarning("Resultado con Alertas", summary)
            else:
                messagebox.showinfo("Éxito Total", summary)
            
            ventana.destroy()
            if hasattr(self.main_app, 'dashboard_tab'):
                try: self.main_app.dashboard_tab.actualizar_metricas()
                except: pass

        # Bindings
        movil_combo.bind("<<ComboboxSelected>>", on_movil_select)
        entry_scan.bind("<Return>", on_scan)
        btn_import_excel.config(command=load_excel_activations)
        btn_procesar.config(command=finalizar)

        # Initial focus
        entry_fecha.focus_set()


    def abrir_ventana_consiliacion(self):
        """Abre ventana para consiliación con lógica de paquetes"""
        ventana = tk.Toplevel(self.master)
        ventana.title("⚖️ Consiliación - Con Paquetes")
        try: 
            ventana.state('zoomed')
        except tk.TclError: 
            ventana.wm_attributes('-fullscreen', True)
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="⚖️ CONCILIACIÓN", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Frame de selectores
        frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#E1BEE7')
        frame_selector.pack(fill='x')
        
        tk.Label(frame_selector, text="Móvil:", font=('Segoe UI', 10, 'bold'), bg='#E1BEE7').pack(side=tk.LEFT)
        moviles_db = obtener_nombres_moviles()
        movil_combo = ttk.Combobox(frame_selector, values=moviles_db, state="readonly", width=15)
        movil_combo.set("--- Seleccionar Móvil ---")
        movil_combo.pack(side=tk.LEFT, padx=10)
        
        # Selector de Paquete
        PAQUETES_DISPONIBLES = ["NINGUNO", "PAQUETE A", "PAQUETE B", "CARRO"]
        tk.Label(frame_selector, text="Paquete Asignado:", font=('Segoe UI', 10, 'bold'), bg='#E1BEE7').pack(side=tk.LEFT, padx=(20, 5))
        paquete_combo = ttk.Combobox(frame_selector, values=PAQUETES_DISPONIBLES, state="readonly", width=15)
        paquete_combo.set("NINGUNO")
        paquete_combo.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#E1BEE7').pack(side=tk.LEFT, padx=(20, 5))
        fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
        fecha_entry.insert(0, date.today().isoformat())
        fecha_entry.pack(side=tk.LEFT)
        
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
        
        self.consiliacion_entries = {}
        
        def cargar_productos_movil_con_paquetes(event=None):
            movil = movil_combo.get()
            paquete_seleccionado = paquete_combo.get()
            
            if movil == "--- Seleccionar Móvil ---":
                return
            
            # Limpiar tabla
            for widget in frame_productos.winfo_children():
                if int(widget.grid_info().get("row", 0)) > 0:
                    widget.destroy()
            
            self.consiliacion_entries.clear()
            
            productos_asignados = obtener_asignacion_movil_con_paquetes(movil)
            if not productos_asignados:
                tk.Label(frame_productos, text="No hay productos asignados a este móvil", 
                        font=('Segoe UI', 10), fg='red').grid(row=1, column=0, columnspan=5, padx=10, pady=10)
                return
            
            # Encabezados
            tk.Label(frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Stock Total Móvil", font=('Segoe UI', 10, 'bold'), fg='blue').grid(row=0, column=2, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Stock del Paquete", font=('Segoe UI', 10, 'bold'), fg='green').grid(row=0, column=3, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Cant. Consumida", font=('Segoe UI', 10, 'bold')).grid(row=0, column=4, padx=5, pady=5, sticky='w')
            
            fila = 1
            for nombre, sku, total, paquete_a, paquete_b, carro in productos_asignados:
                cantidad_paquete = 0
                if paquete_seleccionado == "PAQUETE A":
                    cantidad_paquete = paquete_a
                elif paquete_seleccionado == "PAQUETE B":
                    cantidad_paquete = paquete_b
                elif paquete_seleccionado == "CARRO":
                    cantidad_paquete = carro
                elif paquete_seleccionado == "NINGUNO":
                    cantidad_paquete = total
                
                tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9)).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
                tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
                tk.Label(frame_productos, text=str(total), anchor='center', font=('Segoe UI', 9), fg='blue').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
                
                if paquete_seleccionado != "NINGUNO" and cantidad_paquete == 0:
                    tk.Label(frame_productos, text="No disponible", anchor='center', font=('Segoe UI', 9), fg='red').grid(row=fila, column=3, padx=5, pady=2, sticky='ew')
                else:
                    tk.Label(frame_productos, text=str(cantidad_paquete), anchor='center', font=('Segoe UI', 9), fg='green').grid(row=fila, column=3, padx=5, pady=2, sticky='ew')
                
                entry = tk.Entry(frame_productos, width=8, font=('Segoe UI', 9))
                entry.grid(row=fila, column=4, padx=5, pady=2)
                
                if paquete_seleccionado != "NINGUNO" and cantidad_paquete > 0:
                    entry.insert(0, str(cantidad_paquete))
                
                self.consiliacion_entries[sku] = entry
                fila += 1
            
            frame_productos.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))
        
        movil_combo.bind("<<ComboboxSelected>>", cargar_productos_movil_con_paquetes)
        paquete_combo.bind("<<ComboboxSelected>>", cargar_productos_movil_con_paquetes)
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        def procesar_consiliacion():
            movil_seleccionado = movil_combo.get()
            fecha_evento = fecha_entry.get().strip()
            paquete = paquete_combo.get() if paquete_combo.get() != "NINGUNO" else None
            
            if movil_seleccionado == "--- Seleccionar Móvil ---":
                mostrar_mensaje_emergente(ventana, "Error", "Debe seleccionar un Móvil.", "error")
                return
                
            if not fecha_evento:
                mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
                return

            exitos = 0
            errores = 0
            mensaje_error = ""

            for sku, entry in self.consiliacion_entries.items():
                try:
                    cantidad_text = entry.get().strip()
                    if cantidad_text:
                        cantidad = int(cantidad_text)
                        if cantidad > 0:
                            exito, mensaje = registrar_movimiento_gui(sku, 'CONSUMO_MOVIL', cantidad, movil_seleccionado, fecha_evento, paquete)
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
                                                f"Se completaron {exitos} consumos y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                "warning")
                else:
                    mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} consumos exitosamente.", "success")
            elif exitos == 0 and errores == 0:
                mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")

            self.cargar_datos_tabla()
            if hasattr(self.main_app, 'dashboard_tab'):
                self.main_app.dashboard_tab.actualizar_metricas()
            ventana.destroy()

        tk.Button(ventana, text="Procesar Consumo", 
                  command=procesar_consiliacion, 
                  bg=Styles.WARNING_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

    def abrir_ventana_abasto(self):
        """Abre ventana para registro de abasto"""
        AbastoWindow(self.main_app, mode='registrar')

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

