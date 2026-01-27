import tkinter as tk
from tkinter import ttk, messagebox, Canvas, Scrollbar
from datetime import date, datetime, timedelta
import os
import threading


from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente

from config import TIPOS_MOVIMIENTO, DATABASE_NAME
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
    obtener_nombres_moviles, verificar_stock_disponible
)
# Note: Some imports might be missing, I'll add them as I discover needs during implementation (e.g. exportar_a_csv)

from .reconciliation import abrir_ventana_conciliacion_excel
from .abasto import AbastoWindow
from .mobiles import MobilesManager
from .consumption import ConsumoTecnicoWindow
from .pdf_generator import generar_vale_despacho
from database import obtener_configuracion
from tkinter import filedialog

class InventoryTab:
    def __init__(self, notebook, main_app):
        self.notebook = notebook
        self.main_app = main_app
        self.master = main_app.master
        
        self.ubicacion_var = tk.StringVar()
        self.tabla = None
        
        self.create_widgets()

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
            ("📤 Préstamo Santiago", self.abrir_ventana_prestamo_bodega, '#607D8B'),
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
        
        # Usar un Canvas con scroll por si los campos no caben
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
        """Abre ventana para salida individual desde bodega"""
        productos = obtener_todos_los_skus_para_movimiento()
        if not productos:
            mostrar_mensaje_emergente(self.master, "Información", "No hay productos registrados.", "info")
            return

        ventana = tk.Toplevel(self.master)
        ventana.title("➖ Salida Individual desde Bodega")
        ventana.geometry("900x700")
        try: 
            ventana.state('zoomed')
        except tk.TclError: 
            ventana.wm_attributes('-fullscreen', True)
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
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
        
        self.salida_individual_entries = {}
        
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
            self.salida_individual_entries[sku] = entry
            fila += 1
            
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        def procesar_salida_individual():
            fecha_evento = fecha_entry.get().strip()
            observaciones = observaciones_entry.get().strip()
            
            if not fecha_evento:
                mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
                return

            exitos = 0
            errores = 0
            mensaje_error = ""

            for sku, entry in self.salida_individual_entries.items():
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

    def abrir_ventana_eliminar(self):
        """Abre ventana para eliminar producto con interfaz moderna"""
        productos = obtener_todos_los_skus_para_movimiento()
        if not productos:
            mostrar_mensaje_emergente(self.master, "Información", "No hay productos registrados.", "info")
            return

        ventana = tk.Toplevel(self.master)
        ventana.title("❌ Eliminar Producto")
        ventana.geometry("600x500")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
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

    def abrir_ventana_descarte(self):
        """Abre ventana para descarte con interfaz moderna"""
        productos = obtener_todos_los_skus_para_movimiento()
        if not productos:
            mostrar_mensaje_emergente(self.master, "Información", "No hay productos registrados.", "info")
            return

        ventana = tk.Toplevel(self.master)
        ventana.title("🗑️ Registro de Descarte")
        ventana.geometry("800x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
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
        
        self.descarte_entries = {}
        
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
            self.descarte_entries[sku] = entry
            fila += 1
            
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        def procesar_descarte():
            fecha_evento = fecha_entry.get().strip()
            observaciones = observaciones_entry.get().strip()
            
            if not fecha_evento:
                mostrar_mensaje_emergente(ventana, "Error", "La fecha del evento es obligatoria.", "error")
                return

            exitos = 0
            errores = 0
            mensaje_error = ""

            for sku, entry in self.descarte_entries.items():
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

    def abrir_ventana_traslado(self):
        """Abre ventana para traslado entre móviles con interfaz moderna"""
        ventana = tk.Toplevel(self.master)
        ventana.title("🔄 Traslado entre Móviles")
        ventana.geometry("900x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
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
        moviles_db = obtener_nombres_moviles()
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
        
        self.traslado_entries = {}
        
        def cargar_productos_movil(event=None):
            movil_origen = movil_origen_combo.get()
            if movil_origen == "--- Seleccionar ---":
                return
            
            # Limpiar tabla
            for widget in frame_productos.winfo_children():
                if int(widget.grid_info().get("row", 0)) > 0:
                    widget.destroy()
            
            self.traslado_entries.clear()
            
            # Obtener productos del móvil origen
            productos_asignados = obtener_asignacion_movil(movil_origen)
            if not productos_asignados:
                tk.Label(frame_productos, text="No hay productos asignados a este móvil", 
                        font=('Segoe UI', 10), fg='red').grid(row=1, column=0, columnspan=4, padx=10, pady=10)
                return
            
            # Encabezados
            tk.Label(frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Stock en Móvil", font=('Segoe UI', 10, 'bold'), fg='blue').grid(row=0, column=2, padx=5, pady=5, sticky='w')
            tk.Label(frame_productos, text="Cant. a Trasladar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
            
            fila = 1
            for nombre, sku, cantidad in productos_asignados:
                tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9)).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
                tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
                tk.Label(frame_productos, text=str(cantidad), anchor='center', font=('Segoe UI', 9), fg='blue').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
                entry = tk.Entry(frame_productos, width=8, font=('Segoe UI', 9))
                entry.grid(row=fila, column=3, padx=5, pady=2)
                self.traslado_entries[sku] = entry
                fila += 1
            
            frame_productos.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))
        
        movil_origen_combo.bind("<<ComboboxSelected>>", cargar_productos_movil)
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
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

            for sku, entry in self.traslado_entries.items():
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

    def abrir_ventana_prestamo_bodega(self):
        """Abre ventana para préstamo a Santiago con interfaz moderna"""
        productos = obtener_todos_los_skus_para_movimiento()
        if not productos:
            mostrar_mensaje_emergente(self.master, "Información", "No hay productos registrados.", "info")
            return

        ventana = tk.Toplevel(self.master)
        ventana.title("📤 Préstamo a Santiago")
        ventana.geometry("800x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg='#607D8B', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📤 PRÉSTAMO A SANTIAGO", 
                font=('Segoe UI', 16, 'bold'), bg='#607D8B', fg='white').pack(pady=20)
        
        # Frame de selectores
        frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#ECEFF1')
        frame_selector.pack(fill='x')
        
        tk.Label(frame_selector, text="Fecha Préstamo (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#ECEFF1').pack(side=tk.LEFT)
        fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
        fecha_entry.insert(0, date.today().isoformat())
        fecha_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_selector, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#ECEFF1').pack(side=tk.LEFT, padx=(20, 5))
        observaciones_entry = tk.Entry(frame_selector, width=30, font=('Segoe UI', 10))
        observaciones_entry.pack(side=tk.LEFT, padx=10)
        
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
        
        self.prestamo_entries = {}
        
        # Encabezados
        tk.Label(frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        tk.Label(frame_productos, text="Stock Bodega", font=('Segoe UI', 10, 'bold'), fg='red').grid(row=0, column=2, padx=5, pady=5, sticky='w')
        tk.Label(frame_productos, text="Cant. a Prestar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
        
        fila = 1
        for nombre, sku, stock_actual in productos:
            tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9), wraplength=300).grid(row=fila, column=0, padx=5, pady=2, sticky='w')
            tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='w')
            tk.Label(frame_productos, text=str(stock_actual), anchor='center', font=('Segoe UI', 9), fg='red').grid(row=fila, column=2, padx=5, pady=2, sticky='w')
            entry = tk.Entry(frame_productos, width=10, font=('Segoe UI', 9))
            entry.grid(row=fila, column=3, padx=5, pady=2)
            self.prestamo_entries[sku] = entry
            fila += 1
            
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        def procesar_prestamo():
            fecha_evento = fecha_entry.get().strip()
            observaciones = observaciones_entry.get().strip()
            
            if not fecha_evento:
                mostrar_mensaje_emergente(ventana, "Error", "La fecha del préstamo es obligatoria.", "error")
                return

            exitos = 0
            errores = 0
            mensaje_error = ""

            for sku, entry in self.prestamo_entries.items():
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
                                                f"Se completaron {exitos} préstamos y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                "warning")
                else:
                    mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} préstamos exitosamente.", "success")
            elif exitos == 0 and errores == 0:
                mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")

            self.cargar_datos_tabla()
            if hasattr(self.main_app, 'dashboard_tab'):
                self.main_app.dashboard_tab.actualizar_metricas()
            ventana.destroy()

        tk.Button(ventana, text="Procesar Préstamo", 
                command=procesar_prestamo, 
                bg='#607D8B', fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

    def abrir_ventana_devolucion_santiago(self):
        """Abre ventana para devolución desde Santiago con interfaz moderna"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📥 Devolución desde Santiago")
        ventana.geometry("800x600")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg='#795548', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📥 DEVOLUCIÓN DESDE SANTIAGO", 
                font=('Segoe UI', 16, 'bold'), bg='#795548', fg='white').pack(pady=20)
        
        # Frame de contenido
        frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
        frame_contenido.pack(fill='both', expand=True)
        
        # Obtener préstamos activos
        prestamos_activos = obtener_prestamos_activos()
        
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
        
        # Tabla de préstamos activos
        frame_tabla = tk.Frame(frame_contenido)
        frame_tabla.pack(fill='both', expand=True)
        
        columns = ("SKU", "Producto", "Total Prestado", "Primera Fecha", "Observaciones")
        tabla_prestamos = ttk.Treeview(frame_tabla, columns=columns, show='headings', height=8)
        
        # Configurar columnas
        tabla_prestamos.heading("SKU", text="SKU")
        tabla_prestamos.heading("Producto", text="PRODUCTO")
        tabla_prestamos.heading("Total Prestado", text="TOTAL PRESTADO")
        tabla_prestamos.heading("Primera Fecha", text="PRIMERA FECHA")
        tabla_prestamos.heading("Observaciones", text="OBSERVACIONES")
        
        tabla_prestamos.column("SKU", width=100, anchor='center')
        tabla_prestamos.column("Producto", width=200)
        tabla_prestamos.column("Total Prestado", width=120, anchor='center')
        tabla_prestamos.column("Primera Fecha", width=120, anchor='center')
        tabla_prestamos.column("Observaciones", width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=tabla_prestamos.yview)
        tabla_prestamos.configure(yscrollcommand=scrollbar.set)
        
        tabla_prestamos.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def on_mousewheel(event):
            tabla_prestamos.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        tabla_prestamos.bind("<MouseWheel>", on_mousewheel)
        
        # Llenar tabla
        for sku, nombre, total, primera_fecha, obs in prestamos_activos:
            tabla_prestamos.insert('', 'end', values=(sku, nombre, total, primera_fecha, obs))
        
        # Entradas para devolución
        frame_devolucion = tk.Frame(frame_contenido, bg='#f8f9fa')
        frame_devolucion.pack(fill='x', pady=20)
        
        tk.Label(frame_devolucion, text="SKU a Devolver:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side=tk.LEFT)
        sku_entry = tk.Entry(frame_devolucion, width=15, font=('Segoe UI', 10))
        sku_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_devolucion, text="Cantidad a Devolver:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side=tk.LEFT, padx=(20, 5))
        cantidad_entry = tk.Entry(frame_devolucion, width=10, font=('Segoe UI', 10))
        cantidad_entry.pack(side=tk.LEFT, padx=10)
        
        def procesar_devolucion():
            sku = sku_entry.get().strip()
            cantidad_text = cantidad_entry.get().strip()
            fecha_devolucion = fecha_entry.get().strip()
            observaciones = observaciones_entry.get().strip()
            
            if not sku:
                mostrar_mensaje_emergente(ventana, "Error", "Debe ingresar un SKU.", "error")
                return
                
            if not cantidad_text:
                mostrar_mensaje_emergente(ventana, "Error", "Debe ingresar una cantidad.", "error")
                return
                
            if not fecha_devolucion:
                mostrar_mensaje_emergente(ventana, "Error", "La fecha de devolución es obligatoria.", "error")
                return
            
            try:
                cantidad = int(cantidad_text)
                if cantidad <= 0:
                    mostrar_mensaje_emergente(ventana, "Error", "La cantidad debe ser mayor a 0.", "error")
                    return
            except ValueError:
                mostrar_mensaje_emergente(ventana, "Error", "La cantidad debe ser un número válido.", "error")
                return
            
            exito, mensaje = registrar_devolucion_santiago(sku, cantidad, fecha_devolucion, observaciones)
            
            if exito:
                mostrar_mensaje_emergente(self.master, "Éxito", mensaje, "success")
                self.cargar_datos_tabla()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
                ventana.destroy()
            else:
                mostrar_mensaje_emergente(ventana, "Error", mensaje, "error")

        tk.Button(frame_contenido, text="Procesar Devolución", 
                command=procesar_devolucion, 
                bg='#795548', fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

    def abrir_ventana_prestamos_activos(self):
        """Abre ventana para ver préstamos activos con interfaz moderna"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📋 Préstamos Activos")
        ventana.geometry("1000x600")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg='#009688', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📋 PRÉSTAMOS ACTIVOS", 
                font=('Segoe UI', 16, 'bold'), bg='#009688', fg='white').pack(pady=20)
        
        # Frame de contenido
        frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
        frame_contenido.pack(fill='both', expand=True)
        
        # Obtener préstamos activos
        prestamos_activos = obtener_prestamos_activos()
        
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
        """Abre ventana para salida a móvil con botones de rellenar y limpiar"""
        productos = obtener_todos_los_skus_para_movimiento()
        if not productos:
            mostrar_mensaje_emergente(self.master, "Información", "No hay productos registrados.", "info")
            return

        ventana = tk.Toplevel(self.master)
        ventana.title("📤 Salida a Móvil - Con Paquetes")
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
        
        tk.Label(header_frame, text="📤 SALIDA A MÓVIL", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Frame de selectores
        frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#F8BBD0')
        frame_selector.pack(fill='x')
        
        tk.Label(frame_selector, text="Móvil Destino:", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT)
        moviles_db = obtener_nombres_moviles()
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

        self.salida_entries = {}
        
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

    def abrir_ventana_retorno_movil(self):
        """Abre ventana para retorno de móvil con lógica de paquetes"""
        ventana = tk.Toplevel(self.master)
        ventana.title("🔄 Retorno de Móvil - Con Paquetes")
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
        
        tk.Label(header_frame, text="🔄 RETORNO DE MÓVIL", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Frame de selectores
        frame_selector = tk.Frame(ventana, padx=20, pady=20, bg='#B3E5FC')
        frame_selector.pack(fill='x')
        
        tk.Label(frame_selector, text="Móvil Origen:", font=('Segoe UI', 10, 'bold'), bg='#B3E5FC').pack(side=tk.LEFT)
        moviles_db = obtener_nombres_moviles()
        movil_combo = ttk.Combobox(frame_selector, values=moviles_db, width=15)
        movil_combo.set("--- Seleccionar Móvil ---")
        movil_combo.pack(side=tk.LEFT, padx=10)
        # Usability: Select all text on click to allow easy typing
        movil_combo.bind("<FocusIn>", lambda e: movil_combo.selection_range(0, tk.END))
        
        # Selector de Paquete
        PAQUETES_DISPONIBLES = ["NINGUNO", "PAQUETE A", "PAQUETE B", "CARRO"]
        tk.Label(frame_selector, text="Paquete Asignado:", font=('Segoe UI', 10, 'bold'), bg='#B3E5FC').pack(side=tk.LEFT, padx=(20, 5))
        paquete_combo = ttk.Combobox(frame_selector, values=PAQUETES_DISPONIBLES, state="readonly", width=15)
        paquete_combo.set("NINGUNO")
        paquete_combo.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#B3E5FC').pack(side=tk.LEFT, padx=(20, 5))
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
        
        self.retorno_entries = {}
        
        def cargar_productos_movil_con_paquetes(event=None):
            movil = movil_combo.get()
            paquete_seleccionado = paquete_combo.get()
            
            if movil == "--- Seleccionar Móvil ---":
                return
            
            # Limpiar tabla
            for widget in frame_productos.winfo_children():
                if int(widget.grid_info().get("row", 0)) > 0:
                    widget.destroy()
            
            self.retorno_entries.clear()
            
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
            tk.Label(frame_productos, text="Cant. a Retornar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=4, padx=5, pady=5, sticky='w')
            
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
                # Auto-select text on focus
                entry.bind("<FocusIn>", lambda e: e.widget.selection_range(0, tk.END))
                
                if paquete_seleccionado != "NINGUNO" and cantidad_paquete > 0:
                    entry.insert(0, str(cantidad_paquete))
                
                self.retorno_entries[sku] = entry
                fila += 1
            
            frame_productos.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))
        
        movil_combo.bind("<<ComboboxSelected>>", cargar_productos_movil_con_paquetes)
        paquete_combo.bind("<<ComboboxSelected>>", cargar_productos_movil_con_paquetes)
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        def procesar_retorno():
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

            for sku, entry in self.retorno_entries.items():
                try:
                    cantidad_text = entry.get().strip()
                    if cantidad_text:
                        cantidad = int(cantidad_text)
                        if cantidad > 0:
                            exito, mensaje = registrar_movimiento_gui(sku, 'RETORNO_MOVIL', cantidad, movil_seleccionado, fecha_evento, paquete)
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
                                                f"Se completaron {exitos} retornos y ocurrieron {errores} errores. Revise los detalles:\n{mensaje_error}", 
                                                "warning")
                else:
                    mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} retornos exitosamente.", "success")
            elif exitos == 0 and errores == 0:
                mostrar_mensaje_emergente(ventana, "Información", "No se ingresó ninguna cantidad para procesar.", "info")

            self.cargar_datos_tabla()
            if hasattr(self.main_app, 'dashboard_tab'):
                self.main_app.dashboard_tab.actualizar_metricas()
            ventana.destroy()

        tk.Button(ventana, text="Procesar Retorno", 
                  command=procesar_retorno, 
                  bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

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

