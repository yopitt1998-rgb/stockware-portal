import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date
import threading

from config import PAQUETE_INSTALACION, PRODUCTOS_CON_CODIGO_BARRA
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente, mostrar_cargando_async
from utils.logger import get_logger

# Importaciones diferidas para evitar ciclos
# from database import ... (moved inside methods)
from .abasto import SerialCaptureDialog

logger = get_logger(__name__)


class MobileOutputScannerWindow:
    def __init__(self, master_app, mode='SALIDA_MOVIL'):
        self.master_app = master_app
        self.mode = mode  # 'SALIDA_MOVIL', 'TRASLADO', 'PRESTAMO_SANTIAGO', 'DEVOLUCION_SANTIAGO'
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
        
        self.create_interface()
        self.load_initial_data()
        
    def load_initial_data(self):
        def load():
            from database import obtener_nombres_moviles, obtener_todos_los_skus_para_movimiento
            
            # Cargar móviles
            moviles = obtener_nombres_moviles()
            
            # Cargar productos para validación rápida
            prods = obtener_todos_los_skus_para_movimiento()
            cache = {sku: {'nombre': nombre, 'stock': stock} for nombre, sku, stock in prods}
            
            return moviles, cache
            
        def on_loaded(result):
            moviles, cache = result
            self.combo_movil['values'] = moviles
            self.productos_cache = cache
            
            # Pre-seleccionar según modo
            if self.mode == 'PRESTAMO_SANTIAGO':
                self.combo_movil.set("SANTIAGO")
                self.combo_movil.configure(state='disabled')
            elif self.mode == 'DEVOLUCION_SANTIAGO':
                self.combo_movil.set("CHIRIQUI")  # Destino real de la devolución
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
            self.combo_paquete.set("PAQUETE A")
            self.combo_paquete.pack(side='left', padx=5)
            self.combo_paquete.bind("<<ComboboxSelected>>", self.on_package_change)

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
        
        self.tree.bind('<Double-1>', self.eliminar_item)

    def crear_botones_accion(self, parent):
        frame = tk.Frame(parent, bg=Styles.LIGHT_BG, pady=10)
        frame.pack(fill='x')
        
        tk.Button(frame, text="🔎 Búsqueda Manual", command=self.agregar_manual,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10).pack(side='left', padx=10)

        tk.Button(frame, text="❌ Cancelar", command=self.window.destroy,
                 bg='#6c757d', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10).pack(side='left')
                 
        tk.Button(frame, text=f"💾 REGISTRAR", command=self.registrar_salida,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10).pack(side='right')

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
        
        self.actualizar_panel_progreso()

    def actualizar_panel_progreso(self):
        for widget in self.frame_lista_progreso.winfo_children():
            widget.destroy()
            
        for sku, cantidad_esperada in self.paquete_base.items():
            completado = self.items_completados.get(sku, 0)
            nombre = self.productos_cache.get(sku, {}).get('nombre', sku)
            
            # Truncar nombre si es muy largo
            if len(nombre) > 25: nombre = nombre[:22] + "..."
            
            frame = tk.Frame(self.frame_lista_progreso, bg='white', pady=2)
            frame.pack(fill='x', padx=5)
            
            icon = "✅" if completado >= cantidad_esperada else "⬜"
            color = Styles.SUCCESS_COLOR if completado >= cantidad_esperada else "#666"
            
            tk.Label(frame, text=icon, bg='white').pack(side='left')
            tk.Label(frame, text=f"{nombre}", font=('Segoe UI', 9), bg='white', fg=color).pack(side='left')
            tk.Label(frame, text=f"{completado}/{cantidad_esperada}", font=('Segoe UI', 9, 'bold'), bg='white', fg=color).pack(side='right')

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
        try:
            desde_database = None
            try:
                 from database import obtener_sku_por_codigo_barra, obtener_sku_por_serial
                 desde_database = obtener_sku_por_codigo_barra
            except ImportError:
                 pass

            codigo = self.entry_scanner.get().strip().upper()
            self.entry_scanner.delete(0, tk.END)
            
            if not codigo: return
            
            # Identificar SKU y ORIGEN (Serial o Codigo)
            sku = codigo
            origen_serial = False
            nombre_serial = None
            
            # 1. Intentar buscar por SERIAL primero (Prioridad MAC)
            try:
                sku_serial, existe = obtener_sku_por_serial(codigo)
                if existe:
                    sku = sku_serial
                    origen_serial = True
                    nombre_serial = codigo
                    logger.info(f"Auto-reconocimiento: Serial {codigo} -> SKU {sku}")
            except Exception as e:
                logger.error(f"Error en auto-reconocimiento de serial: {e}")

            # 2. Si no es serial, buscar por SKU/Barcode
            if not origen_serial:
                if codigo in self.productos_cache:
                    sku = codigo
                elif desde_database:
                    sku_found = desde_database(codigo)
                    if sku_found:
                        sku = sku_found
            
            if sku not in self.productos_cache:
                messagebox.showwarning("No encontrado", f"Producto o Serial no encontrado: {codigo}\n(Asegúrese de que el producto esté en catálogo o la serie en BODEGA)", parent=self.window)
                self.entry_scanner.focus() # Recuperar foco
                return
                
            nombre = self.productos_cache[sku]['nombre']
            stock_disponible = self.productos_cache[sku].get('stock', 0)
            
            # Verificar si hay stock en BODEGA (Feedback Usuario)
            if stock_disponible <= 0:
                messagebox.showerror("Sin Stock", f"No hay stock disponible de {nombre} en BODEGA.\n(Stock: {stock_disponible})", parent=self.window)
                self.entry_scanner.focus()
                return

            # Verificar si requiere serial
            requires_serial = sku in PRODUCTOS_CON_CODIGO_BARRA
            seriales = []
            cant = 1
            
            if requires_serial:
                # SI FUE RECONOCIDO POR SERIAL (MAC), AUTO-AGREGAR
                if origen_serial:
                    seriales = [nombre_serial]
                    # Validar que no esté ya en el carrito
                    ya_en_carrito = False
                    for item in self.items_carrito:
                        if nombre_serial in item.get('seriales', []):
                             ya_en_carrito = True
                             break
                    
                    if ya_en_carrito:
                         messagebox.showwarning("Duplicado", f"El serial {nombre_serial} ya está en la lista.", parent=self.window)
                         self.entry_scanner.focus()
                         return
                    
                    # AUTO-ADD (Sin preguntar cantidad)
                    self.agregar_al_carrito(sku, nombre, 1, seriales)
                    self.entry_scanner.focus()
                    return

                else:
                    # Flujo normal (Escaneó codigo maestro de un producto con serie)
                    cant_str = simpledialog.askstring("Cantidad", f"Ingrese cantidad para {nombre}:\n(Disponible: {stock_disponible})", 
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
                            messagebox.showerror("Error", f"No puede sacar más de lo disponible ({stock_disponible}).", parent=self.window)
                            self.entry_scanner.focus()
                            return
                    except:
                        self.entry_scanner.focus()
                        return
                    
                    # Abrir captura de series
                    dialog = SerialCaptureDialog(self.window, sku, nombre, cant, allow_existing=True)
                    if dialog.cancelado or len(dialog.series_capturadas) != cant:
                        self.entry_scanner.focus()
                        return
                    seriales = dialog.series_capturadas
            else:
                # Producto normal (Sin serial)
                cant_str = simpledialog.askstring("Cantidad", f"Ingrese cantidad para {nombre}:\n(Disponible: {stock_disponible})", 
                                                parent=self.window, initialvalue="1")
                
                if not cant_str: 
                    self.entry_scanner.focus()
                    return # Cancelado
                
                try:
                    cant = int(cant_str)
                    if cant <= 0: 
                        self.entry_scanner.focus()
                        return
                    if cant > stock_disponible:
                        messagebox.showerror("Error", f"No puede sacar más de lo disponible ({stock_disponible}).", parent=self.window)
                        self.entry_scanner.focus()
                        return
                except:
                    self.entry_scanner.focus()
                    return
            
            self.agregar_al_carrito(sku, nombre, cant, seriales)
            self.entry_scanner.focus()
            
        except Exception as e:
            logger.error(f"Error procesando escaneo: {e}")
            # No mostrar popup intrusivo por cada error de escaneo, solo log y beep
            self.window.bell() 
            self.entry_scanner.focus()

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
        # Verificar si es paquete o adicional (Robust matching)
        sku_clean = sku.strip().upper()
        es_paquete = sku_clean in self.paquete_base
        
        # Logging para depuración
        if not es_paquete:
            logger.info(f"SKU {sku_clean} no encontrado en paquete base: {list(self.paquete_base.keys())[:5]}...")
        
        # Agregar a lista
        self.items_carrito.append({
            'sku': sku,
            'nombre': nombre,
            'cantidad': cantidad,
            'seriales': seriales,
            'es_adicional': not es_paquete
        })
        
        # Actualizar contadores
        if es_paquete:
            self.items_completados[sku] += cantidad
            
        # Actualizar UI
        tipo_str = "📦 Paquete" if es_paquete else "➕ Adicional"
        series_str = ", ".join(seriales) if seriales else "—"
        
        self.tree.insert('', 0, values=(sku, nombre, cantidad, series_str, tipo_str))
        self.actualizar_panel_progreso()
        
        logger.info(f"Item agregado: {sku} x{cantidad}")

    def eliminar_item(self, event):
        item_id = self.tree.selection()
        if not item_id: return
        
        vals = self.tree.item(item_id[0])['values']
        sku = vals[0]
        cant = int(vals[2])
        
        if messagebox.askyesno("Eliminar", f"¿Quitar {sku} del carrito?", parent=self.window):
            self.tree.delete(item_id)
            
            # Buscar y remover de lista interna
            for i, item in enumerate(self.items_carrito):
                if item['sku'] == sku and item['cantidad'] == cant: 
                    self.items_carrito.pop(i)
                    break
            
            # Actualizar contadores
            if sku in self.paquete_base:
                self.items_completados[sku] -= cant
                if self.items_completados[sku] < 0: self.items_completados[sku] = 0
                
            self.actualizar_panel_progreso()

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
        if not messagebox.askyesno("Confirmar", f"¿{action_name.capitalize()} {movil} ({len(self.items_carrito)} líneas)?"):
            return
            
        items_to_process = self.items_carrito
        
        def process_background():
            from database import registrar_movimiento_gui, actualizar_ubicacion_serial, registrar_devolucion_santiago

            errores = []
            count = 0
            
            for item in items_to_process:
                sku = item['sku']
                cantidad = item['cantidad']
                seriales = item['seriales']
                
                # A. TRANSFERENCIA A SANTIAGO — igual que SALIDA_MOVIL con movil='SANTIAGO'
                if self.mode == 'PRESTAMO_SANTIAGO':
                    if seriales:
                        for serial in seriales:
                            exito, mensaje = registrar_movimiento_gui(
                                sku, 'SALIDA_MOVIL', 1, 'SANTIAGO',
                                fecha_evento=fecha,
                                paquete_asignado=None,
                                observaciones=f"Transferencia a Santiago"
                            )
                            if exito:
                                actualizar_ubicacion_serial(serial, 'SANTIAGO')
                                count += 1
                            else:
                                errores.append(f"{sku} ({serial}): {mensaje}")
                    else:
                        exito, mensaje = registrar_movimiento_gui(
                            sku, 'SALIDA_MOVIL', cantidad, 'SANTIAGO',
                            fecha_evento=fecha,
                            paquete_asignado=None,
                            observaciones=f"Transferencia a Santiago"
                        )
                        if exito:
                            count += 1
                        else:
                            errores.append(f"{sku}: {mensaje}")

                # B. DEVOLUCIÓN DE SANTIAGO — entrada a Bodega Local con seriales nuevos
                elif self.mode == 'DEVOLUCION_SANTIAGO':
                    exito, mensaje = registrar_devolucion_santiago(
                        sku, cantidad, seriales, fecha,
                        observaciones="Devolución desde Santiago"
                    )
                    if exito:
                        count += 1
                    else:
                        errores.append(f"{sku}: {mensaje}")

                # B. TRASLADO O SALIDA MOVIL
                else: 
                    tipo_mov = 'TRASLADO' if self.mode == 'TRASLADO' else 'SALIDA_MOVIL'
                    paquete_record = self.combo_paquete.get() if hasattr(self, 'combo_paquete') else None
                    
                    if seriales:
                        # Equipos con serial
                        for serial in seriales:
                            exito, mensaje = registrar_movimiento_gui(
                                sku, tipo_mov, 1, movil, 
                                fecha_evento=fecha,
                                paquete_asignado=paquete_record
                            )
                            
                            if exito:
                                # Actualizar ubicación del serial
                                nueva_ubicacion = movil if self.mode == 'SALIDA_MOVIL' else f"TRASLADO_{movil}"
                                actualizar_ubicacion_serial(serial, nueva_ubicacion)
                                count += 1
                            else:
                                errores.append(f"{sku} ({serial}): {mensaje}")

                    else:
                        # Materiales sin serial
                        exito, mensaje = registrar_movimiento_gui(
                            sku, tipo_mov, cantidad, movil,
                            fecha_evento=fecha,
                            paquete_asignado=paquete_record
                        )
                        
                        if exito:
                            count += 1
                        else:
                            errores.append(f"{sku}: {mensaje}")
                            
            return count, errores
            
        def on_complete(result):
            count, errores = result
            if errores:
                msg = f"Se procesaron {count} items con {len(errores)} errores:\n\n" + "\n".join(errores[:5])
                if len(errores) > 5: msg += "\n..."
                messagebox.showwarning("Resultado parcial", msg, parent=self.window)
            else:
                messagebox.showinfo("Éxito", f"Operación completada exitosamente.\n{count} registros procesados.", parent=self.window)
                # NO CERRAR VENTANA - LIMPIAR Y MANTENER EL FLUJO
                self.items_carrito = []
                for item in self.tree.get_children():
                    self.tree.delete(item)
                
                # Reiniciar contadores visuales
                self.items_completados = {sku: 0 for sku in self.paquete_base}
                self.actualizar_panel_progreso()
                
                self.entry_scanner.focus()
                
        mostrar_cargando_async(self.window, process_background, on_complete, self.window)
