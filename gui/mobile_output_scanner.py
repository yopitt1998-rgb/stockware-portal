import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date
import threading

from config import PAQUETE_INSTALACION, PRODUCTOS_CON_CODIGO_BARRA, CURRENT_CONTEXT
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente, mostrar_cargando_async
from utils.logger import get_logger

# Importaciones diferidas para evitar ciclos
# from database import ... (moved inside methods)
from .abasto import SerialCaptureDialog

logger = get_logger(__name__)


class MobileOutputScannerWindow:
    def __init__(self, master_app, mode='SALIDA_MOVIL', prefill_items=None, initial_movil=None, initial_package=None):
        self.master_app = master_app
        self.mode = mode
        self.prefill_items = prefill_items 
        self.initial_movil = initial_movil
        self.initial_package = initial_package
        self.window = tk.Toplevel(master_app.master)
        
        # Configurar título y colores según modo
        if self.mode == 'PRESTAMO_SANTIAGO':
            self.title_text = "Transferencia a Santiago"
            self.header_color = '#6f42c1' # Purple
            self.icon = "🚚"
        elif self.mode == 'DEVOLUCION_SANTIAGO':
            self.title_text = "Devolución de Santiago"
            self.header_color = '#fd7e14' # Orange
            self.icon = "↩️"
        elif self.mode == 'TRASLADO':
            self.title_text = "Traslado de Inventario"
            self.header_color = '#0dcaf0' # Cyan
            self.icon = "⇆"
        else: # SALIDA_MOVIL
            self.title_text = "Salida a Móvil (Escáner)"
            self.header_color = Styles.PRIMARY_COLOR
            self.icon = "🔫"

        self.window.title(f"{self.icon} {self.title_text}")
        self.window.geometry("1100x700")
        self.window.state('zoomed')
        self.window.configure(bg=Styles.LIGHT_BG)
        
        # State
        self.items_carrito = [] # List of dict: {sku, nombre, cantidad, seriales[], es_adicional}
        self.paquete_base = PAQUETE_INSTALACION if self.mode == 'SALIDA_MOVIL' else {}
        self.items_completados = {sku: 0 for sku in self.paquete_base}
        
        # Cache de productos
        self.productos_cache = {} # sku -> {nombre, stock}
        # Cache de detalles de seriales (serial -> {mac_number, ...})
        # Evita repetir consultas DB remotas por cada render de tabla
        self.serial_details_cache = {}
        
        self.create_interface()
        self.load_initial_data()
        
        # Prefill if items provided
        if self.prefill_items:
            for item in self.prefill_items:
                self.agregar_al_carrito(
                    item.get('sku'), 
                    item.get('nombre'), 
                    item.get('cantidad', 1), 
                    item.get('seriales', [])
                )
        
    def load_initial_data(self):
        def load():
            from database import obtener_nombres_moviles, obtener_todos_los_skus_para_movimiento, obtener_diccionarios_escaneo
            from config import CURRENT_CONTEXT
            branch = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
            
            # Cargar móviles
            moviles = obtener_nombres_moviles()
            
            # Cargar productos para validación rápida
            prods = obtener_todos_los_skus_para_movimiento()
            cache = {sku: {'nombre': nombre, 'stock': stock} for nombre, sku, stock in prods}
            
            # Cargar cachés de escaneo rápido
            seriales, barcodes = obtener_diccionarios_escaneo(sucursal_context=branch)
            
            return moviles, cache, seriales, barcodes
            
        def on_loaded(result):
            moviles, cache, seriales, barcodes = result
            self.combo_movil['values'] = moviles
            self.productos_cache = cache
            self.serial_cache = seriales
            self.barcode_cache = barcodes
            
            # Pre-seleccionar según modo o parámetros iniciales
            if self.initial_movil:
                self.combo_movil.set(self.initial_movil)
            elif self.mode == 'PRESTAMO_SANTIAGO':
                self.combo_movil.set("SANTIAGO")
                self.combo_movil.configure(state='disabled')
            elif self.mode == 'DEVOLUCION_SANTIAGO':
                self.combo_movil.set("CHIRIQUI")
                self.combo_movil.configure(state='disabled')
            
        mostrar_cargando_async(self.window, load, on_loaded, self.window)

    def create_interface(self):
        # Header
        header = tk.Frame(self.window, bg=self.header_color, pady=15)
        header.pack(fill='x')
        
        tk.Label(header, text=f"{self.icon} {self.title_text}", 
                font=('Segoe UI', 18, 'bold'), bg=self.header_color, fg='white').pack(side='left', padx=20)
                
        # Main Container
        main_container = tk.Frame(self.window, bg=Styles.LIGHT_BG)
        main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Left Panel: Controls & Scanner
        left_panel = tk.Frame(main_container, bg=Styles.LIGHT_BG)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Right Panel: Package Progress
        self.right_panel = tk.Frame(main_container, bg='white', width=350)
        self.right_panel.pack(side='right', fill='y', padx=(10, 0))
        self.right_panel.pack_propagate(False)
        
        self.crear_selector_movil(left_panel)
        self.crear_barra_scanner(left_panel)
        self.crear_tabla_items(left_panel)
        self.crear_botones_accion(left_panel)
        
        self.crear_panel_progreso(self.right_panel)
        
    def crear_selector_movil(self, parent):
        frame = tk.LabelFrame(parent, text="1. Seleccionar Móvil", font=('Segoe UI', 10, 'bold'),
                            bg=Styles.LIGHT_BG, fg=Styles.PRIMARY_COLOR, padx=15, pady=10)
        frame.pack(fill='x', pady=(0, 10))
        
        # Label dinámico según modo
        if self.mode == 'DEVOLUCION_SANTIAGO':
            label_movil = "Origen (Santiago) → Destino:"
        elif self.mode == 'PRESTAMO_SANTIAGO':
            label_movil = "Destino:"
        else:
            label_movil = "Móvil Destino:"
        tk.Label(frame, text=label_movil, bg=Styles.LIGHT_BG).pack(side='left', padx=5)
        
        self.combo_movil = ttk.Combobox(frame, state='readonly', width=30, font=('Segoe UI', 10))
        self.combo_movil.pack(side='left', padx=5)
        
        # Fecha
        tk.Label(frame, text="Fecha:", bg=Styles.LIGHT_BG).pack(side='left', padx=(20, 5))
        self.fecha_var = tk.StringVar(value=date.today().isoformat())
        tk.Entry(frame, textvariable=self.fecha_var, width=12, font=('Segoe UI', 10)).pack(side='left', padx=5)

        # Selector de Paquete (NUEVO)
        if self.mode == 'SALIDA_MOVIL':
            from config import PAQUETES_MATERIALES
            tk.Label(frame, text="Paquete:", bg=Styles.LIGHT_BG).pack(side='left', padx=(20, 5))
            self.lista_paquetes = list(PAQUETES_MATERIALES.keys()) + ["PERSONALIZADO"]
            self.combo_paquete = ttk.Combobox(frame, values=self.lista_paquetes, state='readonly', width=18, font=('Segoe UI', 10))
            
            start_paq = self.initial_package if self.initial_package and self.initial_package in self.lista_paquetes else "PAQUETE A"
            self.combo_paquete.set(start_paq)
            
            self.combo_paquete.pack(side='left', padx=5)
            self.combo_paquete.bind("<<ComboboxSelected>>", self.on_package_change)
            # Forzar actualización inicial del panel de progreso si hay paquete
            self.window.after(100, self.on_package_change)

    def crear_barra_scanner(self, parent):
        frame = tk.LabelFrame(parent, text="2. Escanear Productos", font=('Segoe UI', 10, 'bold'),
                            bg=Styles.LIGHT_BG, fg=Styles.PRIMARY_COLOR, padx=15, pady=10)
        frame.pack(fill='x', pady=10)
        
        tk.Label(frame, text="🔍 Código de Barras / SKU:", bg=Styles.LIGHT_BG).pack(side='left', padx=5)
        
        self.entry_scanner = tk.Entry(frame, font=('Segoe UI', 12), width=30)
        self.entry_scanner.pack(side='left', padx=5, fill='x', expand=True)
        self.entry_scanner.bind('<Return>', self.procesar_escaneo)
        self.entry_scanner.focus()
        
        tk.Button(frame, text="➕ Agregar Manual", command=self.agregar_manual,
                 bg=Styles.SECONDARY_COLOR, fg='white', relief='flat').pack(side='left', padx=10)

    def crear_tabla_items(self, parent):
        frame = tk.Frame(parent, bg=Styles.LIGHT_BG)
        frame.pack(fill='both', expand=True, pady=10)
        
        columns = ("SKU", "Producto", "Cantidad", "Series", "Tipo")
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        
        self.tree.heading("SKU", text="SKU")
        self.tree.heading("Producto", text="Producto")
        self.tree.heading("Cantidad", text="Cant.")
        self.tree.heading("Series", text="Series")
        self.tree.heading("Tipo", text="Tipo")
        
        self.tree.column("SKU", width=100)
        self.tree.column("Producto", width=300, minwidth=200)
        self.tree.column("Cantidad", width=60, anchor='center')
        self.tree.column("Series", width=150)
        self.tree.column("Tipo", width=100, anchor='center')
        
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        
        self.tree.bind('<Double-1>', self.editar_o_eliminar_item)

    def crear_botones_accion(self, parent):
        frame = tk.Frame(parent, bg=Styles.LIGHT_BG, pady=10)
        frame.pack(fill='x')
        
        tk.Button(frame, text="🔎 Búsqueda Manual", command=self.agregar_manual,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10).pack(side='left', padx=10)

        tk.Button(frame, text="❌ Cancelar", command=self.window.destroy,
                 bg='#6c757d', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10).pack(side='left')
                 
        self.btn_registrar = tk.Button(frame, text=f"💾 REGISTRAR", command=self.registrar_salida,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10)
        self.btn_registrar.pack(side='right')

    def crear_panel_progreso(self, parent):
        tk.Label(parent, text="📦 Progreso Paquete", font=('Segoe UI', 12, 'bold'),
                bg='white', fg=Styles.PRIMARY_COLOR).pack(pady=10)
        
        self.canvas_progreso = tk.Canvas(parent, bg='white', highlightthickness=0)
        self.scroll_progreso = ttk.Scrollbar(parent, orient="vertical", command=self.canvas_progreso.yview)
        
        self.frame_lista_progreso = tk.Frame(self.canvas_progreso, bg='white')
        
        self.canvas_progreso.create_window((0, 0), window=self.frame_lista_progreso, anchor="nw")
        self.canvas_progreso.configure(yscrollcommand=self.scroll_progreso.set)
        
        self.canvas_progreso.pack(side="left", fill="both", expand=True, padx=5)
        self.scroll_progreso.pack(side="right", fill="y")
        
        self.frame_lista_progreso.bind("<Configure>", lambda e: self.canvas_progreso.configure(scrollregion=self.canvas_progreso.bbox("all")))
        
        # Mousewheel local pattern (Recursive)
        def on_mousewheel(event):
            try:
                if self.canvas_progreso.winfo_exists():
                    self.canvas_progreso.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        def _bind_mousewheel_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                _bind_mousewheel_recursive(child)

        _bind_mousewheel_recursive(self.canvas_progreso)
        _bind_mousewheel_recursive(self.frame_lista_progreso)
        
        self.actualizar_panel_progreso()

    def actualizar_panel_progreso(self):
        for widget in self.frame_lista_progreso.winfo_children():
            widget.destroy()
            
        from config import MATERIALES_COMPARTIDOS
        
        for sku, cantidad_esperada in self.paquete_base.items():
            completado = self.items_completados.get(sku, 0)
            nombre = self.productos_cache.get(sku, {}).get('nombre', sku)
            es_compartido = sku in MATERIALES_COMPARTIDOS
            
            # Truncar nombre si es muy largo
            if len(nombre) > 25: nombre = nombre[:22] + "..."
            
            frame = tk.Frame(self.frame_lista_progreso, bg='white', pady=2)
            frame.pack(fill='x', padx=5)
            
            icon = "✅" if completado >= cantidad_esperada else "⬜"
            color = Styles.SUCCESS_COLOR if completado >= cantidad_esperada else "#666"
            
            tk.Label(frame, text=icon, bg='white').pack(side='left')
            tk.Label(frame, text=f"{nombre}", font=('Segoe UI', 9), bg='white', fg=color).pack(side='left')
            
            # Botón de auto-relleno si falta cantidad y NO es compartido
            if completado < cantidad_esperada and not es_compartido:
                btn_auto = tk.Button(frame, text="⚡", font=('Segoe UI', 8), 
                                     command=lambda s=sku, n=nombre, c=(cantidad_esperada - completado): self.auto_rellenar_item(s, n, c),
                                     bg='#f1c40f', fg='white', relief='flat', padx=2, pady=0)
                btn_auto.pack(side='right', padx=2)
            elif es_compartido:
                 tk.Label(frame, text="🏠", font=('Segoe UI', 8), bg='white', fg='#3498db').pack(side='right', padx=2)
            
            tk.Label(frame, text=f"{completado}/{cantidad_esperada}", font=('Segoe UI', 9, 'bold'), bg='white', fg=color).pack(side='right', padx=2)

    def auto_rellenar_item(self, sku, nombre, cantidad_faltante):
        """Auto-rellena un material (sin serial) en el carrito"""
        from config import PRODUCTOS_CON_CODIGO_BARRA
        es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA
        
        # Validación dinámica adicional basada en la base de datos
        if not es_equipo:
            try:
                from database import get_db_connection, close_connection
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT codigo_barra FROM productos WHERE sku = ? LIMIT 1", (sku,))
                    res = cursor.fetchone()
                    if res and res[0] and str(res[0]).lower() not in ['none', 'null', '']:
                         es_equipo = True
            except Exception as e:
                logger.error(f"Error verificando si el sku {sku} requiere serial: {e}")
            finally:
                if 'conn' in locals() and conn:
                    close_connection(conn)

        if es_equipo:
            messagebox.showinfo("Equipo con Serial", "Los equipos con serial deben escanearse uno a uno para registrar su MAC/Serial.", parent=self.window)
            return
            
        self.agregar_al_carrito(sku, nombre, cantidad_faltante, [])
        messagebox.showinfo("Auto-relleno", f"Se agregaron {cantidad_faltante} unidades de {nombre}.", parent=self.window)

    def on_package_change(self, event=None):
        """Maneja el cambio de paquete seleccionado"""
        from config import PAQUETES_MATERIALES
        seleccion = self.combo_paquete.get()
        
        if seleccion == "PERSONALIZADO":
            self.paquete_base = {}
        else:
            # Convertir lista de tuplas a dict
            self.paquete_base = {sku: cant for sku, cant in PAQUETES_MATERIALES.get(seleccion, [])}
            
        self.items_completados = {sku: 0 for sku in self.paquete_base}
        
        # Recalcular completados basados en el carrito actual
        for item in self.items_carrito:
            sku = item['sku']
            if sku in self.items_completados:
                self.items_completados[sku] += item['cantidad']
                
        self.actualizar_panel_progreso()
        logger.info(f"Paquete cambiado a: {seleccion}")

    def procesar_escaneo(self, event=None):
        """Procesa el código escaneado. El lookup de serial/barcode se hace en background
        para no bloquear la UI ante la latencia de MySQL remoto."""
        codigo = self.entry_scanner.get().strip().upper()
        self.entry_scanner.delete(0, tk.END)
        if not codigo:
            return

        # Deshabilitar el entry mientras se busca para evitar doble-escaneo
        self.entry_scanner.config(state='disabled')

        def buscar_en_background():
            """Ejecutado en hilo secundario: resuelve codigo -> (sku, origen_serial, nombre_serial, ubicacion)"""
            try:
                from database import obtener_sku_por_codigo_barra, obtener_sku_por_serial
            except ImportError:
                obtener_sku_por_codigo_barra = None
                obtener_sku_por_serial = None

            sku = codigo
            origen_serial = False
            nombre_serial = None
            ubicacion_actual = None

            # 1. Intentar reconocer como serial/MAC en memoria caché (INSTANTÁNEO)
            if hasattr(self, 'serial_cache') and codigo in self.serial_cache:
                sku_serial, ub = self.serial_cache[codigo]
                sku = sku_serial
                origen_serial = True
                nombre_serial = codigo
                ubicacion_actual = ub
                logger.debug(f"Cache Hit: Serial {codigo} -> SKU {sku} (Ubicación: {ub})")
            
            # 2. Búsqueda remota (Fallback) solo si no está en caché
            elif obtener_sku_por_serial:
                try:
                    sku_serial, existe, ub = obtener_sku_por_serial(codigo)
                    if existe:
                        sku = sku_serial
                        origen_serial = True
                        nombre_serial = codigo
                        ubicacion_actual = ub
                        logger.info(f"Fallback remoto: Serial {codigo} -> SKU {sku} (Ubicación: {ub})")
                except Exception as e:
                    logger.error(f"Error en auto-reconocimiento remoto de serial: {e}")

            # 3. Si no es serial, buscar por SKU/Barcode
            if not origen_serial:
                if codigo in self.productos_cache:
                    sku = codigo
                # Buscar en caché de códigos de barra en memoria (INSTANTÁNEO)
                elif hasattr(self, 'barcode_cache') and codigo in self.barcode_cache:
                    sku = self.barcode_cache[codigo]
                    logger.debug(f"Cache Hit: Barcode {codigo} -> SKU {sku}")
                # Búsqueda remota de barcode (Fallback)
                elif obtener_sku_por_codigo_barra:
                    try:
                        sku_found = obtener_sku_por_codigo_barra(codigo)
                        if sku_found:
                            sku = sku_found
                            logger.info(f"Fallback remoto: Barcode {codigo} -> SKU {sku}")
                    except Exception as e:
                        logger.error(f"Error buscando por código de barra remoto: {e}")

            return sku, origen_serial, nombre_serial, ubicacion_actual

        def al_terminar_busqueda(resultado):
            """Ejecutado en hilo principal tras la búsqueda. Continúa el flujo normal."""
            # Re-habilitar entry
            if not self.window.winfo_exists():
                return
            self.entry_scanner.config(state='normal')

            sku, origen_serial, nombre_serial, ubicacion_actual = resultado

            try:
                # Validación de ubicación si fue reconocido como serial
                if origen_serial and ubicacion_actual and ubicacion_actual not in ['BODEGA', 'FALTANTE']:
                    messagebox.showerror("Ubicación Inválida",
                        f"El equipo con serial {codigo} ya está asignado a: {ubicacion_actual}\n\n"
                        "No se puede realizar una salida de un equipo que no esté en BODEGA o FALTANTE.",
                        parent=self.window)
                    self.entry_scanner.focus_set()
                    return

                if sku not in self.productos_cache:
                    messagebox.showwarning("No encontrado",
                        f"Producto o Serial no encontrado: {codigo}\n"
                        "(Asegúrese de que el producto esté en catálogo o la serie en BODEGA)",
                        parent=self.window)
                    self.window.lift()
                    self.entry_scanner.update()
                    self.entry_scanner.focus_set()
                    return

                nombre = self.productos_cache[sku]['nombre']
                stock_disponible = self.productos_cache[sku].get('stock', 0)

                if stock_disponible <= 0:
                    messagebox.showerror("Sin Stock",
                        f"No hay stock disponible de {nombre} en BODEGA.\n(Stock: {stock_disponible})",
                        parent=self.window)
                    self.entry_scanner.focus()
                    return

                requires_serial = sku in PRODUCTOS_CON_CODIGO_BARRA
                seriales = []
                cant = 1

                if requires_serial:
                    if origen_serial:
                        seriales = [nombre_serial]
                        ya_en_carrito = any(
                            nombre_serial in item.get('seriales', [])
                            for item in self.items_carrito
                        )
                        if ya_en_carrito:
                            messagebox.showwarning("Duplicado",
                                f"El serial {nombre_serial} ya está en la lista.", parent=self.window)
                            self.entry_scanner.focus()
                            return
                        self.agregar_al_carrito(sku, nombre, 1, seriales)
                        self.entry_scanner.focus()
                        return
                    else:
                        cant_str = simpledialog.askstring("Cantidad",
                            f"Ingrese cantidad para {nombre}:\n(Disponible: {stock_disponible})",
                            parent=self.window, initialvalue="1")
                        if not cant_str:
                            self.entry_scanner.focus()
                            return
                        try:
                            cant = int(cant_str)
                            if cant <= 0:
                                self.entry_scanner.focus()
                                return
                            if cant > stock_disponible:
                                messagebox.showerror("Error",
                                    f"No puede sacar más de lo disponible ({stock_disponible}).",
                                    parent=self.window)
                                self.entry_scanner.focus()
                                return
                        except:
                            self.entry_scanner.focus()
                            return
                        dialog = SerialCaptureDialog(self.window, sku, nombre, cant, allow_existing=True)
                        if dialog.cancelado or len(dialog.series_capturadas) != cant:
                            self.entry_scanner.focus()
                            return
                        seriales = dialog.series_capturadas
                else:
                    cant_str = simpledialog.askstring("Cantidad",
                        f"Ingrese cantidad para {nombre}:\n(Disponible: {stock_disponible})",
                        parent=self.window, initialvalue="1")
                    if not cant_str:
                        self.entry_scanner.focus()
                        return
                    try:
                        cant = int(cant_str)
                        if cant <= 0:
                            self.entry_scanner.focus()
                            return
                        if cant > stock_disponible:
                            messagebox.showerror("Error",
                                f"No puede sacar más de lo disponible ({stock_disponible}).",
                                parent=self.window)
                            self.entry_scanner.focus()
                            return
                    except:
                        self.entry_scanner.focus()
                        return

                self.agregar_al_carrito(sku, nombre, cant, seriales)
                self.entry_scanner.focus()

            except Exception as e:
                logger.error(f"Error completando escaneo: {e}")
                self.window.bell()
                self.entry_scanner.focus()

        # Lanzar búsqueda en background, resultado se procesa en hilo UI
        def run_and_schedule():
            try:
                resultado = buscar_en_background()
                if self.window.winfo_exists():
                    self.window.after(0, lambda r=resultado: al_terminar_busqueda(r))
            except Exception as e:
                logger.error(f"Error en hilo de búsqueda: {e}")
                if self.window.winfo_exists():
                    self.window.after(0, lambda: (
                        self.entry_scanner.config(state='normal'),
                        self.window.bell(),
                        self.entry_scanner.focus()
                    ))

        threading.Thread(target=run_and_schedule, daemon=True).start()

    def agregar_manual(self):
        """Diálogo para agregar productos manualmente con búsquedas y validación"""
        # Crear diálogo de búsqueda
        dialog = tk.Toplevel(self.window)
        dialog.title("Búsqueda Manual")
        dialog.geometry("500x300")
        dialog.transient(self.window)
        dialog.grab_set()
        
        main_f = tk.Frame(dialog, bg='white', pady=20, padx=20)
        main_f.pack(fill='both', expand=True)
        
        tk.Label(main_f, text="Seleccione Producto:", bg='white').pack(anchor='w')
        
        # Lista filtrada de nombres
        self.manual_prods = sorted([f"{v['nombre']} ({k})" for k, v in self.productos_cache.items()])
        self.manual_combo = ttk.Combobox(main_f, values=self.manual_prods, width=50, font=('Segoe UI', 10))
        self.manual_combo.pack(pady=10)
        
        def confirmar_manual():
            sel = self.manual_combo.get()
            if not sel: return
            
            # Extraer SKU de "Nombre (SKU)"
            import re
            match = re.search(r'\((.*)\)$', sel)
            if not match: return
            sku = match.group(1)
            
            dialog.destroy()
            
            # Simular escaneo de ese SKU
            self.entry_scanner.delete(0, tk.END)
            self.entry_scanner.insert(0, sku)
            self.procesar_escaneo()

        tk.Button(main_f, text="✅ Seleccionar", command=confirmar_manual,
                 bg=Styles.SUCCESS_COLOR, fg='white', relief='flat', padx=20, pady=8).pack(pady=20)

    def agregar_al_carrito(self, sku, nombre, cantidad, seriales):
        """Adds an item to the cart. If the SKU already exists, merges the quantity/serials."""
        sku_clean = sku.strip().upper()
        es_paquete = sku_clean in self.paquete_base
        
        from config import PRODUCTOS_CON_CODIGO_BARRA
        requires_serial = sku_clean in PRODUCTOS_CON_CODIGO_BARRA
        
        if requires_serial:
            # Los equipos con serial NO se agrupan: se agregan uno por uno para visualización clara
            for s in seriales:
                self.items_carrito.append({
                    'sku': sku,
                    'nombre': nombre,
                    'cantidad': 1,
                    'seriales': [s],
                    'es_adicional': not es_paquete
                })
                if es_paquete:
                    self.items_completados[sku] = self.items_completados.get(sku, 0) + 1
            
            # Si se pasó cantidad > len(seriales) por error en un equipo, el remanente (sin MAC) se ignora
            # o se podría agregar sin serial, pero siguiendo la instrucción del usuario: 
            # "si no hay mac no debe mostrar nada" (para equipos).
        else:
            # --- LÓGICA DE MERGE PARA MATERIALES (Sin Serial) ---
            item_existente = None
            for item in self.items_carrito:
                if item['sku'] == sku:
                    item_existente = item
                    break
            
            if item_existente is not None:
                item_existente['cantidad'] += cantidad
            else:
                self.items_carrito.append({
                    'sku': sku,
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'seriales': [],
                    'es_adicional': not es_paquete
                })
            
            if es_paquete:
                self.items_completados[sku] = self.items_completados.get(sku, 0) + cantidad
            
        # Refresh UI inmediatamente
        self.actualizar_tabla()
        self.actualizar_panel_progreso()
        logger.info(f"Item(s) procesado(s): {sku} (Equipos individuales o Material agrupado)")

        # Pre-cargar detalles MAC de seriales nuevos en background (sin bloquear UI)
        seriales_sin_cache = [s for s in seriales if s not in self.serial_details_cache]
        if seriales_sin_cache:
            def cargar_detalles_seriales(lista_seriales):
                try:
                    from database import obtener_detalles_serial
                    for s in lista_seriales:
                        try:
                            info = obtener_detalles_serial(s)
                            if info:
                                self.serial_details_cache[s] = info
                        except Exception as e:
                            logger.warning(f"No se pudo obtener detalles de serial {s}: {e}")
                    # Refrescar tabla con datos MAC ahora disponibles
                    if self.window.winfo_exists():
                        self.window.after(0, self.actualizar_tabla)
                except Exception as e:
                    logger.error(f"Error en carga background de seriales: {e}")

            threading.Thread(
                target=cargar_detalles_seriales,
                args=(list(seriales_sin_cache),),
                daemon=True
            ).start()

    def editar_o_eliminar_item(self, event=None):
        """Shows a dialog to edit quantity or delete the selected item from the cart."""
        item_id = self.tree.selection()
        if not item_id: return
        
        vals = self.tree.item(item_id[0])['values']
        sku = str(vals[0])
        nombre = str(vals[1])

        # Find actual item in internal list
        item_data = None
        for item in self.items_carrito:
            if item['sku'] == sku:
                item_data = item
                break
        if not item_data: return

        cant_actual = item_data['cantidad']
        tiene_seriales = bool(item_data.get('seriales'))

        dialog = tk.Toplevel(self.window)
        dialog.title(f"Editar: {nombre[:40]}")
        dialog.geometry("390x280")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.configure(bg='white')

        tk.Label(dialog, text="✏️ Editar Ítem", font=('Segoe UI', 13, 'bold'), bg='white', fg='#2c3e50').pack(pady=(15, 2))
        tk.Label(dialog, text=nombre, font=('Segoe UI', 10), bg='white', fg='#555', wraplength=340).pack(pady=(0, 8))

        if tiene_seriales:
            serials_str = ", ".join(item_data['seriales'])
            tk.Label(dialog, text=f"Seriales: {serials_str}", font=('Segoe UI', 9), bg='white', fg='gray', wraplength=340).pack(pady=(0, 5))
            tk.Label(dialog, text="Para equipos: elimine el ítem y escanéelo de nuevo.", font=('Segoe UI', 8), bg='white', fg='#bbb').pack()
        else:
            qty_frame = tk.Frame(dialog, bg='white')
            qty_frame.pack(pady=5)
            tk.Label(qty_frame, text="Nueva Cantidad:", bg='white', font=('Segoe UI', 10)).pack(side='left', padx=5)
            qty_var = tk.StringVar(value=str(cant_actual))
            qty_entry = ttk.Entry(qty_frame, textvariable=qty_var, width=8, font=('Segoe UI', 11))
            qty_entry.pack(side='left', padx=5)
            qty_entry.select_range(0, tk.END)
            qty_entry.focus_set()

            def aplicar_cambio():
                try:
                    nueva_cant = int(qty_var.get())
                    if nueva_cant <= 0: raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "Ingrese una cantidad válida (> 0).", parent=dialog)
                    return
                old_cant = item_data['cantidad']
                item_data['cantidad'] = nueva_cant
                if sku in self.paquete_base:
                    self.items_completados[sku] = max(0, self.items_completados.get(sku, 0) - old_cant + nueva_cant)
                dialog.destroy()
                self.actualizar_tabla()
                self.actualizar_panel_progreso()

            btn_apply_frame = tk.Frame(dialog, bg='white')
            btn_apply_frame.pack(pady=8)
            tk.Button(btn_apply_frame, text="✅ Aplicar Cantidad", command=aplicar_cambio,
                      bg='#2ecc71', fg='white', relief='flat', padx=15, pady=6,
                      font=('Segoe UI', 10, 'bold')).pack(side='left', padx=8)
            dialog.bind('<Return>', lambda e: aplicar_cambio())

        def eliminar():
            if messagebox.askyesno("❌ Eliminar", f"¿Eliminar '{nombre[:50]}' del carrito?", parent=dialog):
                dialog.destroy()
                cant = item_data['cantidad']
                self.items_carrito.remove(item_data)
                if sku in self.paquete_base:
                    self.items_completados[sku] = max(0, self.items_completados.get(sku, 0) - cant)
                self.actualizar_tabla()
                self.actualizar_panel_progreso()

        btn_del_frame = tk.Frame(dialog, bg='white')
        btn_del_frame.pack(pady=(0, 10))
        tk.Button(btn_del_frame, text="🗑️ Eliminar Item", command=eliminar,
                  bg='#e74c3c', fg='white', relief='flat', padx=15, pady=6,
                  font=('Segoe UI', 10, 'bold')).pack(side='left', padx=8)
        tk.Button(btn_del_frame, text="Cancelar", command=dialog.destroy,
                  bg='#95a5a6', fg='white', relief='flat', padx=10, pady=6).pack(side='left')



    def actualizar_tabla(self):
        """Limpia y vuelve a llenar la tabla con los items del carrito.
        Usa el cache local de seriales para no bloquear el hilo de UI.
        Los detalles MAC se pre-cargan en background desde agregar_al_carrito.
        """
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        for item in self.items_carrito:
            sku = item['sku']
            nombre = item['nombre']
            cantidad = item['cantidad']
            seriales = item['seriales']
            es_adicional = item.get('es_adicional', False)
            
            tipo_str = "📦 Paquete" if not es_adicional else "➕ Adicional"
            
            # Usar cache local — SIN llamadas a DB en hilo UI
            display_series = []
            for s in seriales[:3]:
                info = self.serial_details_cache.get(s)
                if info and info.get('mac_number'):
                    mac = str(info['mac_number']).strip()
                    if mac and mac != str(s).strip():
                        display_series.append(f"{s} (MAC:{mac})")
                        continue
                display_series.append(str(s))
            
            series_str = ", ".join(display_series)
            if len(seriales) > 3:
                series_str += f" (+{len(seriales)-3})"
            if not seriales:
                series_str = "—"
            
            self.tree.insert('', 0, values=(sku, nombre, cantidad, series_str, tipo_str))

    def registrar_salida(self):
        if not self.items_carrito:
            messagebox.showwarning("Vacío", "No hay items escaneados.")
            return
            
        movil = self.combo_movil.get()
        # Para PRESTAMO_SANTIAGO: movil interno = SANTIAGO (destino)
        # Para DEVOLUCION_SANTIAGO: movil interno = SANTIAGO (origen), el combo muestra CHIRIQUI solo visualmente
        if self.mode == 'PRESTAMO_SANTIAGO':
            movil = "SANTIAGO"
        elif self.mode == 'DEVOLUCION_SANTIAGO':
            movil = "SANTIAGO"  # La función registrar_devolucion_santiago usa SANTIAGO como origen
        elif not movil:
            messagebox.showwarning("Destino", "Seleccione un destino válido.")
            return

        fecha = self.fecha_var.get()
        
        # Confirmar
        if self.mode == 'DEVOLUCION_SANTIAGO':
            action_name = "registrar devolución desde"
        elif self.mode == 'PRESTAMO_SANTIAGO':
            action_name = "transferir a"
        else:
            action_name = "registrar salida a"
        if not messagebox.askyesno("Confirmar", f"¿{action_name.capitalize()} {movil} ({len(self.items_carrito)} líneas)?", parent=self.window):
            self.window.lift()
            self.entry_scanner.focus_set()
            return
            
        items_to_process = list(self.items_carrito)
        
        def process_background():
            from database import registrar_movimiento_gui, actualizar_ubicacion_serial, get_db_connection, close_connection
            count = 0
            errores = []
            exitosos = []
            branch = CURRENT_CONTEXT.get('BRANCH')
            paquete_sel = self.combo_paquete.get() if hasattr(self, 'combo_paquete') else None
            
            # OPTIMIZACIÓN: Una sola conexión compartida para todos los items (reduce latencia MySQL)
            shared_conn = None
            try:
                shared_conn = get_db_connection()
            except Exception as e:
                logger.warning(f"No se pudo abrir conexión compartida: {e}. Usando conexiones individuales.")
                shared_conn = None
            
            total = len(items_to_process)
            try:
                for idx, item in enumerate(items_to_process, 1):
                    sku = item['sku']
                    nombre = item['nombre']
                    cantidad = item['cantidad']
                    seriales = [s.strip().upper() for s in item.get('seriales', [])]
                    
                    # Feedback de progreso en el botón
                    if self.window.winfo_exists():
                        self.window.after(0, lambda i=idx, t=total: 
                            self.btn_registrar.config(text=f"⏳ Procesando {i}/{t}...") 
                            if hasattr(self, 'btn_registrar') else None)
                    
                    try:
                        # Determinar tipo de movimiento
                        tipo_mov = 'SALIDA_MOVIL'
                        if self.mode == 'PRESTAMO_SANTIAGO':
                            tipo_mov = 'PRESTAMO_SANTIAGO'
                        elif self.mode == 'DEVOLUCION_SANTIAGO':
                            tipo_mov = 'RETORNO_MOVIL'
                        elif self.mode == 'TRASLADO':
                            tipo_mov = 'TRASLADO'
                        
                        # 1. Registrar usando conexión compartida para velocidad
                        ok, msg = registrar_movimiento_gui(
                            sku=sku,
                            tipo_movimiento=tipo_mov,
                            cantidad_afectada=cantidad,
                            movil_afectado=movil,
                            fecha_evento=fecha,
                            paquete_asignado=paquete_sel,
                            sucursal_context=branch,
                            existing_conn=shared_conn
                        )
                        
                        if not ok:
                            errores.append(f"{nombre}: {msg}")
                            continue
                        
                        # 2. Actualizar ubicación de seriales si aplica
                        if seriales:
                            for s in seriales:
                                s_ok, s_msg = actualizar_ubicacion_serial(s, movil, paquete=paquete_sel, existing_conn=shared_conn, sucursal_context=branch)
                                if not s_ok:
                                    logger.warning(f"No se pudo actualizar ubicación de serial {s}: {s_msg}")
                        
                        exitosos.append((sku, seriales))
                        count += 1

                    except Exception as e:
                        errores.append(f"{nombre}: {e}")
                
                # Commit final único para todos los items
                if shared_conn:
                    try:
                        shared_conn.commit()
                    except Exception as ce:
                        logger.error(f"Error en commit final: {ce}")
            finally:
                if shared_conn:
                    try:
                        close_connection(shared_conn)
                    except: pass
            
            return count, errores, exitosos
        
        def on_complete(result):
            # Rehabilitar botón
            if hasattr(self, 'btn_registrar'):
                self.btn_registrar.config(state='normal', text="💾 REGISTRAR")
                
            if not self.window.winfo_exists(): return
            
            count, errores, exitosos = result
            
            # Forzar foco y traer al frente
            self.window.attributes("-topmost", True)
            self.window.lift()
            self.window.focus_force()
            self.window.after(100, lambda: self.window.attributes("-topmost", False))
            
            if errores:
                msg = f"Se procesaron {count} items con {len(errores)} errores:\n\n" + "\n".join(errores[:5])
                if len(errores) > 5: msg += "\n..."
                messagebox.showerror("Error en Registro", msg, parent=self.window)
            else:
                mostrar_mensaje_emergente(self.window, "Éxito", f"Operación completada exitosamente.\n{count} registros procesados.", "success")

            # LIMPIEZA PARCIAL: Solo remover lo que se registró bien
            for e_sku, e_seriales in exitosos:
                e_sku_clean = str(e_sku).strip().upper()
                # Buscar en el carrito y restar/remover
                for item in list(self.items_carrito):
                    if str(item['sku']).strip().upper() == e_sku_clean:
                        if not e_seriales: # Material sin serial
                            self.items_carrito.remove(item)
                            break
                        else: # Equipo con serial
                            seriales_carrito = [s.strip().upper() for s in item['seriales']]
                            for s in e_seriales:
                                s_clean = s.strip().upper()
                                if s_clean in seriales_carrito:
                                    # Encontrar el índice original para remover
                                    orig_idx = -1
                                    for idx, orig_s in enumerate(item['seriales']):
                                        if orig_s.strip().upper() == s_clean:
                                            orig_idx = idx
                                            break
                                    if orig_idx != -1:
                                        item['seriales'].pop(orig_idx)
                                        item['cantidad'] -= 1
                            if item['cantidad'] <= 0:
                                self.items_carrito.remove(item)
                            break

            self.actualizar_tabla()
            self.actualizar_panel_progreso()
            
            # Recuperación agresiva de foco tras cerrar mensajes
            def recover_focus():
                if self.window.winfo_exists():
                    self.window.lift()
                    self.window.focus_force()
                    self.entry_scanner.focus_set()
            
            self.window.after(500, recover_focus) # Dar tiempo a que se cierren popups
                # Decisión: En éxito total, cerrar o limpiar. El usuario se quejó de que mandara atrás, 
                # así que mejor quedarse pero con foco.
        
        # Desactivar botón para evitar doble clic
        if hasattr(self, 'btn_registrar'):
            self.btn_registrar.config(state='disabled', text="⏳ Procesando...")
            
        mostrar_cargando_async(self.window, process_background, on_complete, self.window)
