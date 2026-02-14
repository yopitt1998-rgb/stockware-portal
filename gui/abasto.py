import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import date
from config import PRODUCTOS_CON_CODIGO_BARRA
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente
from utils.logger import get_logger

logger = get_logger(__name__)
from database import (
    obtener_todos_los_skus_para_movimiento,
    registrar_movimiento_gui,
    obtener_abastos_resumen,
    obtener_detalle_abasto,
    actualizar_movimiento_abasto,
    verificar_serie_existe,
    registrar_series_bulk,
    obtener_sku_por_codigo_barra # NUEVO
)

class SerialCaptureDialog:
    def __init__(self, parent, sku, nombre, cantidad_total, allow_existing=False):
        self.top = tk.Toplevel(parent)
        self.top.title(f"Escaneo de Series: {sku}")
        self.top.geometry("600x500")
        self.top.grab_set()
        
        self.sku = sku
        self.cantidad_total = cantidad_total
        self.series_capturadas = []
        self.cancelado = False
        self.allow_existing = allow_existing
        
        # UI
        header = tk.Frame(self.top, bg=Styles.PRIMARY_COLOR, pady=10)
        header.pack(fill='x')
        tk.Label(header, text=f"Producto: {nombre}", font=('Segoe UI', 12, 'bold'), 
                bg=Styles.PRIMARY_COLOR, fg='white').pack()
        tk.Label(header, text=f"SKU: {sku}", bg=Styles.PRIMARY_COLOR, fg='white').pack()
        
        self.lbl_progress = tk.Label(self.top, text=f"Series Capturadas: 0 / {cantidad_total}", 
                                   font=('Segoe UI', 14, 'bold'), fg=Styles.ACCENT_COLOR)
        self.lbl_progress.pack(pady=15)
        
        input_frame = tk.Frame(self.top)
        input_frame.pack(pady=10)
        tk.Label(input_frame, text="🔍 ESCANEAR SERIE:", font=('Segoe UI', 10, 'bold')).pack(side='left', padx=5)
        self.entry_serie = tk.Entry(input_frame, width=30, font=('Segoe UI', 11))
        self.entry_serie.pack(side='left', padx=5)
        self.entry_serie.bind('<Return>', self.procesar_serie)
        self.entry_serie.focus_set()
        
        # Frame con listbox y scrollbar
        list_frame = tk.Frame(self.top)
        list_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.listbox = tk.Listbox(list_frame, width=50, height=10, font=('Courier', 10),
                                 yscrollcommand=scrollbar.set)
        self.listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Botones de acción para series
        action_frame = tk.Frame(self.top)
        action_frame.pack(pady=5)
        
        tk.Button(action_frame, text="🗑️ Eliminar Serie Seleccionada", 
                 command=self.eliminar_serie_seleccionada,
                 bg='#dc3545', fg='white', font=('Segoe UI', 9),
                 relief='flat', padx=10, pady=5).pack(side='left', padx=5)
        
        tk.Label(self.top, text="Doble clic en una serie para eliminarla", 
                fg='gray', font=('Segoe UI', 8)).pack()
        
        self.listbox.bind('<Double-1>', lambda e: self.eliminar_serie_seleccionada())
        
        btn_frame = tk.Frame(self.top)
        btn_frame.pack(fill='x', pady=15, padx=20)
        
        tk.Button(btn_frame, text="❌ Cancelar", command=self.cancelar,
                 bg='#6c757d', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=15, pady=8).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="✅ Confirmar y Guardar", command=self.confirmar,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=15, pady=8).pack(side='right', padx=5)
        
        # Keep window on top
        self.top.transient(parent)
        self.top.wait_window()
        
    def procesar_serie(self, event):
        serial = self.entry_serie.get().strip().upper()
        if not serial: return
        
        # 1. Check duplicates in current session
        if serial in self.series_capturadas:
             messagebox.showwarning("Duplicado", f"La serie '{serial}' ya fue escaneada en esta sesión.", parent=self.top)
             self.entry_serie.delete(0, tk.END)
             return

        # 2. Check DB
        if self.allow_existing:
            # Para Salida: Debe existir, estar DISPONIBLE y en BODEGA
            exists, msg = verificar_serie_existe(serial, ubicacion_requerida='BODEGA', estado_requerido='DISPONIBLE')
            if not exists or "no está" in msg or "no encontrada" in msg:
                messagebox.showerror("Error de Serie", msg, parent=self.top)
                self.entry_serie.delete(0, tk.END)
                return
        else:
            # Para Abasto: NO debe existir
            exists, msg = verificar_serie_existe(serial)
            if exists:
                messagebox.showerror("Error", msg, parent=self.top)
                self.entry_serie.delete(0, tk.END)
                return
            
        # Add OK
        self.series_capturadas.append(serial)
        self.listbox.insert(tk.END, f"{len(self.series_capturadas)}. {serial}")
        self.update_progress()
        self.entry_serie.delete(0, tk.END)
        
        # Ya NO cerramos automáticamente, el usuario debe confirmar
        
    def update_progress(self):
        self.lbl_progress.config(text=f"Series Capturadas: {len(self.series_capturadas)} / {self.cantidad_total}")
    
    def eliminar_serie_seleccionada(self):
        """Elimina la serie seleccionada de la lista"""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Por favor, seleccione una serie para eliminar.", parent=self.top)
            return
        
        index = selection[0]
        serie_eliminada = self.series_capturadas.pop(index)
        
        # Reconstruir la lista visualmente
        self.listbox.delete(0, tk.END)
        for i, serie in enumerate(self.series_capturadas, 1):
            self.listbox.insert(tk.END, f"{i}. {serie}")
        
        self.update_progress()
        logger.info(f"🗑️ Serie eliminada: {serie_eliminada}")
    
    def confirmar(self):
        """Confirma que las series son correctas y cierra el diálogo"""
        # Verificar que se hayan capturado todas las series requeridas
        if len(self.series_capturadas) != self.cantidad_total:
            result = messagebox.askyesno("Confirmar", 
                f"Se requieren {self.cantidad_total} series pero solo se capturaron {len(self.series_capturadas)}.\n\n"
                "¿Desea continuar de todas formas?", parent=self.top)
            if not result:
                return
        
        # Todo OK, cerrar el diálogo
        self.top.destroy()
        
    def cancelar(self):
        if messagebox.askyesno("Cancelar", "¿Está seguro? Esto cancelará el escaneo de series para este producto.", parent=self.top):
            self.cancelado = True
            self.series_capturadas = []  # Limpiar series si cancela
            self.top.destroy()


def mostrar_cargando_async(parent, funcion_carga, callback_exito, master_error=None):
    # Determine master for error handling if not provided
    if master_error is None:
        try:
            master_error = parent.winfo_toplevel()
        except:
            master_error = parent

    # Crear un overlay semi-parente
    overlay = tk.Frame(parent, bg='white')
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    
    lbl = tk.Label(overlay, text="Cargando datos...", font=('Segoe UI', 12), bg='white')
    lbl.pack(expand=True)
    
    def run_async():
        try:
            datos = funcion_carga()
            # Programar actualización en hilo principal
            parent.after(0, lambda: finalizar_carga(overlay, callback_exito, datos))
        except Exception as e:
            parent.after(0, lambda: manejar_error_carga(overlay, str(e), master_error))
            
    # Iniciar hilo
    threading.Thread(target=run_async, daemon=True).start()

def finalizar_carga(overlay, callback, datos):
    try:
        overlay.destroy()
    except:
        pass
    callback(datos)

def manejar_error_carga(overlay, error_msg, master):
    try:
        overlay.destroy()
    except:
        pass
    mostrar_mensaje_emergente(master, "Error", f"Error al cargar datos: {error_msg}", "error")

class AbastoWindow:
    def __init__(self, master_app, mode='registrar'):
        self.master_app = master_app
        self.master = master_app.master
        
        self.mode = mode # 'registrar' or 'gestionar'
        
        self.window = tk.Toplevel(self.master)
        self.window.title("📦 Gestión de Abastos")
        self.window.geometry("1000x800")
        try:
             self.window.state('zoomed')
        except:
             pass
        self.window.configure(bg='#f8f9fa')
        
        self.create_widgets()
        
        # Select initial tab based on mode
        if self.mode == 'gestionar':
            self.notebook.select(self.tab_history)
        
    
    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.window, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📦 GESTIÓN DE ABASTOS E INVENTARIO INICIAL", 
                font=('Segoe UI', 18, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Notebook
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Tab 1: Registrar
        self.tab_register = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(self.tab_register, text="➕ Registrar Nuevo Abasto")
        self.setup_register_tab()
        
        # Tab 2: Historial
        self.tab_history = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(self.tab_history, text="📜 Historial de Abastos")
        self.setup_history_tab()
        
    def setup_register_tab(self):
        # --- Formulario ---
        form_frame = tk.Frame(self.tab_register, bg='#f8f9fa', pady=10)
        form_frame.pack(fill='x')
        
        # Fecha
        tk.Label(form_frame, text="Fecha (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.fecha_entry = tk.Entry(form_frame, width=15, font=('Segoe UI', 10))
        self.fecha_entry.insert(0, date.today().isoformat())
        self.fecha_entry.pack(side='left', padx=5)
        
        # Referencia
        tk.Label(form_frame, text="Referencia / ID Abasto:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.ref_entry = tk.Entry(form_frame, width=20, font=('Segoe UI', 10))
        self.ref_entry.pack(side='left', padx=5)
        
        # Observaciones
        tk.Label(form_frame, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.obs_entry = tk.Entry(form_frame, width=30, font=('Segoe UI', 10))
        self.obs_entry.pack(side='left', padx=5)
        
        # Botón Guardar
        btn_save = tk.Button(form_frame, text="💾 Guardar Abasto", command=self.guardar_abasto,
                           bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'), relief='flat', padx=15, pady=5)
        btn_save.pack(side='right', padx=20)
        
        # --- SECCIÓN DE ESCÁNER (NUEVO) ---
        scan_frame = tk.Frame(self.tab_register, bg='#E8EAF6', padx=10, pady=5, relief='groove', bd=1)
        scan_frame.pack(fill='x', padx=20, pady=(10, 0))
        
        tk.Label(scan_frame, text="🔫 Escáner / Código de Barra:", font=('Segoe UI', 10, 'bold'), bg='#E8EAF6').pack(side='left')
        self.scan_entry = tk.Entry(scan_frame, font=('Segoe UI', 11))
        self.scan_entry.pack(side='left', fill='x', expand=True, padx=10)
        self.scan_entry.focus_set()
        
        
        # --- Lista de Productos ---
        list_frame = tk.Frame(self.tab_register, bg='#f8f9fa')
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Canvas & Scrollbar
        canvas = tk.Canvas(list_frame, bg='white')
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='white')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass
        
        # Bind only when mouse enters the widget to prevent global scrolling issues
        canvas.bind('<Enter>', lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Iniciar carga asíncrona
        mostrar_cargando_async(self.scrollable_frame, obtener_todos_los_skus_para_movimiento, self.populate_products_list, self.window)
        
    
    def populate_products_list(self, productos):
        # Limpiar
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        # DEBUG: Confirmar carga de productos
        logger.debug(f"Cargando {len(productos)} productos en la lista")
        if len(productos) > 0:
            logger.debug(f"Primeros 5 SKUs: {[p[1] for p in productos[:5]]}")
        
        # Headers
        headers = ["Producto", "SKU", "Stock Actual", "Cantidad a Ingresar", "Acción"]
        for i, h in enumerate(headers):
            tk.Label(self.scrollable_frame, text=h, font=('Segoe UI', 10, 'bold'), bg='#e9ecef', padx=10, pady=5).grid(row=0, column=i, sticky='ew')
            
        # Data
        self.entry_vars = {}
        self.series_capturadas = {}  # Almacenar series capturadas: {sku: [series]}
        self.scan_buttons = {}  # Almacenar botones de escaneo para cambiar color
        
        # Lógica de Escaneo Global (Adaptada de MobileOutputScanner)
        def procesar_scan(event=None):
            # Importación local para evitar ciclos
            try:
                from database import obtener_sku_por_codigo_barra
            except ImportError:
                obtener_sku_por_codigo_barra = lambda x: None

            raw_code = self.scan_entry.get().strip().upper()
            if not raw_code: return
            
            # Identificar SKU (obtener_sku_por_codigo_barra ya normaliza comillas)
            sku_encontrado = None
            
            if raw_code in self.entry_vars:
                sku_encontrado = raw_code
            else:
                found_db = obtener_sku_por_codigo_barra(raw_code)
                if found_db:
                    found_str = str(found_db).strip().upper()
                    if found_str in self.entry_vars:
                        sku_encontrado = found_str
            
            if not sku_encontrado:
                logger.warning(f"Código no identificado: {raw_code}")
                # messagebox.showwarning("Código No Encontrado", f"No se pudo identificar: {raw_code}", parent=self.window)
                self.scan_entry.delete(0, tk.END)
                return
            if sku_encontrado:
                # Encontrado!
                nombre_prod = "Producto"
                # Buscar nombre (visual)
                for w in self.scrollable_frame.winfo_children():
                    if isinstance(w, tk.Label) and w.cget("text") == sku_encontrado: 
                        grid_info = w.grid_info()
                        row = grid_info['row']
                        col = grid_info['column']
                        if col == 1: # Es la columna SKU
                             # Buscar nombre en col 0
                             for w2 in self.scrollable_frame.winfo_children():
                                 if isinstance(w2, tk.Label) and w2.grid_info()['row'] == row and w2.grid_info()['column'] == 0:
                                     nombre_prod = w2.cget("text")
                                     break
                        break
                        
                required_serials = sku_encontrado in PRODUCTOS_CON_CODIGO_BARRA
                msg_qty = f"Producto: {nombre_prod}\nSKU: {sku_encontrado}\n\nIngrese cantidad a ingresar:"
                if required_serials:
                    msg_qty += "\n(Luego se pedirá escanear las series)"

                from tkinter import simpledialog
                # Usar parent=self.window para que sea modal sobre la ventana de abasto
                qty = simpledialog.askinteger("Input Escáner", msg_qty, parent=self.window, minvalue=1)
                
                if qty:
                    self.entry_vars[sku_encontrado].delete(0, tk.END)
                    self.entry_vars[sku_encontrado].insert(0, str(qty))
                    
                    # Feedback visual
                    self.entry_vars[sku_encontrado].config(bg='#e8f5e9')
                    self.scan_entry.delete(0, tk.END)

                    # Si tiene botón de series, activarlo automáticamente para capturar
                    if sku_encontrado in self.scan_buttons:
                        self.window.update_idletasks()
                        self.scan_buttons[sku_encontrado].invoke() 
            else:
                 messagebox.showwarning("No encontrado", f"Producto no encontrado: {codigo_norm}\n(Original: {raw_code})", parent=self.window)
                 self.scan_entry.select_range(0, tk.END)

        self.scan_entry.bind('<Return>', procesar_scan)
        
        def crear_boton_escanear(sku_param, nombre_param):
            """Crea un botón para escanear series del producto"""
            def on_click_escanear():
                # Obtener cantidad del campo
                if sku_param not in self.entry_vars:
                    return
                
                cantidad_str = self.entry_vars[sku_param].get().strip()
                if not cantidad_str:
                    messagebox.showwarning("Cantidad Requerida", 
                        f"Por favor, ingrese primero la cantidad de {nombre_param} a ingresar.",
                        parent=self.window)
                    return
                
                try:
                    cantidad = int(cantidad_str)
                    if cantidad <= 0:
                        messagebox.showwarning("Cantidad Inválida", 
                            "La cantidad debe ser mayor a 0.",
                            parent=self.window)
                        return
                except ValueError:
                    messagebox.showwarning("Cantidad Inválida", 
                        "Por favor, ingrese un número válido.",
                        parent=self.window)
                    return
                
                # Abrir diálogo de captura de series
                logger.info(f"🔍 Iniciando captura de series: {sku_param}, Cantidad: {cantidad}")
                dialog = SerialCaptureDialog(self.window, sku_param, nombre_param, cantidad)
                
                if dialog.cancelado or len(dialog.series_capturadas) != cantidad:
                    # Si cancela, no hacer nada (mantener series anteriores si las había)
                    if sku_param in self.series_capturadas:
                        messagebox.showinfo("Mantenido", 
                            f"Se mantienen las series previamente capturadas para {sku_param}.",
                            parent=self.window)
                else:
                    # Guardar las series capturadas
                    self.series_capturadas[sku_param] = dialog.series_capturadas
                    logger.info(f"✅ {len(dialog.series_capturadas)} series capturadas para {sku_param}")
                    
                    # Cambiar color del botón para indicar éxito
                    if sku_param in self.scan_buttons:
                        self.scan_buttons[sku_param].config(bg='#28a745', fg='white', text='✅ Escaneado')
            
            return on_click_escanear
        
        for idx, (nombre, sku, stock) in enumerate(productos, start=1):
            sku_str = str(sku).strip().upper() # FORCE STRING AND UPPERCASE
            bg_color = 'white' if idx % 2 == 0 else '#f1f3f5'
            
            tk.Label(self.scrollable_frame, text=nombre, bg=bg_color, anchor='w', padx=10, pady=5).grid(row=idx, column=0, sticky='ew')
            tk.Label(self.scrollable_frame, text=sku, bg=bg_color, anchor='c', padx=10, pady=5).grid(row=idx, column=1, sticky='ew')
            tk.Label(self.scrollable_frame, text=str(stock), bg=bg_color, anchor='c', padx=10, pady=5).grid(row=idx, column=2, sticky='ew')
            
            entry = tk.Entry(self.scrollable_frame, width=10, justify='center')
            entry.grid(row=idx, column=3, padx=10, pady=2)
            self.entry_vars[sku_str] = entry
            
            # Columna de acción vacía (sin botón)
            tk.Label(self.scrollable_frame, text='', bg=bg_color).grid(row=idx, column=4)
            
            # Crear botón de escanear series si el producto lo requiere
            if sku in PRODUCTOS_CON_CODIGO_BARRA:
                btn_scan = tk.Button(self.scrollable_frame, text="🔍 Escanear Series", 
                                   command=crear_boton_escanear(sku_str, nombre),
                                   bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 8),
                                   relief='flat', padx=5, pady=2)
                btn_scan.grid(row=idx, column=4, padx=5, pady=2)
                self.scan_buttons[sku_str] = btn_scan
        
        logger.debug(f"✅ Diccionario entry_vars creado con {len(self.entry_vars)} SKUs")
        logger.debug(f"✅ {len(self.scan_buttons)} botones de escaneo creados")
        
    def guardar_abasto(self):
        fecha = self.fecha_entry.get().strip()
        ref = self.ref_entry.get().strip()
        obs = self.obs_entry.get().strip()
        
        if not fecha:
            mostrar_mensaje_emergente(self.window, "Error", "La fecha es obligatoria", "error")
            return
        if not ref:
            mostrar_mensaje_emergente(self.window, "Error", "La referencia es obligatoria (ej: ABS-001)", "error")
            return
            
        items_to_save = []
        for sku, entry in self.entry_vars.items():
            val = entry.get().strip()
            if val:
                try:
                    qty = int(val)
                    if qty > 0:
                        items_to_save.append((sku, qty))
                except ValueError:
                    continue
                    
        if not items_to_save:
            mostrar_mensaje_emergente(self.window, "Aviso", "No ha ingresado cantidades para ningún producto", "warning")
            return
            
        confirm = messagebox.askyesno("Confirmar Abasto", 
                                    f"Se registrará el abasto '{ref}' con {len(items_to_save)} items.\n\n¿Desea continuar?")
        if not confirm:
            return
            
        success_count = 0
        errors = []
        series_globales = [] # (sku, serial, ubicacion)
        
        # 1. Fase de Validación de Series
        # Verificar que todos los productos con código de barras tengan sus series capturadas
        for sku, qty in items_to_save:
            if sku in PRODUCTOS_CON_CODIGO_BARRA:
                # Verificar si ya se capturaron las series
                if sku not in self.series_capturadas or len(self.series_capturadas[sku]) != qty:
                    mostrar_mensaje_emergente(self.window, "Error", 
                        f"El producto {sku} requiere escaneo de series.\n\n"
                        f"Por favor, ingrese la cantidad y presione Enter para escanear las series.", 
                        "error")
                    return
                
                # Agregar series a la lista global
                for s in self.series_capturadas[sku]:
                    series_globales.append({'sku': sku, 'serial': s, 'ubicacion': 'BODEGA'})

        # 2. Fase de Guardado
        for sku, qty in items_to_save:
            ok, msg = registrar_movimiento_gui(
                sku, 'ABASTO', qty, None, fecha, 
                documento_referencia=ref, observaciones=obs
            )
            if ok:
                success_count += 1
            else:
                errors.append(f"{sku}: {msg}")
        
        # 3. Guardar Series
        if series_globales and not errors:
            ok_series, msg_series = registrar_series_bulk(series_globales, fecha_ingreso=fecha)
            if not ok_series:
                errors.append(f"Error registrando series: {msg_series}")

        if errors:
            msg_res = f"Se registraron {success_count} items.\nErrores:\n" + "\n".join(errors)
            mostrar_mensaje_emergente(self.window, "Resultado Parcial", msg_res, "warning")
        else:
            mostrar_mensaje_emergente(self.window, "Éxito", "Abasto registrado correctamente.", "success")
            # Limpiar entradas
            self.ref_entry.delete(0, tk.END)
            self.obs_entry.delete(0, tk.END)
            for entry in self.entry_vars.values():
                entry.delete(0, tk.END)
            
            # Limpiar series capturadas
            self.series_capturadas = {}
            
            # Resetear botones de escaneo
            for sku, btn in self.scan_buttons.items():
                btn.config(bg=Styles.INFO_COLOR, fg='white', text='🔍 Escanear Series')
                
            # Actualizar historial
            self.load_history()
            
            # Recargar stocks en lista (visual feedback)
            mostrar_cargando_async(self.scrollable_frame, obtener_todos_los_skus_para_movimiento, self.populate_products_list, self.window)
            
    def setup_history_tab(self):
        # Controls
        ctrl_frame = tk.Frame(self.tab_history, bg='#f8f9fa', pady=10)
        ctrl_frame.pack(fill='x')
        
        tk.Button(ctrl_frame, text="🔄 Actualizar Lista", command=self.load_history,
                bg=Styles.INFO_COLOR, fg='white', relief='flat', padx=10).pack(side='left', padx=20)
                
        # Treeview
        columns = ("Fecha", "Referencia", "Items", "Total Unidades", "Última Modificación")
        self.tree_history = ttk.Treeview(self.tab_history, columns=columns, show='headings')
        
        for col in columns:
            self.tree_history.heading(col, text=col)
            self.tree_history.column(col, anchor='center')
            
        self.tree_history.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbar
        sb = ttk.Scrollbar(self.tab_history, orient="vertical", command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        
        self.tree_history.bind("<Double-1>", self.on_history_double_click)
        
        self.load_history()
        
    def load_history(self):
        mostrar_cargando_async(self.tree_history, obtener_abastos_resumen, self.display_history, self.window)

    def display_history(self, data):
        for item in self.tree_history.get_children():
            self.tree_history.delete(item)
            
        # data is passed from async load
        for row in data:
            self.tree_history.insert('', 'end', values=row)
            
    def on_history_double_click(self, event):
        item_id = self.tree_history.selection()
        if not item_id: return
        
        vals = self.tree_history.item(item_id[0])['values']
        fecha = vals[0]
        ref = vals[1]
        
        AbastoDetailWindow(self.window, fecha, ref, self.load_history)

class AbastoDetailWindow:
    def __init__(self, parent, fecha, referencia, callback_refresh):
        self.top = tk.Toplevel(parent)
        self.top.title(f"Detalle Abasto: {referencia}")
        
        # Maximizar ventana
        self.top.state('zoomed')  # Windows - pantalla completa
        self.top.grab_set()
        
        self.fecha = fecha
        self.referencia = referencia
        self.callback_refresh = callback_refresh
        
        # Diccionario para almacenar series por SKU
        self.series_por_sku = {}
        
        self.create_ui()
        self.iniciar_carga_detalles()
        
    def create_ui(self):
        tk.Label(self.top, text=f"Detalle de Abasto: {self.referencia}", font=('Segoe UI', 14, 'bold')).pack(pady=10)
        tk.Label(self.top, text=f"Fecha: {self.fecha}").pack()
        
        # Treeview for items
        cols = ("ID", "Producto", "SKU", "Cantidad", "Ref", "Series")
        self.tree = ttk.Treeview(self.top, columns=cols, show='headings', height=15)
        self.tree.heading("ID", text="ID"); self.tree.column("ID", width=50)
        self.tree.heading("Producto", text="Producto"); self.tree.column("Producto", width=180)
        self.tree.heading("SKU", text="SKU"); self.tree.column("SKU", width=100)
        self.tree.heading("Cantidad", text="Cantidad"); self.tree.column("Cantidad", width=80)
        self.tree.heading("Ref", text="Ref"); self.tree.column("Ref", width=100)
        self.tree.heading("Series", text="Códigos de Serie"); self.tree.column("Series", width=350)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True, padx=(20, 0), pady=10)
        scrollbar.pack(side='right', fill='y', padx=(0, 20), pady=10)
        
        
        self.tree.bind("<Double-1>", self.edit_item)
        
        info_label = tk.Label(self.top, 
            text="💡 Doble clic: editar cantidad/ref | Clic en 'Códigos': ver series", 
            fg='gray', font=('Segoe UI', 9))
        info_label.pack(pady=5)
        
    def iniciar_carga_detalles(self):
        # Wrapper to pass arguments
        def loading_func():
            return obtener_detalle_abasto(self.fecha, self.referencia)
            
        mostrar_cargando_async(self.tree, loading_func, self.display_details, self.top)
        
    def display_details(self, detalles):
        for i in self.tree.get_children(): self.tree.delete(i)
        
        if not detalles:
             return
        
        # Obtener series de la base de datos para productos con código de barras
        from database import get_db_connection, run_query
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Calcular ventana de búsqueda (mismo día +/- 2 días por seguridad)
        try:
            from datetime import datetime, timedelta
            fecha_dt = datetime.strptime(self.fecha, '%Y-%m-%d')
            fecha_inicio = (fecha_dt - timedelta(days=2)).strftime('%Y-%m-%d')
            fecha_fin = (fecha_dt + timedelta(days=2)).strftime('%Y-%m-%d')
        except:
            fecha_inicio = self.fecha
            fecha_fin = self.fecha

        # Obtener todas las series para esta fecha y referencia
        sql_series = """
            SELECT 
                sr.sku,
                GROUP_CONCAT(sr.serial_number ORDER BY sr.serial_number SEPARATOR '|') as series
            FROM series_registradas sr
            WHERE sr.sku IN (
                SELECT sku_producto 
                FROM movimientos 
                WHERE tipo_movimiento = 'ABASTO' 
                AND fecha_evento = ? 
                AND COALESCE(documento_referencia, 'Sin Referencia') = ?
            )
            AND DATE(sr.fecha_ingreso) BETWEEN ? AND ?
            GROUP BY sr.sku
        """
        
        try:
            run_query(cursor, sql_series, (self.fecha, self.referencia, fecha_inicio, fecha_fin))
            # Guardar series en el diccionario (separadas por |)
            for row in cursor.fetchall():
                self.series_por_sku[row[0]] = row[1].split('|') if row[1] else []
        except Exception as e:
            logger.error(f"Error obteniendo series: {e}")
            self.series_por_sku = {}
        finally:
            conn.close()
        
        for d in detalles:
            id_mov, nombre, sku, cantidad, ref, obs = d
            
            # Determinar qué mostrar en la columna de series
            if sku in self.series_por_sku and len(self.series_por_sku[sku]) > 0:
                series_text = f"📋 {len(self.series_por_sku[sku])} códigos"
            elif sku in PRODUCTOS_CON_CODIGO_BARRA:
                series_text = "⚠️ Sin series"
            else:
                series_text = "—"
            
            # Insertar fila
            values = (id_mov, nombre, sku, cantidad, ref, series_text)
            self.tree.insert('', 'end', values=values)
    
    def ver_codigos_serie(self, sku, nombre_producto):
        """Abre un diálogo para ver todos los códigos de serie de un producto"""
        if sku not in self.series_por_sku or len(self.series_por_sku[sku]) == 0:
            messagebox.showinfo("Sin Series", 
                f"No hay series registradas para {nombre_producto}.", 
                parent=self.top)
            return
        
        # Crear diálogo
        dialog = tk.Toplevel(self.top)
        dialog.title(f"Códigos de Serie - {nombre_producto}")
        dialog.geometry("500x400")
        dialog.transient(self.top)
        dialog.grab_set()
        
        # Header
        header = tk.Frame(dialog, bg=Styles.PRIMARY_COLOR, pady=10)
        header.pack(fill='x')
        tk.Label(header, text=f"📦 {nombre_producto}", 
                font=('Segoe UI', 12, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack()
        tk.Label(header, text=f"SKU: {sku} | Total: {len(self.series_por_sku[sku])} series", 
                bg=Styles.PRIMARY_COLOR, fg='white').pack()
        
        # Lista de series
        list_frame = tk.Frame(dialog, padx=20, pady=10)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        listbox = tk.Listbox(list_frame, font=('Courier', 10), 
                            yscrollcommand=scrollbar.set)
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Agregar series a la lista
        for i, serie in enumerate(self.series_por_sku[sku], 1):
            listbox.insert(tk.END, f"{i}. {serie}")
        
        # Botón cerrar
        tk.Button(dialog, text="Cerrar", command=dialog.destroy,
                 bg=Styles.PRIMARY_COLOR, fg='white', font=('Segoe UI', 10),
                 relief='flat', padx=20, pady=8).pack(pady=15)
            
    def edit_item(self, event):
        item = self.tree.selection()
        if not item: return
        
        # Detectar en qué columna se hizo clic
        region = self.tree.identify("region", event.x, event.y)
        column = self.tree.identify_column(event.x)
        
        vals = self.tree.item(item[0])['values']
        
        id_mov = vals[0]
        nombre_producto = vals[1]
        sku = vals[2]
        old_qty = vals[3]
        old_ref = vals[4]
        
        # Si hizo clic en la columna de Series (#6), abrir diálogo de códigos
        if column == '#6' and sku in PRODUCTOS_CON_CODIGO_BARRA:
            self.ver_codigos_serie(sku, nombre_producto)
            return
        
        # Obtener series actuales de la base de datos
        from database import get_db_connection, run_query
        conn = get_db_connection()
        cursor = conn.cursor()
        
        series_actuales = []
        if sku in PRODUCTOS_CON_CODIGO_BARRA:
            try:
                sql = """
                    SELECT serial_number 
                    FROM series_registradas 
                    WHERE sku = ? AND DATE(fecha_ingreso) = ?
                    ORDER BY serial_number
                """
                run_query(cursor, sql, (sku, self.fecha))
                series_actuales = [row[0] for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"Error obteniendo series: {e}")
        
        conn.close()
        
        # Edit Dialog
        edit_win = tk.Toplevel(self.top)
        edit_win.title(f"Editar: {nombre_producto}")
        edit_win.geometry("700x600")
        edit_win.transient(self.top)
        edit_win.grab_set()
        
        # Header
        header = tk.Frame(edit_win, bg=Styles.PRIMARY_COLOR, pady=10)
        header.pack(fill='x')
        tk.Label(header, text=f"📦 {nombre_producto}", font=('Segoe UI', 14, 'bold'), 
                bg=Styles.PRIMARY_COLOR, fg='white').pack()
        tk.Label(header, text=f"SKU: {sku}", bg=Styles.PRIMARY_COLOR, fg='white').pack()
        
        # Información básica
        info_frame = tk.Frame(edit_win, bg='#f8f9fa', pady=10)
        info_frame.pack(fill='x', padx=20, pady=10)
        
        # Cantidad
        qty_frame = tk.Frame(info_frame, bg='#f8f9fa')
        qty_frame.pack(fill='x', pady=5)
        tk.Label(qty_frame, text="Cantidad:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa', width=15, anchor='w').pack(side='left')
        e_qty = tk.Entry(qty_frame, font=('Segoe UI', 10), width=10)
        e_qty.insert(0, str(old_qty))
        e_qty.pack(side='left', padx=5)
        
        # Referencia
        ref_frame = tk.Frame(info_frame, bg='#f8f9fa')
        ref_frame.pack(fill='x', pady=5)
        tk.Label(ref_frame, text="Referencia:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa', width=15, anchor='w').pack(side='left')
        e_ref = tk.Entry(ref_frame, font=('Segoe UI', 10), width=30)
        e_ref.insert(0, str(old_ref))
        e_ref.pack(side='left', padx=5)
        
        # Variable para almacenar series editadas
        series_editadas = series_actuales.copy()
        
        # Si el producto tiene series, mostrar sección de edición de series
        if sku in PRODUCTOS_CON_CODIGO_BARRA:
            series_frame = tk.LabelFrame(edit_win, text="📋 Códigos de Serie", 
                                        font=('Segoe UI', 11, 'bold'), padx=10, pady=10)
            series_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            # Lista de series
            list_container = tk.Frame(series_frame)
            list_container.pack(fill='both', expand=True, pady=5)
            
            scrollbar = tk.Scrollbar(list_container)
            scrollbar.pack(side='right', fill='y')
            
            listbox_series = tk.Listbox(list_container, font=('Courier', 10), 
                                       height=8, yscrollcommand=scrollbar.set)
            listbox_series.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=listbox_series.yview)
            
            def actualizar_listbox():
                listbox_series.delete(0, tk.END)
                for i, serie in enumerate(series_editadas, 1):
                    listbox_series.insert(tk.END, f"{i}. {serie}")
            
            actualizar_listbox()
            
            # Botones de acciones de series
            action_frame = tk.Frame(series_frame)
            action_frame.pack(fill='x', pady=10)
            
            def eliminar_serie():
                selection = listbox_series.curselection()
                if not selection:
                    messagebox.showwarning("Advertencia", "Seleccione una serie para eliminar.", parent=edit_win)
                    return
                
                serie_a_eliminar = series_editadas[selection[0]]
                if messagebox.askyesno("Confirmar", f"¿Eliminar la serie '{serie_a_eliminar}'?", parent=edit_win):
                    series_editadas.pop(selection[0])
                    actualizar_listbox()
                    logger.info(f"🗑️ Serie marcada para eliminar: {serie_a_eliminar}")
            
            def agregar_serie():
                # Abrir diálogo para agregar series
                add_win = tk.Toplevel(edit_win)
                add_win.title("Agregar Series")
                add_win.geometry("400x200")
                add_win.transient(edit_win)
                add_win.grab_set()
                
                tk.Label(add_win, text="¿Cuántas series desea agregar?", 
                        font=('Segoe UI', 10, 'bold')).pack(pady=10)
                
                e_cantidad = tk.Entry(add_win, font=('Segoe UI', 11), width=10)
                e_cantidad.insert(0, "1")
                e_cantidad.pack(pady=5)
                
                def procesar_agregar():
                    try:
                        cant = int(e_cantidad.get())
                        if cant <= 0:
                            messagebox.showwarning("Error", "La cantidad debe ser mayor a 0", parent=add_win)
                            return
                        
                        add_win.destroy()
                        
                        # Abrir diálogo de escaneo
                        dialog = SerialCaptureDialog(edit_win, sku, nombre_producto, cant)
                        
                        if not dialog.cancelado and len(dialog.series_capturadas) == cant:
                            # Agregar series a la lista
                            series_editadas.extend(dialog.series_capturadas)
                            actualizar_listbox()
                            logger.info(f"✅ {cant} series agregadas")
                        
                    except ValueError:
                        messagebox.showwarning("Error", "Cantidad inválida", parent=add_win)
                
                tk.Button(add_win, text="✅ Continuar", command=procesar_agregar,
                         bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10),
                         relief='flat', padx=15, pady=5).pack(pady=20)
            
            tk.Button(action_frame, text="➕ Agregar Series", command=agregar_serie,
                     bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9),
                     relief='flat', padx=10, pady=5).pack(side='left', padx=5)
            
            tk.Button(action_frame, text="🗑️ Eliminar Seleccionada", command=eliminar_serie,
                     bg='#dc3545', fg='white', font=('Segoe UI', 9),
                     relief='flat', padx=10, pady=5).pack(side='left', padx=5)
            
            tk.Label(series_frame, text="💡 Doble clic para eliminar", 
                    fg='gray', font=('Segoe UI', 8)).pack()
            
            listbox_series.bind('<Double-1>', lambda e: eliminar_serie())
        
        # Botones principales
        btn_frame = tk.Frame(edit_win, bg='#f8f9fa', pady=15)
        btn_frame.pack(fill='x', padx=20)
        
        def save():
            try:
                new_q = int(e_qty.get())
                new_r = e_ref.get()
                
                if new_q <= 0:
                    messagebox.showwarning("Error", "La cantidad debe ser mayor a 0", parent=edit_win)
                    return
                
                # Validar que la cantidad coincida con las series (si aplica)
                if sku in PRODUCTOS_CON_CODIGO_BARRA:
                    if len(series_editadas) != new_q:
                        messagebox.showwarning("Error", 
                            f"La cantidad ({new_q}) no coincide con el número de series ({len(series_editadas)}).\n\n"
                            "Por favor, ajuste las series o la cantidad.", parent=edit_win)
                        return
                
                # Actualizar movimiento
                ok, msg = actualizar_movimiento_abasto(id_mov, new_q, new_r)
                if not ok:
                    messagebox.showerror("Error", msg, parent=edit_win)
                    return
                
                
                # Si tiene series, actualizar en la base de datos
                if sku in PRODUCTOS_CON_CODIGO_BARRA:
                    conn = None
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        
                        # Eliminar series antiguas
                        sql_delete = """
                            DELETE FROM series_registradas 
                            WHERE sku = ? AND DATE(fecha_ingreso) = ?
                        """
                        run_query(cursor, sql_delete, (sku, self.fecha))
                        conn.commit()  # IMPORTANTE: Hacer commit del DELETE
                        
                        logger.info(f"🗑️ Series antiguas eliminadas para {sku}")
                        
                        # Insertar nuevas series (registrar_series_bulk abre su propia conexión)
                        if series_editadas:
                            series_data = [{'sku': sku, 'serial': s, 'ubicacion': 'BODEGA'} for s in series_editadas]
                            ok_series, msg_series = registrar_series_bulk(series_data)
                            
                            if not ok_series:
                                messagebox.showerror("Error", 
                                    f"Se eliminaron las series antiguas pero hubo un error insertando las nuevas:\n{msg_series}", 
                                    parent=edit_win)
                                return
                            
                            logger.info(f"✅ {len(series_editadas)} series nuevas registradas")
                        
                    except Exception as e:
                        if conn:
                            conn.rollback()
                        messagebox.showerror("Error", f"Error actualizando series: {e}", parent=edit_win)
                        return
                    finally:
                        if conn:
                            conn.close()
                
                messagebox.showinfo("Éxito", "Cambios guardados correctamente", parent=self.top)
                self.iniciar_carga_detalles()
                self.callback_refresh()
                edit_win.destroy()
                        
            except ValueError:
                messagebox.showerror("Error", "Cantidad inválida", parent=edit_win)
        
        tk.Button(btn_frame, text="❌ Cancelar", command=edit_win.destroy,
                 bg='#6c757d', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=15, pady=8).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="💾 Guardar Cambios", command=save, 
                 bg=Styles.SUCCESS_COLOR, fg='white', 
                 font=('Segoe UI', 10, 'bold'), relief='flat', padx=15, pady=8).pack(side='right', padx=5)
