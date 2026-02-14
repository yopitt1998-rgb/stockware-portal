
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import date
from config import PRODUCTOS_CON_CODIGO_BARRA
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente, mostrar_cargando_async
from utils.logger import get_logger
from .abasto import AbastoDetailWindow, SerialCaptureDialog # Importar diálogo de detalle y captura de manual

logger = get_logger(__name__)
from database import (
    buscar_producto_por_codigo_barra_maestro,
    registrar_abasto_batch,
    obtener_abastos_resumen,
    obtener_detalle_abasto,
)


class AbastoScannerWindow:
    """Ventana de Abasto con sistema de escaneo universal tipo 'carrito' y Historial"""
    
    def __init__(self, master_app):
        self.master_app = master_app
        self.master = master_app.master
        
        self.window = tk.Toplevel(self.master)
        self.window.title("📦 Gestión de Abastos (Escáner & Historial)")
        self.window.geometry("1000x800")
        try:
            self.window.state('zoomed')
        except:
            pass
        self.window.configure(bg='#f8f9fa')
        
        # Carrito de items
        self.items_carrito = []  # [{'sku': '', 'nombre': '', 'cantidad': 0, 'seriales': []}]
        
        self.create_interface()
        
    def create_interface(self):
        """Crea toda la interfaz"""
        # Header Global
        header_frame = tk.Frame(self.window, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📦 GESTIÓN DE ABASTOS", 
                font=('Segoe UI', 18, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Notebook principal
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Tab 1: Escáner (Carrito)
        self.tab_scanner = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(self.tab_scanner, text="🔫 Escáner (Carrito)")
        
        # Tab 2: Historial
        self.tab_history = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(self.tab_history, text="📜 Historial")
        
        # Inicializar Tabs
        self.setup_scanner_tab()
        self.setup_history_tab()
        
    # ==========================================
    # TAB 1: ESCÁNER / CARRITO
    # ==========================================
    
    def setup_scanner_tab(self):
        # Container principal del tab scanner
        container = tk.Frame(self.tab_scanner, bg='#f8f9fa')
        container.pack(fill='both', expand=True)
        
        # ========== BOTONES DE ACCIÓN (PARTE INFERIOR) ==========
        # Empacamos esto primero con side=BOTTOM para que se quede abajo y siempre visible
        self.crear_botones_accion(container)
        
        # ========== SISTEMA DE SCROLL PARA EL CONTENIDO MEDIO ==========
        canvas_container = tk.Frame(container, bg='#f8f9fa')
        canvas_container.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(canvas_container, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f8f9fa')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Hacer que el frame ocupe todo el ancho del canvas
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas.find_all()[0], width=event.width)
        canvas.bind('<Configure>', _on_canvas_configure)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mousewheel support (local binding to canvas)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # ========== CONTENIDO DEL ESCÁNER (DENTRO DEL SCROLL) ==========
        self.crear_barra_scanner(scrollable_frame)
        self.crear_formulario(scrollable_frame)
        self.crear_tabla_carrito(scrollable_frame)
    
    def crear_barra_scanner(self, parent):
        """Barra de escaneo siempre activa en la parte superior"""
        frame_scanner = tk.Frame(parent, bg='#fff3cd', padx=15, pady=15)
        frame_scanner.pack(fill='x', padx=20, pady=(20,10))
        
        # Título
        tk.Label(frame_scanner, text="📷 ESCÁNER ACTIVO", 
                font=('Segoe UI', 14, 'bold'), 
                bg='#fff3cd', fg='#856404').pack()
        
        # Instrucción
        tk.Label(frame_scanner, text="Escanee el código de barra del producto:", 
                font=('Segoe UI', 10), bg='#fff3cd').pack(pady=(5,5))
        
        # Campo de entrada
        self.entry_scanner = tk.Entry(frame_scanner, font=('Segoe UI', 14), 
                                      width=40, justify='center')
        self.entry_scanner.pack(pady=5)
        
        # Importante: Focus cuando se selecciona el tab
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
        
        # Evento al escanear (Enter)
        self.entry_scanner.bind('<Return>', self.procesar_escaneo)
        
        # Indicador de estado
        self.label_status = tk.Label(frame_scanner, text="Esperando escaneo...", 
                                    font=('Segoe UI', 9), bg='#fff3cd', fg='#6c757d')
        self.label_status.pack(pady=5)
    
    def on_tab_change(self, event):
        # Dar foco al scanner si se selecciona el primer tab
        if self.notebook.index(self.notebook.select()) == 0:
            self.entry_scanner.focus_set()

    def crear_formulario(self, parent):
        """Formulario con fecha y número de abasto"""
        form_frame = tk.Frame(parent, bg='#f8f9fa', pady=10)
        form_frame.pack(fill='x', padx=20)
        
        tk.Label(form_frame, text="Fecha:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').pack(side='left', padx=(0, 5))
        self.fecha_var = tk.StringVar(value=date.today().isoformat())
        tk.Entry(form_frame, textvariable=self.fecha_var, width=12, 
                font=('Segoe UI', 10)).pack(side='left', padx=5)
        
        tk.Label(form_frame, text="Número Abasto:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.numero_var = tk.StringVar()
        tk.Entry(form_frame, textvariable=self.numero_var, width=15, 
                font=('Segoe UI', 10)).pack(side='left', padx=5)
    
    def crear_tabla_carrito(self, parent):
        """Tabla que muestra los items a registrar"""
        frame_tabla = tk.LabelFrame(parent, text="ITEMS A REGISTRAR", 
                                    font=('Segoe UI', 11, 'bold'), padx=10, pady=10)
        frame_tabla.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Tabla
        columnas = ('SKU', 'Producto', 'Cantidad', 'Seriales')
        self.tabla_carrito = ttk.Treeview(frame_tabla, columns=columnas, 
                                          show='headings', height=10)
        
        self.tabla_carrito.heading('SKU', text='SKU')
        self.tabla_carrito.heading('Producto', text='Producto')
        self.tabla_carrito.heading('Cantidad', text='Cantidad')
        self.tabla_carrito.heading('Seriales', text='Seriales')
        
        self.tabla_carrito.column('SKU', width=100, anchor='center')
        self.tabla_carrito.column('Producto', width=300)
        self.tabla_carrito.column('Cantidad', width=100, anchor='center')
        self.tabla_carrito.column('Seriales', width=150, anchor='center')
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', 
                                 command=self.tabla_carrito.yview)
        self.tabla_carrito.configure(yscrollcommand=scrollbar.set)
        
        self.tabla_carrito.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Totales
        self.label_totales = tk.Label(frame_tabla, 
            text="Total Items: 0 | Total Unidades: 0", 
            font=('Segoe UI', 10, 'bold'))
        self.label_totales.pack(pady=5)
    
    def crear_botones_accion(self, parent):
        """Botones para gestionar el carrito"""
        frame_btns = tk.Frame(parent, bg='#f8f9fa', padx=20, pady=15)
        frame_btns.pack(fill='x', side='bottom')
        
        # Botones izquierda
        tk.Button(frame_btns, text="Quitar Item", command=self.quitar_item,
                 bg='#ffc107', fg='black', padx=15, pady=8,
                 font=('Segoe UI', 10)).pack(side='left', padx=5)
        
        tk.Button(frame_btns, text="Limpiar Todo", command=self.limpiar_carrito,
                 bg='#dc3545', fg='white', padx=15, pady=8,
                 font=('Segoe UI', 10)).pack(side='left', padx=5)
        
        # Botones derecha
        tk.Button(frame_btns, text="❌ Cancelar", command=self.window.destroy,
                 bg='#6c757d', fg='white', padx=20, pady=8,
                 font=('Segoe UI', 10)).pack(side='right', padx=5)
        
        tk.Button(frame_btns, text="✅ PROCEDER CON ABASTO", 
                 command=self.proceder_abasto,
                 bg='#28a745', fg='white', padx=30, pady=12,
                 font=('Segoe UI', 11, 'bold')).pack(side='right', padx=5)
    
    
    def ver_historial(self):
        """Cambia al tab de historial"""
        self.notebook.select(self.tab_history)
    
    # ========== LÓGICA DE ESCANEO ==========
    
    def procesar_escaneo(self, event):
        """Procesa el código de barra escaneado"""
        codigo = self.entry_scanner.get().strip().upper()
        self.entry_scanner.delete(0, tk.END)
        
        if not codigo:
            return
        
        self.label_status.config(text=f"🔍 Buscando: {codigo}...", fg=Styles.PRIMARY_COLOR)
        self.window.update()
        
        # buscar_producto_por_codigo_barra_maestro ya normaliza internamente
        producto = buscar_producto_por_codigo_barra_maestro(codigo)
        
        if not producto:
            self.label_status.config(text=f"❌ No encontrado: {codigo}", fg=Styles.ACCENT_COLOR)
            messagebox.showwarning("No encontrado", f"Producto no encontrado: {codigo}", parent=self.window)
            self.entry_scanner.focus_set()
            return
        
        nombre = producto['nombre']
        sku = producto['sku']
        
        self.label_status.config(text=f"✅ Encontrado: {nombre}", fg=Styles.SUCCESS_COLOR)
        
        # Verificar si requiere serial
        if producto['tiene_seriales']:
            # Pedir cantidad para series
            from tkinter import simpledialog
            cant_str = simpledialog.askstring("Cantidad", f"¿Cuántos equipos '{nombre}' va a ingresar?", 
                                            parent=self.window, initialvalue="1")
            if not cant_str: 
                self.label_status.config(text="Operación cancelada", fg='#666')
                return
            
            try:
                cant = int(cant_str)
                if cant <= 0: return
            except:
                return
            
            # Abrir captura de series
            dialog = SerialCaptureDialog(self.window, sku, nombre, cant)
            if dialog.cancelado or len(dialog.series_capturadas) != cant:
                self.label_status.config(text="Captura de series cancelada", fg='#666')
                return
            
            self.agregar_item_carrito(producto, cant, dialog.series_capturadas)
        else:
            # Producto normal (Sin serial)
            from tkinter import simpledialog
            cant_str = simpledialog.askstring("Cantidad", f"Ingrese cantidad para '{nombre}':", 
                                            parent=self.window, initialvalue="1")
            
            if not cant_str: 
                self.label_status.config(text="Operación cancelada", fg='#666')
                return 
            
            try:
                cant = int(cant_str)
                if cant <= 0: return
            except:
                return
            
            self.agregar_item_carrito(producto, cant, [])
        
        self.entry_scanner.focus_set()
        self.label_status.config(text=f"📦 {cant} x {nombre} agregado al carrito", fg=Styles.SUCCESS_COLOR)
    
    # Los popups antiguos fueron reemplazados por diálogos directos en procesar_escaneo para mayor fluidez.
    
    # ========== GESTIÓN DEL CARRITO ==========
    
    def agregar_item_carrito(self, producto, cantidad, seriales):
        """Agrega un item al carrito"""
        item = {
            'sku': producto['sku'],
            'nombre': producto['nombre'],
            'cantidad': cantidad,
            'seriales': seriales
        }
        
        self.items_carrito.append(item)
        
        # Actualizar tabla
        seriales_text = f"{len(seriales)} seriales" if seriales else "-"
        self.tabla_carrito.insert('', 'end', values=(
            producto['sku'],
            producto['nombre'],
            cantidad,
            seriales_text
        ))
        
        # Actualizar totales
        self.actualizar_totales()
    
    def quitar_item(self):
        """Quita el item seleccionado del carrito"""
        seleccion = self.tabla_carrito.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Seleccione un item para quitar")
            return
        
        # Obtener índice
        item_id = seleccion[0]
        index = self.tabla_carrito.index(item_id)
        
        # Confirmar
        item = self.items_carrito[index]
        if messagebox.askyesno("Confirmar", f"¿Quitar {item['nombre']}?"):
            # Remover de lista y tabla
            self.items_carrito.pop(index)
            self.tabla_carrito.delete(item_id)
            self.actualizar_totales()
    
    def limpiar_carrito(self):
        """Limpia todos los items del carrito"""
        if not self.items_carrito:
            return
        
        if messagebox.askyesno("Confirmar", "¿Limpiar todo el carrito?"):
            self.items_carrito = []
            for item in self.tabla_carrito.get_children():
                self.tabla_carrito.delete(item)
            self.actualizar_totales()
            self.label_status.config(text="Carrito limpiado", fg='#6c757d')
    
    def actualizar_totales(self):
        """Actualiza el label de totales"""
        total_items = len(self.items_carrito)
        total_unidades = sum(item['cantidad'] for item in self.items_carrito)
        self.label_totales.config(
            text=f"Total Items: {total_items} | Total Unidades: {total_unidades}"
        )
    
    # ========== REGISTRO EN BD ==========
    
    def proceder_abasto(self):
        """Registra todos los items del carrito"""
        if not self.items_carrito:
            messagebox.showwarning("Vacío", "No hay items para registrar")
            return
        
        # Confirmación
        total_items = len(self.items_carrito)
        total_unidades = sum(item['cantidad'] for item in self.items_carrito)
        
        confirmar = messagebox.askyesno("Confirmar Abasto",
            f"¿Registrar abasto con {total_items} productos ({total_unidades} unidades)?")
        
        if not confirmar:
            return
        
        # Registrar en BD
        fecha = self.fecha_var.get() or date.today().isoformat()
        numero = self.numero_var.get() or None
        
        # Guardar asíncrono
        def guardar_func():
            return registrar_abasto_batch(self.items_carrito, fecha, numero)
            
        def on_complete(result):
            exito, mensaje = result
            if exito:
                messagebox.showinfo("Éxito", mensaje)
                self.limpiar_carrito()
                self.label_status.config(text="✅ Abasto registrado exitosamente", fg='#28a745')
                # Recargar historial si estamos en ese tab (o simplemente se refrescará al entrar)
                self.load_history()
            else:
                messagebox.showerror("Error", mensaje)
                
        mostrar_cargando_async(self.window, guardar_func, on_complete, self.master_app)

    # ==========================================
    # TAB 2: HISTORIAL
    # ==========================================
    
    def setup_history_tab(self):
        # Container
        container = tk.Frame(self.tab_history, bg='#f8f9fa')
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Controles
        ctrl_frame = tk.Frame(container, bg='#f8f9fa', pady=10)
        ctrl_frame.pack(fill='x')
        
        tk.Button(ctrl_frame, text="🔄 Actualizar Lista", command=self.load_history,
                bg=Styles.INFO_COLOR, fg='white', relief='flat', padx=10).pack(side='left')
                
        # Treeview
        columns = ("Fecha", "Referencia", "Items", "Total Unidades", "Última Modificación")
        self.tree_history = ttk.Treeview(container, columns=columns, show='headings')
        
        for col in columns:
            self.tree_history.heading(col, text=col)
            self.tree_history.column(col, anchor='center')
            
        # Frame para tree + scroll
        tree_frame = tk.Frame(container)
        tree_frame.pack(fill='both', expand=True)
        
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=sb.set)
        
        sb.pack(side='right', fill='y')
        self.tree_history.pack(side='left', fill='both', expand=True)
        
        self.tree_history.bind("<Double-1>", self.on_history_double_click)
        
        # Cargar datos iniciales
        self.load_history()
        
    def load_history(self):
        # Usar el overlay en el tab de historia si es posible, o en la ventana principal
        target = self.window 
        mostrar_cargando_async(target, obtener_abastos_resumen, self.display_history, self.master_app)

    def display_history(self, data):
        # Limpiar
        for item in self.tree_history.get_children():
            self.tree_history.delete(item)
            
        # Llenar
        for row in data:
            self.tree_history.insert('', 'end', values=row)
            
    def on_history_double_click(self, event):
        item_id = self.tree_history.selection()
        if not item_id: return
        
        vals = self.tree_history.item(item_id[0])['values']
        fecha = vals[0]
        ref = vals[1]
        
        # Usar la ventana de detalle importada desde abasto.py
        # Le pasamos self.load_history como callback para refrescar si se edita algo
        AbastoDetailWindow(self.window, fecha, ref, self.load_history)

