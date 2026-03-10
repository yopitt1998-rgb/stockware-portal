import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta
import threading
import os
import pandas as pd

from ..styles import Styles
from ..utils import darken_color, mostrar_mensaje_emergente, mostrar_cargando_async
from utils.logger import get_logger
from ..pdf_generator import generar_vale_despacho

from database import (
    obtener_todos_los_skus_para_movimiento,
    registrar_movimiento_gui,
    verificar_stock_disponible,
    obtener_nombres_moviles,
    obtener_ultima_salida_movil,
    obtener_consumos_pendientes,
    eliminar_consumo_pendiente,
    obtener_info_serial,
    obtener_sku_por_codigo_barra,
    actualizar_ubicacion_serial,
    obtener_asignacion_movil_con_paquetes,
    obtener_configuracion,
    crear_recordatorio,
    get_db_connection,
    obtener_series_por_sku_y_ubicacion,
)
from config import TIPO_MOVIMIENTO_DESCARTE, PRODUCTOS_INICIALES, DATABASE_NAME, PRODUCTOS_CON_CODIGO_BARRA

logger = get_logger(__name__)

class IndividualOutputWindow:
    def __init__(self, master_app, on_close_callback=None, mode='SALIDA'):
        self.master_app = master_app
        self.master = master_app.master
        self.on_close_callback = on_close_callback
        self.mode = mode # 'SALIDA' or 'DESCARTE'
        
        title_text = "➖ Salida Individual desde Bodega" if mode == 'SALIDA' else "🗑️ Registro de Descarte"
        self.ventana = tk.Toplevel(self.master)
        self.ventana.title(title_text)
        self.ventana.geometry("900x700")
        try: 
            self.ventana.state('zoomed')
        except tk.TclError: 
            self.ventana.wm_attributes('-fullscreen', True)
        self.ventana.configure(bg='#f8f9fa')
        self.ventana.grab_set()
        
        mostrar_cargando_async(self.ventana, obtener_todos_los_skus_para_movimiento, self.construir_ui)

    def construir_ui(self, productos):
        if not productos:
            mostrar_mensaje_emergente(self.ventana, "Información", "No hay productos registrados.", "info")
            self.ventana.destroy()
            return

        is_descarte = (self.mode == 'DESCARTE')
        
        # Styles config
        header_color = Styles.INFO_COLOR if is_descarte else Styles.WARNING_COLOR
        header_text = "🗑️ REGISTRO DE DESCARTE" if is_descarte else "➖ SALIDA INDIVIDUAL DESDE BODEGA"
        bg_selector = '#E1F5FE' if is_descarte else '#FFF3E0'
        btn_text = "Confirmar Descarte" if is_descarte else "Procesar Salida Individual"
        
        # Header
        header_frame = tk.Frame(self.ventana, bg=header_color, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=header_text, 
                font=('Segoe UI', 16, 'bold'), bg=header_color, fg='white').pack(pady=20)
        
        # Frame de selectores
        frame_selector = tk.Frame(self.ventana, padx=20, pady=20, bg=bg_selector)
        frame_selector.pack(fill='x')
        
        if is_descarte:
            tk.Label(frame_selector, text="Origen:", font=('Segoe UI', 10, 'bold'), bg=bg_selector).pack(side=tk.LEFT)
            self.origen_combo = ttk.Combobox(frame_selector, state="readonly", width=15)
            self.origen_combo['values'] = ["BODEGA"] + obtener_nombres_moviles()
            self.origen_combo.set("BODEGA")
            self.origen_combo.pack(side=tk.LEFT, padx=(0, 20))
            self.origen_combo.bind("<<ComboboxSelected>>", self._on_origen_changed)
            
        tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg=bg_selector).pack(side=tk.LEFT)
        self.fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
        self.fecha_entry.insert(0, date.today().isoformat())
        self.fecha_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_selector, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg=bg_selector).pack(side=tk.LEFT, padx=(20, 5))
        self.observaciones_entry = tk.Entry(frame_selector, width=30, font=('Segoe UI', 10))
        self.observaciones_entry.pack(side=tk.LEFT, padx=10)

        # --- Barcode Scanner ---
        scan_frame = tk.Frame(self.ventana, bg='#f8f9fa', pady=5)
        scan_frame.pack(fill='x', padx=20)
        
        tk.Label(scan_frame, text="🔍 ESCANEAR CODIGO:", font=('Segoe UI', 12, 'bold'), bg='#f8f9fa', fg=header_color).pack(side='left')
        self.scan_entry = tk.Entry(scan_frame, width=30, font=('Segoe UI', 12), highlightthickness=2, highlightcolor=header_color)
        self.scan_entry.pack(side='left', padx=10)
        
        tk.Label(scan_frame, text="(Presiona Enter)", font=('Segoe UI', 9), bg='#f8f9fa', fg='gray').pack(side='left')
        
        # Tabla de productos
        self.canvas = tk.Canvas(self.ventana)
        scrollbar = ttk.Scrollbar(self.ventana, orient="vertical", command=self.canvas.yview)
        self.frame_productos_inner = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.frame_productos_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        def on_mousewheel(event):
            try:
                if self.canvas.winfo_exists():
                    self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass
        
        def _bind_mousewheel_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                _bind_mousewheel_recursive(child)
        
        _bind_mousewheel_recursive(self.canvas)
        _bind_mousewheel_recursive(self.frame_productos_inner)
        
        self.entry_vars = {} 
        self._recargar_tabla(productos)

        self.scan_entry.bind('<Return>', self.real_scan_handler)
        self.scan_entry.focus_set()
        
        tk.Button(self.ventana, text=btn_text, 
                command=self.procesar_salida_individual, 
                bg=header_color, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

    def _on_origen_changed(self, event=None):
        if not hasattr(self, 'origen_combo'): return
        origen = self.origen_combo.get()
        if origen == "BODEGA":
            mostrar_cargando_async(self.ventana, obtener_todos_los_skus_para_movimiento, self._recargar_tabla)
        else:
            def fetch_movil():
                res = obtener_asignacion_movil_con_paquetes(origen)
                return [(r[0], r[1], r[2]) for r in res]
            mostrar_cargando_async(self.ventana, fetch_movil, self._recargar_tabla)

    def _recargar_tabla(self, productos_filtrados):
        for widget in self.frame_productos_inner.winfo_children():
            widget.destroy()
            
        self.entry_vars.clear()
        self.productos_cache = productos_filtrados
        self.PRODUCTOS_CON_CODIGO_BARRA = [p[1] for p in productos_filtrados]

        is_descarte = (self.mode == 'DESCARTE')
        is_movil = is_descarte and hasattr(self, 'origen_combo') and self.origen_combo.get() != "BODEGA"
        stock_header = "Stock en Móvil" if is_movil else "Stock Bodega"
        
        tk.Label(self.frame_productos_inner, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos_inner, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos_inner, text=stock_header, font=('Segoe UI', 10, 'bold'), fg='blue' if is_movil else 'red').grid(row=0, column=2, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos_inner, text="Cant. a Procesar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
        
        fila = 1
        for row_data in productos_filtrados:
            nombre = row_data[0]
            sku = row_data[1]
            stock_actual = row_data[2]
            tk.Label(self.frame_productos_inner, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9), wraplength=300).grid(row=fila, column=0, padx=5, pady=2, sticky='w')
            tk.Label(self.frame_productos_inner, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='w')
            tk.Label(self.frame_productos_inner, text=str(stock_actual), anchor='center', font=('Segoe UI', 9), fg='blue' if is_movil else 'red').grid(row=fila, column=2, padx=5, pady=2, sticky='w')
            entry = tk.Entry(self.frame_productos_inner, width=10, font=('Segoe UI', 9))
            entry.grid(row=fila, column=3, padx=5, pady=2)
            self.entry_vars[sku] = entry
            fila += 1
            
        self.frame_productos_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.frame_productos_inner.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def real_scan_handler(self, event):
        raw_code = self.scan_entry.get().strip().upper()
        self.scan_entry.delete(0, tk.END)
        if not raw_code: return

        # obtener_sku_por_codigo_barra ya normaliza comillas
        sku = obtener_sku_por_codigo_barra(raw_code)
        if not sku:
            sku = raw_code # Fallback a búsqueda directa

        if sku in self.entry_vars:
            entry_widget = self.entry_vars[sku]
            try:
                curr = entry_widget.get().strip()
                val = int(curr) + 1 if curr else 1
                
                max_stock = next((st for n, s, st in self.productos_cache if s == sku), 0)
                
                if val > max_stock:
                        messagebox.showwarning("Stock Insuficiente", f"No hay suficiente stock para {sku}. Max: {max_stock}", master=self.ventana)
                else:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, str(val))
                    entry_widget.config(bg=Styles.SUCCESS_COLOR, fg='white')
                    self.ventana.after(500, lambda: entry_widget.config(bg='white', fg='black'))

            except ValueError: pass
        else:
            messagebox.showwarning("No Encontrado", f"Producto {sku} no listado.", master=self.ventana)
        
        self.scan_entry.delete(0, tk.END)

    def procesar_salida_individual(self):
        fecha_evento = self.fecha_entry.get().strip()
        observaciones = self.observaciones_entry.get().strip()
        
        if not fecha_evento:
            mostrar_mensaje_emergente(self.ventana, "Error", "La fecha del evento es obligatoria.", "error")
            return

        exitos = 0; errores = 0; mensaje_error = ""
        is_descarte = (self.mode == 'DESCARTE')
        movil_afectado = None
        if is_descarte and hasattr(self, 'origen_combo'):
            origen = self.origen_combo.get()
            if origen != "BODEGA":
                movil_afectado = origen
                
        tipo_mov = TIPO_MOVIMIENTO_DESCARTE if is_descarte else 'SALIDA'
        prefix_obs = "DESCARTE" if is_descarte else "SALIDA INDIVIDUAL"

        for sku, entry in self.entry_vars.items():
            try:
                cantidad_text = entry.get().strip()
                if cantidad_text:
                    cantidad = int(cantidad_text)
                    if cantidad > 0:
                        stock_actual = next((st for n, s, st in self.productos_cache if str(s) == str(sku)), 0)
                        if stock_actual >= cantidad:
                            disponible, stock = True, stock_actual
                        else:
                            disponible, stock = False, stock_actual
                            
                        if not disponible:
                            errores += 1
                            mensaje_error += f"\\n- {sku}: Stock insuficiente en origen ({stock} < {cantidad})"
                            entry.configure(bg='#FFCDD2')
                            continue
                            
                        obs_final = f"{prefix_obs} - {observaciones}" if observaciones else prefix_obs
                        exito, mensaje = registrar_movimiento_gui(sku, tipo_mov, cantidad, movil_afectado, fecha_evento, None, obs_final)
                        if exito: exitos += 1
                        else:
                            errores += 1
                            mensaje_error += f"\\n- SKU {sku}: {mensaje}"
            except ValueError:
                if cantidad_text: errores += 1; mensaje_error += f"\\n- SKU {sku}: Cantidad no válida"
            except Exception as e:
                errores += 1
                mensaje_error += f"\\n- SKU {sku} (Error Inesperado): {e}"

        if exitos > 0 or errores > 0:
            if errores > 0:
                mostrar_mensaje_emergente(self.ventana, "Proceso Finalizado con Errores", 
                                            f"Se completaron {exitos} registros y ocurrieron {errores} errores. Revise:\\n{mensaje_error}", 
                                            "warning")
            else:
                mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} registros exitosamente.", "success")
                if self.on_close_callback: self.on_close_callback()
                self.ventana.destroy() # Solo cerrar si no hay errores o al menos hubo éxito total
        elif exitos == 0 and errores == 0:
            mostrar_mensaje_emergente(self.ventana, "Información", "No se ingresó ninguna cantidad.", "info")



class MobileOutputWindow:
    def __init__(self, master_app, on_close_callback=None):
        self.master_app = master_app
        self.master = master_app.master
        self.on_close_callback = on_close_callback
        
        self.ventana = tk.Toplevel(self.master)
        self.ventana.title("📤 Salida a Móvil - Con Paquetes")
        try: 
            self.ventana.state('zoomed')
        except tk.TclError: 
            self.ventana.wm_attributes('-fullscreen', True)
        self.ventana.configure(bg='#f8f9fa')
        self.ventana.grab_set()

        self.salida_entries = {}
        self.seriales_escaneados = {}

        # Iniciar carga async
        mostrar_cargando_async(self.ventana, self.carga_datos, self.construir_ui)

    def carga_datos(self):
        return obtener_todos_los_skus_para_movimiento(), obtener_nombres_moviles()

    def construir_ui(self, datos_carga):
        self.productos, moviles_db = datos_carga
        
        if not self.productos:
            mostrar_mensaje_emergente(self.ventana, "Información", "No hay productos registrados.", "info")
            self.ventana.destroy()
            return

        # Header moderno
        header_frame = tk.Frame(self.ventana, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(side='top', fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📤 SALIDA A MÓVIL", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Botón de Procesar (FIJO ABAJO)
        btn_procesar_salida = tk.Button(self.ventana, text="✅ Procesar Salida a Móvil", 
                  command=self.procesar_salida,
                  bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 12, 'bold'))
        btn_procesar_salida.pack(side='bottom', fill='x', padx=20, pady=10)

        # --- SETUP GLOBAL SCROLLBAR ---
        main_container = tk.Frame(self.ventana, bg='#f8f9fa')
        main_container.pack(fill='both', expand=True, padx=10)
        
        canvas = tk.Canvas(main_container, bg='#f8f9fa')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f8f9fa')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def on_canvas_configure(event):
            canvas.itemconfig(canvas.create_window((0,0), window=scrollable_frame, anchor='nw'), width=event.width)
        
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas.find_all()[0], width=e.width))
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mousewheel local pattern (Recursive)
        def on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        def _bind_mousewheel_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                _bind_mousewheel_recursive(child)

        _bind_mousewheel_recursive(canvas)
        _bind_mousewheel_recursive(scrollable_frame)

        # Frame de selectores
        frame_selector = tk.Frame(scrollable_frame, padx=10, pady=10, bg='#F8BBD0')
        frame_selector.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_selector, text="Móvil Destino:", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT)
        self.movil_combo = ttk.Combobox(frame_selector, values=moviles_db, state="readonly", width=15)
        self.movil_combo.set("--- Seleccionar Móvil ---")
        self.movil_combo.pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_selector, text="Fecha:", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT, padx=(10, 5))
        self.fecha_entry = tk.Entry(frame_selector, width=12, font=('Segoe UI', 10))
        self.fecha_entry.insert(0, date.today().isoformat())
        self.fecha_entry.pack(side=tk.LEFT)

        tk.Label(frame_selector, text="Paquete:", font=('Segoe UI', 10, 'bold'), bg='#F8BBD0').pack(side=tk.LEFT, padx=(10, 5))
        self.paquete_combo = ttk.Combobox(frame_selector, values=["NINGUNO", "PAQUETE A", "PAQUETE B", "CARRO", "PERSONALIZADO"], state="readonly", width=15)
        self.paquete_combo.set("NINGUNO")
        self.paquete_combo.pack(side=tk.LEFT, padx=5)
        
        # Frame de botones de utilidad
        frame_utilidad = tk.Frame(scrollable_frame, padx=10, pady=5, bg='#f8f9fa')
        frame_utilidad.pack(fill='x', padx=10)
        
        tk.Button(frame_utilidad, text="🔄 Rellenar desde última salida", 
                command=self.rellenar_desde_ultima_salida,
                bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                relief='flat', bd=0, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
                
        tk.Button(frame_utilidad, text="🧹 Limpiar campos", 
                command=self.limpiar_campos,
                bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                relief='flat', bd=0, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        # ==================== NUEVO: SISTEMA DE ESCANEO COLAPSABLE ====================
        frame_toggle = tk.Frame(scrollable_frame, bg='#f8f9fa')
        frame_toggle.pack(fill='x', padx=20, pady=5)
        
        self.scan_visible_var = tk.BooleanVar(value=False)
        self.frame_escaneo_container = tk.Frame(scrollable_frame, bg='#E3F2FD', bd=1, relief='solid')

        def toggle_scanner():
            if self.scan_visible_var.get():
                self.frame_escaneo_container.pack(fill='x', padx=20, pady=5)
                self.entry_scan.focus_set()
            else:
                self.frame_escaneo_container.pack_forget()
        
        chk_toggle_scanner = tk.Checkbutton(frame_toggle, text="🔍 Activar Escáner (Seriales o SKUs)", 
                                            variable=self.scan_visible_var, command=toggle_scanner,
                                            bg='#f8f9fa', font=('Segoe UI', 11, 'bold'),
                                            fg=Styles.PRIMARY_COLOR, activebackground='#f8f9fa')
        chk_toggle_scanner.pack(side='left')

        from collections import defaultdict
        self.seriales_escaneados = defaultdict(list)
        
        frame_escaneo = tk.Frame(self.frame_escaneo_container, bg='#E3F2FD', padx=10, pady=10)
        frame_escaneo.pack(fill='x')
        
        tk.Label(frame_escaneo, text="Código / Serial:", font=('Segoe UI', 10, 'bold'), 
                 bg='#E3F2FD').pack(side='left', padx=5)
        self.entry_scan = tk.Entry(frame_escaneo, font=('Segoe UI', 12), width=25, bg='white')
        self.entry_scan.pack(side='left', padx=5)
        
        self.lbl_total_escaneados = tk.Label(frame_escaneo, 
                                        text="Total escaneado: 0 equipos",
                                        font=('Segoe UI', 10, 'bold'), 
                                        bg='#E3F2FD', fg=Styles.SUCCESS_COLOR)
        self.lbl_total_escaneados.pack(side='left', padx=20)
        
        btn_limpiar_scan = tk.Button(frame_escaneo, text="🗑️ Limpiar Escaneados",
                                      command=self.limpiar_escaneados,
                                      bg='#FF9800', fg='white', 
                                      font=('Segoe UI', 9, 'bold'),
                                      relief='flat', padx=10, pady=5)
        btn_limpiar_scan.pack(side='left', padx=10)
        
        frame_tabla_escaneados = tk.LabelFrame(self.frame_escaneo_container, 
                                               text="📋 Equipos Escaneados", 
                                               font=('Segoe UI', 10, 'bold'), bg='#E3F2FD')
        frame_tabla_escaneados.pack(fill='x', expand=False, padx=10, pady=5)
        
        self.tree_escaneados = ttk.Treeview(frame_tabla_escaneados,
                                       columns=('Producto', 'SKU', 'Cantidad', 'Seriales'),
                                       show='headings', height=4)
        self.tree_escaneados.heading('Producto', text='Producto')
        self.tree_escaneados.heading('SKU', text='SKU')
        self.tree_escaneados.heading('Cantidad', text='Cantidad')
        self.tree_escaneados.heading('Seriales', text='Seriales (primeros 5)')
        
        self.tree_escaneados.column('Producto', width=200)
        self.tree_escaneados.column('SKU', width=80, anchor='center')
        self.tree_escaneados.column('Cantidad', width=70, anchor='center')
        self.tree_escaneados.column('Seriales', width=350)
        
        self.tree_escaneados.pack(fill='both', expand=True, padx=5, pady=5)
        
        scrollbar_tree = ttk.Scrollbar(frame_tabla_escaneados, orient='vertical', 
                                       command=self.tree_escaneados.yview)
        self.tree_escaneados.configure(yscrollcommand=scrollbar_tree.set)
        scrollbar_tree.pack(side='right', fill='y')
        
        self.entry_scan.bind('<Return>', self.procesar_serial_escaneado)
        
        lbl_info_modo = tk.Label(scrollable_frame, 
                                 text="💡 Puede usar escaneo de códigos O ingresar cantidades manualmente abajo",
                                 font=('Segoe UI', 9, 'italic'), 
                                 fg='#666', bg='#f8f9fa')
        lbl_info_modo.pack(pady=5)
        
        ttk.Separator(scrollable_frame, orient='horizontal').pack(fill='x', padx=20, pady=5)
        
        tk.Label(scrollable_frame, text="📦 LISTA DE PRODUCTOS - Ingreso Manual de Cantidades", 
                 font=('Segoe UI', 11, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(pady=5)
        
        frame_productos_grid = tk.Frame(scrollable_frame, bg='#ffffff', bd=1, relief='solid')
        frame_productos_grid.pack(fill='x', padx=20, pady=5)
        
        tk.Label(frame_productos_grid, text="Nombre", font=('Segoe UI', 10, 'bold'), bg='#eee').grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        tk.Label(frame_productos_grid, text="SKU", font=('Segoe UI', 10, 'bold'), bg='#eee').grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        tk.Label(frame_productos_grid, text="Stock Actual", font=('Segoe UI', 10, 'bold'), fg='red', bg='#eee').grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        tk.Label(frame_productos_grid, text="Cant. a Asignar", font=('Segoe UI', 10, 'bold'), bg='#eee').grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        
        frame_productos_grid.grid_columnconfigure(0, weight=3)
        frame_productos_grid.grid_columnconfigure(1, weight=1)
        frame_productos_grid.grid_columnconfigure(2, weight=1)
        frame_productos_grid.grid_columnconfigure(3, weight=1)
        
        fila = 1
        for nombre, sku, cantidad_actual in self.productos:
            bg_color = '#ffffff' if fila % 2 == 0 else '#f9f9f9'
            
            tk.Label(frame_productos_grid, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9), bg=bg_color).grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
            tk.Label(frame_productos_grid, text=sku, anchor='center', font=('Segoe UI', 9), bg=bg_color).grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
            tk.Label(frame_productos_grid, text=str(cantidad_actual), anchor='center', font=('Segoe UI', 9), fg='red', bg=bg_color).grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
            entry = tk.Entry(frame_productos_grid, width=8, font=('Segoe UI', 9))
            entry.grid(row=fila, column=3, padx=5, pady=2)
            self.salida_entries[sku] = entry
            fila += 1
            
        scrollable_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def rellenar_desde_ultima_salida(self):
        movil_seleccionado = self.movil_combo.get()
        if movil_seleccionado == "--- Seleccionar Móvil ---":
            mostrar_mensaje_emergente(self.ventana, "Error", "Debe seleccionar un móvil primero.", "error")
            return
            
        ultima_salida = obtener_ultima_salida_movil(movil_seleccionado)
        if not ultima_salida:
            mostrar_mensaje_emergente(self.ventana, "Información", f"No se encontró una salida previa para {movil_seleccionado}.", "info")
            return
            
        for entry in self.salida_entries.values():
            entry.delete(0, tk.END)
            
        for sku, cantidad in ultima_salida:
            if sku in self.salida_entries:
                self.salida_entries[sku].insert(0, str(cantidad))
                
        mostrar_mensaje_emergente(self.ventana, "Éxito", f"Datos de última salida cargados para {movil_seleccionado}.", "success")

    def limpiar_campos(self):
        for entry in self.salida_entries.values():
            entry.delete(0, tk.END)
        mostrar_mensaje_emergente(self.ventana, "Información", "Todos los campos han sido limpiados.", "info")

    def limpiar_escaneados(self):
        if not self.seriales_escaneados:
            return
        total = sum(len(s) for s in self.seriales_escaneados.values())
        if messagebox.askyesno("Limpiar", f"¿Está seguro de limpiar todos los {total} equipos escaneados?", parent=self.ventana):
            self.seriales_escaneados.clear()
            self.actualizar_tabla_escaneados()
            self.entry_scan.focus_set()

    def actualizar_tabla_escaneados(self):
        for item in self.tree_escaneados.get_children():
            self.tree_escaneados.delete(item)
        
        total_equipos = 0
        for sku in sorted(self.seriales_escaneados.keys()):
            seriales_list = self.seriales_escaneados[sku]
            cantidad = len(seriales_list)
            total_equipos += cantidad
            
            nombre_producto = "Producto Desconocido"
            for nombre, sku_prod, _ in self.productos:
                if sku_prod == sku:
                    nombre_producto = nombre
                    break
            
            seriales_display = ", ".join(seriales_list[:5])
            if len(seriales_list) > 5:
                seriales_display += f" ... (+{len(seriales_list) - 5} más)"
            
            self.tree_escaneados.insert('', 'end', values=(nombre_producto, sku, cantidad, seriales_display))
        
        self.lbl_total_escaneados.config(text=f"Total escaneado: {total_equipos} equipos")

    def procesar_serial_escaneado(self, event):
        serial = self.entry_scan.get().strip().upper()
        if not serial: return
        
        from database import obtener_sku_por_codigo_barra
        from tkinter import simpledialog
        
        # 0. Check SKU (obtener_sku_por_codigo_barra ya normaliza comillas)
        sku_encontrado_lista = obtener_sku_por_codigo_barra(serial)
        
        if sku_encontrado_lista and sku_encontrado_lista in self.salida_entries:
            # Encontrado en la lista de entradas manuales
            pass
        elif serial in self.salida_entries:
            sku_encontrado_lista = serial
        
        if sku_encontrado_lista:
            nombre_prod = "Producto"
            for nom, s, _ in self.productos:
                if s == sku_encontrado_lista:
                    nombre_prod = nom
                    break
            
            qty = simpledialog.askinteger("Input Escáner", 
                                        f"Producto: {nombre_prod}\\nSKU: {serial}\\n\\nIngrese cantidad a asignar:",
                                        parent=self.ventana, minvalue=1)
            if qty:
                entry_widget = self.salida_entries[sku_encontrado_lista]
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, str(qty))
                entry_widget.config(bg='#e8f5e9')
                
                self.entry_scan.delete(0, tk.END)
                self.entry_scan.config(bg='#C8E6C9')
                self.ventana.after(200, lambda: self.entry_scan.config(bg='white'))
            
            self.entry_scan.focus_set()
            return

        # 1. Serial Logic
        sku, ubicacion = obtener_info_serial(serial)
        
        if not sku:
            messagebox.showerror("Serial No Encontrado", f"El serial '{serial}' no existe en la base de datos.\\n\\nVerifique que fue registrado en Abasto.", parent=self.ventana)
            self.entry_scan.delete(0, tk.END)
            self.entry_scan.focus_set()
            return
        
        if ubicacion != 'BODEGA':
            messagebox.showwarning("Serial Ya Asignado", f"El serial '{serial}' ya está asignado a: {ubicacion}\\n\\nNo se puede asignar nuevamente.", parent=self.ventana)
            self.entry_scan.delete(0, tk.END)
            self.entry_scan.focus_set()
            return
        
        if serial in self.seriales_escaneados[sku]:
            messagebox.showinfo("Duplicado", f"El serial '{serial}' ya fue escaneado en esta sesión.", parent=self.ventana)
            self.entry_scan.delete(0, tk.END)
            self.entry_scan.focus_set()
            return
        
        self.seriales_escaneados[sku].append(serial)
        self.actualizar_tabla_escaneados()
        
        self.entry_scan.delete(0, tk.END)
        self.entry_scan.config(bg='#C8E6C9') 
        self.ventana.after(200, lambda: self.entry_scan.config(bg='white'))
        self.entry_scan.focus_set()

        movil_seleccionado = self.movil_combo.get()
        fecha_evento = self.fecha_entry.get().strip()
        paquete = self.paquete_combo.get()
        if paquete == "NINGUNO": paquete = None
        
        if movil_seleccionado == "--- Seleccionar Móvil ---":
            mostrar_mensaje_emergente(self.ventana, "Error", "Debe seleccionar un Móvil.", "error")
            return
            
        if not fecha_evento:
            mostrar_mensaje_emergente(self.ventana, "Error", "La fecha del evento es obligatoria.", "error")
            return
        
        if self.seriales_escaneados:
            self._procesar_modo_escaneo(movil_seleccionado, fecha_evento, paquete)
        else:
            self._procesar_modo_manual(movil_seleccionado, fecha_evento, paquete)

    def _procesar_modo_escaneo(self, movil, fecha, paquete):
        total_equipos = sum(len(s) for s in self.seriales_escaneados.values())
        if not messagebox.askyesno("Confirmar Asignación", f"¿Confirma asignar {total_equipos} equipos escaneados a {movil}?", parent=self.ventana):
            return
        
        exitos = 0
        errores = 0
        errores_detalle = []
        
        # OPTIMIZACIÓN BATCH: Usar una sola conexión para todas las operaciones
        from database import get_db_connection, close_connection
        conn = None
        try:
            conn = get_db_connection()
            
            for sku, seriales_list in self.seriales_escaneados.items():
                cantidad = len(seriales_list)
                exito_mov, mensaje_mov = registrar_movimiento_gui(
                    sku, 'SALIDA_MOVIL', cantidad, movil,
                    fecha, paquete, f"Asignación por escaneo - {cantidad} equipos",
                    existing_conn=conn
                )
                
                if not exito_mov:
                    errores += cantidad
                    errores_detalle.append(f"SKU {sku}: {mensaje_mov}")
                    continue
                
                for serial in seriales_list:
                    exito_ser, mensaje_ser = actualizar_ubicacion_serial(
                        serial, movil, paquete=paquete, existing_conn=conn
                    )
                    if exito_ser: exitos += 1
                    else:
                        errores += 1
                        errores_detalle.append(f"Serial {serial}: {mensaje_ser}")
            
            # Commit único al final del batch
            if errores == 0:
                conn.commit()
            else:
                conn.rollback()
                exitos = 0  # Revertir: no hubo éxito parcial
        except Exception as e:
            if conn:
                try: conn.rollback()
                except: pass
            errores += 1
            errores_detalle.append(f"Error de transacción: {e}")
        finally:
            if conn: close_connection(conn)
        
        if errores == 0:
            mostrar_mensaje_emergente(self.master, "Éxito", f"Se asignaron {exitos} equipos exitosamente a {movil}.", "success")
            self.ofrecer_pdf(movil, self.seriales_escaneados.items())
            if self.on_close_callback: self.on_close_callback()
            self.ventana.destroy()
        else:
            mensaje = f"Se procesaron algunos items con errores:\n\nÉxitos: {exitos}\nErrores: {errores}\n\nDetalles:\n" + "\n".join(errores_detalle[:5])
            mostrar_mensaje_emergente(self.ventana, "Proceso con Errores", mensaje, "warning")
            # MANTENER VENTANA ABIERTA PARA CORRECCIÓN
        
        if exitos > 0: self.crear_recordatorios_automaticos(fecha)

    def _procesar_modo_manual(self, movil, fecha, paquete):
        # Recolectar ítems válidos primero
        items_a_procesar = []
        for sku, entry in self.salida_entries.items():
            cant_str = entry.get().strip()
            if cant_str and cant_str.isdigit() and int(cant_str) > 0:
                items_a_procesar.append((sku, int(cant_str)))
        
        if not items_a_procesar:
            mostrar_mensaje_emergente(self.ventana, "Información", "No se ingresaron cantidades válidas para procesar.", "info")
            return
        
        exitos = 0
        errores = 0
        errores_msg = []
        
        # OPTIMIZACIÓN BATCH: Usar una sola conexión para todas las operaciones
        from database import get_db_connection, close_connection
        conn = None
        try:
            conn = get_db_connection()
            
            for sku, cantidad in items_a_procesar:
                exito, msg = registrar_movimiento_gui(
                    sku, 'SALIDA_MOVIL', cantidad,
                    movil_afectado=movil,
                    fecha_evento=fecha,
                    paquete_asignado=paquete,
                    observaciones="Salida Manual a Móvil",
                    existing_conn=conn
                )
                if exito: exitos += 1
                else:
                    errores += 1
                    errores_msg.append(f"{sku}: {msg}")
            
            # Commit único al final del batch
            if errores == 0:
                conn.commit()
            else:
                conn.rollback()
                exitos = 0  # Revertir
        except Exception as e:
            if conn:
                try: conn.rollback()
                except: pass
            errores += 1
            errores_msg.append(f"Error de transacción: {e}")
        finally:
            if conn: close_connection(conn)
        
        if exitos > 0 and errores == 0:
            mostrar_mensaje_emergente(self.ventana, "Éxito", f"{exitos} productos asignados a {movil}.", "success")
            # PDF Logic manual
            productos_pdf = [(sku, str(cant)) for sku, cant in items_a_procesar]
            self.ofrecer_pdf_manual(movil, productos_pdf)
            if self.on_close_callback: self.on_close_callback()
            self.ventana.destroy()
        elif errores > 0:
            mostrar_mensaje_emergente(self.ventana, "Error", f"Todos los cambios fueron revertidos. Revise los errores:\n{chr(10).join(errores_msg)}", "error")
        
        if exitos > 0: self.crear_recordatorios_automaticos(fecha)

    def ofrecer_pdf(self, movil, items_iter):
        if messagebox.askyesno("Vale de Despacho", "¿Desea generar el Vale de Despacho en PDF para este movimiento?", parent=self.ventana):
            productos_pdf = []
            for sku, seriales_list in items_iter:
                nombre_p = "Producto"
                for p in self.productos:
                    if str(p[1]) == str(sku):
                        nombre_p = p[0]
                        break
                productos_pdf.append((sku, nombre_p, str(len(seriales_list))))
            self._generar_pdf_file(movil, productos_pdf)

    def ofrecer_pdf_manual(self, movil, items_iter):
        if messagebox.askyesno("Vale de Despacho", "¿Desea generar el Vale de Despacho en PDF para este movimiento?", parent=self.ventana):
            productos_pdf = []
            for sku, qty in items_iter:
                nombre_p = "Producto"
                for p in self.productos:
                    if str(p[1]) == str(sku):
                        nombre_p = p[0]
                        break
                productos_pdf.append((sku, nombre_p, str(qty)))
            self._generar_pdf_file(movil, productos_pdf)

    def _generar_pdf_file(self, movil, productos_pdf):
        if not productos_pdf: return
        filename = filedialog.asksaveasfilename(title="Guardar Vale de Despacho", initialfile=f"Vale_{movil.replace(' ', '_')}_{date.today().isoformat()}.pdf", defaultextension=".pdf", filetypes=[("Archivo PDF", "*.pdf")])
        if filename:
            datos_vale = {
                'folio': f"{date.today().strftime('%Y%m%d')}-{movil.split()[-1]}",
                'fecha': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'movil': movil,
                'tecnico': 'N/A',
                'usuario': self.master_app.usuario_actual or 'Admin'
            }
            exito_pdf, msg_pdf = generar_vale_despacho(datos_vale, productos_pdf, filename)
            if exito_pdf: mostrar_mensaje_emergente(self.master, "PDF Guardado", f"Vale de despacho generado: {filename}", "success")
            else: mostrar_mensaje_emergente(self.master, "Error PDF", f"No se pudo generar el PDF: {msg_pdf}", "error")

    def crear_recordatorios_automaticos(self, fecha_salida):
        try:
            fecha_salida_date = datetime.strptime(fecha_salida, '%Y-%m-%d').date()
            fecha_retorno = fecha_salida_date + timedelta(days=1)
            fecha_conciliacion = fecha_salida_date + timedelta(days=2)
            
            import sqlite3
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
            conn.close()
            
            recordatorios_creados = 0
            for movil, paquete in salidas:
                if movil and paquete:
                    if crear_recordatorio(movil, paquete, 'RETORNO', fecha_retorno.isoformat()): recordatorios_creados += 1
                    if crear_recordatorio(movil, paquete, 'CONCILIACION', fecha_conciliacion.isoformat()): recordatorios_creados += 1
            
            if recordatorios_creados > 0:
                mostrar_mensaje_emergente(self.master, "Éxito", f"Se crearon {recordatorios_creados} recordatorios automáticos.", "success")
        except Exception as e:
            logger.error(f"Error al crear recordatorios automáticos: {e}")



class MobileReturnWindow:
    def __init__(self, master_app, on_close_callback=None):
        self.master_app = master_app
        self.master = master_app.master
        self.on_close_callback = on_close_callback
        
        self.ventana = tk.Toplevel(self.master)
        self.ventana.title("🔄 Historial de Instalaciones y Retorno")
        try: 
            self.ventana.state('zoomed')
        except: 
            self.ventana.wm_attributes('-fullscreen', True)
        self.ventana.configure(bg='#f8f9fa')
        self.ventana.grab_set()

        self.session_data = {
            'movil': None,
            'fecha': date.today().isoformat(),
            'excel_data': [],
            'stock_teorico': {},
            'consumo_app': {},
            'consumo_verificado': {},
            'stock_fisico_escaneado': {},
            'stock_danado': {},
            'seriales_danados': {},
        }
        
        try:
             self.productos = obtener_todos_los_skus_para_movimiento()
        except:
             self.productos = PRODUCTOS_INICIALES

        self.construir_ui()

    def construir_ui(self):
        header = tk.Frame(self.ventana, bg=Styles.PRIMARY_COLOR, height=70)
        header.pack(fill='x'); header.pack_propagate(False)
        tk.Label(header, text="🛡️ HISTORIAL DE INSTALACIONES Y RETORNO", font=('Segoe UI', 18, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=15)

        main_frame = tk.Frame(self.ventana, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # SECCIÓN 1: SELECCIÓN Y CARGA (TOP)
        top_panel = tk.LabelFrame(main_frame, text="1. Configuración de Retorno", bg='white', font=('Segoe UI', 10, 'bold'))
        top_panel.pack(fill='x', pady=5)
        
        tk.Label(top_panel, text="Móvil / Técnico:", bg='white').pack(side='left', padx=10, pady=10)
        self.movil_combo = ttk.Combobox(top_panel, width=25, state='readonly')
        self.movil_combo.pack(side='left', padx=5)

        # Label dinámico: muestra el técnico (conductor) del móvil seleccionado
        self.lbl_tecnico = tk.Label(top_panel, text="👤 —", bg='white',
                                    font=('Segoe UI', 10, 'bold'), fg=Styles.PRIMARY_COLOR)
        self.lbl_tecnico.pack(side='left', padx=(5, 20))

        threading.Thread(target=self._load_moviles_con_tecnicos, daemon=True).start()

        self.entry_fecha = tk.Entry(top_panel, width=12)
        self.entry_fecha.insert(0, self.session_data['fecha'])
        self.entry_fecha.pack(side='left')

        tk.Label(top_panel, text="Filtrar por Paquete:", bg='white').pack(side='left', padx=(20, 10))
        self.paquete_combo = ttk.Combobox(top_panel, values=["TODOS", "PAQUETE A", "PAQUETE B", "CARRO", "PERSONALIZADO", "NINGUNO"], state='readonly', width=15)
        self.paquete_combo.set("PAQUETE A")
        self.paquete_combo.pack(side='left', padx=5)
        self.paquete_combo.bind("<<ComboboxSelected>>", lambda e: self.update_consumo_ui())

        # SECCIÓN 2: AUDITORÍA DE CONSUMO (Left)
        left_panel = tk.LabelFrame(main_frame, text="2. Auditoría de Consumo (Activaciones vs App)", bg='white', font=('Segoe UI', 10, 'bold'), width=500)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10), pady=5)
        
        self.btn_import_excel = tk.Button(left_panel, text="📥 Cargar Excel Activaciones", bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9), command=self.load_excel_activations)
        self.btn_import_excel.pack(pady=5)
        
        self.tree_consumo = ttk.Treeview(left_panel, columns=('Producto', 'App', 'Excel', 'Dif'), show='headings')
        self.tree_consumo.heading('Producto', text='Producto'); self.tree_consumo.column('Producto', width=150)
        self.tree_consumo.heading('App', text='App'); self.tree_consumo.column('App', width=50, anchor='center')
        self.tree_consumo.heading('Excel', text='Activ.'); self.tree_consumo.column('Excel', width=50, anchor='center')
        self.tree_consumo.heading('Dif', text='Estado'); self.tree_consumo.column('Dif', width=80, anchor='center')
        self.tree_consumo.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tree_consumo.tag_configure('ok', background='#d4edda')
        self.tree_consumo.tag_configure('error', background='#f8d7da')

        # SECCIÓN 3: AUDITORÍA FÍSICA (Right)
        right_panel = tk.LabelFrame(main_frame, text="3. Auditoría Física (Stock Esperado vs Real)", bg='white', font=('Segoe UI', 10, 'bold'))
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0), pady=5)
        
        scan_frame = tk.Frame(right_panel, bg='white')
        scan_frame.pack(fill='x', pady=5)
        tk.Label(scan_frame, text="🔍 ESCANEAR:", fg=Styles.PRIMARY_COLOR, font=('Segoe UI', 12, 'bold'), bg='white').pack(side='left', padx=10)
        self.entry_scan = tk.Entry(scan_frame, font=('Segoe UI', 12), width=25, bg='#e8f0fe')
        self.entry_scan.pack(side='left', padx=5)
        self.entry_scan.focus_set()
        
        self.var_danado = tk.BooleanVar(value=False)
        self.chk_danado = tk.Checkbutton(scan_frame, text="⚠️ Es Dañado", variable=self.var_danado, bg='white', fg='#c0392b', font=('Segoe UI', 10, 'bold'), activebackground='white')
        self.chk_danado.pack(side='left', padx=10)

        self.tree_fisico = ttk.Treeview(right_panel, columns=('SKU', 'Producto', 'Esperado', 'Escaneado', 'Estado'), show='headings')
        self.tree_fisico.heading('SKU', text='SKU'); self.tree_fisico.column('SKU', width=80)
        self.tree_fisico.heading('Producto', text='Producto'); self.tree_fisico.column('Producto', width=150)
        self.tree_fisico.heading('Esperado', text='Deben Tener', anchor='center')
        self.tree_fisico.column('Esperado', width=80)
        self.tree_fisico.heading('Escaneado', text='Físico', anchor='center')
        self.tree_fisico.column('Escaneado', width=80)
        self.tree_fisico.heading('Estado', text='Estado', anchor='center')
        self.tree_fisico.column('Estado', width=80)
        self.tree_fisico.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tree_fisico.tag_configure('found', background='#d4edda')
        self.tree_fisico.tag_configure('missing', background='#c0392b', foreground='white')  # dark red
        self.tree_fisico.tag_configure('extra', background='#fff3cd')

        # --- ACTIONS ---
        bottom_panel = tk.Frame(self.ventana, bg='#f8f9fa', height=60)
        bottom_panel.pack(fill='x', side='bottom')
        
        self.btn_autorelleno = tk.Button(bottom_panel, text="🚀 Auto-Rellenar Faltantes", 
                               bg='#e67e22', fg='white', font=('Segoe UI', 12, 'bold'),
                               state='disabled', padx=20, pady=10, command=self.auto_rellenar)
        self.btn_autorelleno.pack(side='left', padx=20, pady=10)
        
        self.lbl_faltantes_count = tk.Label(bottom_panel, text="", fg='#c0392b', 
                                            font=('Segoe UI', 10, 'bold'), bg='#f8f9fa')
        self.lbl_faltantes_count.pack(side='left', padx=5)
        
        self.btn_procesar = tk.Button(bottom_panel, text="⚙️ Procesar", 
                               bg='#2ecc71', fg='white', font=('Segoe UI', 12, 'bold'),
                               state='normal', padx=20, pady=10, command=self.finalizar)
        self.btn_procesar.pack(side='right', padx=20, pady=10)

        # Bindings
        self.movil_combo.bind("<<ComboboxSelected>>", self.on_movil_select)
        self.entry_scan.bind("<Return>", self.on_scan)
        self.tree_fisico.bind("<Double-1>", self.mostrar_detalle_mac)
        self.entry_fecha.focus_set()

    def _load_moviles_con_tecnicos(self):
        """Carga los móviles junto con el nombre de su conductor para mostrar al seleccionar."""
        try:
            from database import obtener_moviles, obtener_nombres_moviles
            moviles_data = obtener_moviles(solo_activos=True)
            # Guardamos dict {nombre_movil: conductor}
            self._movil_tecnico_map = {m[0]: m[2] for m in moviles_data if len(m) > 2 and m[2]}  # m[2] = conductor
            nombres = [m[0] for m in moviles_data]
            
            # Fallback if empty
            if not nombres:
                nombres = obtener_nombres_moviles()
        except Exception as e:
            print(f"DEBUG: Error loading mobiles in thread: {e}")
            self._movil_tecnico_map = {}
            try:
                from database import obtener_nombres_moviles
                nombres = obtener_nombres_moviles()
            except:
                nombres = []
                
        if self.ventana.winfo_exists():
            self.ventana.after(0, lambda: self._update_combo(nombres))
            
    def _update_combo(self, values):
        self.movil_combo['values'] = values
        if not hasattr(self, '_movil_tecnico_map'):
            self._movil_tecnico_map = {}

    def reset_session(self):
        self.session_data['stock_teorico'] = {}
        self.session_data['consumo_app'] = {}
        self.session_data['consumo_verificado'] = {}
        self.session_data['stock_fisico_escaneado'] = {}
        self.session_data['excel_data'] = []
        for i in self.tree_consumo.get_children(): self.tree_consumo.delete(i)
        for i in self.tree_fisico.get_children(): self.tree_fisico.delete(i)
        self.btn_procesar.config(state='normal', text='⚙️ Procesar')

    def on_movil_select(self, event):
        movil = self.movil_combo.get()
        if not movil: return
        self.session_data['movil'] = movil
        self.reset_session()
        # Mostrar nombre del técnico
        tecnico = getattr(self, '_movil_tecnico_map', {}).get(movil, '')
        if tecnico:
            self.lbl_tecnico.config(text=f"👤 {tecnico}")
        else:
            self.lbl_tecnico.config(text="👤 Sin técnico asignado")
        mostrar_cargando_async(self.ventana, lambda: self._fetch_mobile_data(movil), self._on_data_loaded)

    def _fetch_mobile_data(self, movil):
        asignados = obtener_asignacion_movil_con_paquetes(movil)
        stock_actual = {}
        for item in asignados:
             if len(item) >= 8:
                 # breakdown: (total, paq_a, paq_b, carro, sin_paquete, personalizado)
                 stock_actual[item[1]] = {
                     'name': item[0], 
                     'total': item[2],
                     'PAQUETE A': item[3],
                     'PAQUETE B': item[4],
                     'CARRO': item[5],
                     'NINGUNO': item[6],
                     'PERSONALIZADO': item[7]
                 }
        
        pendientes = obtener_consumos_pendientes()
        # consumo_reportado[sku][paquete] = total
        consumo_reportado = {}
        
        # Mapping para robustez si cambian los índices en database.py
        # c.id(0), c.movil(1), c.sku(2), p.nombre(3), c.cantidad(4), c.tecnico_nombre(5), 
        # c.ticket(6), c.fecha(7), c.colilla(8), c.num_contrato(9), c.ayudante_nombre(10), 
        # c.seriales_usados(11), c.paquete(12)
        IDX_MOVIL = 1
        IDX_SKU = 2
        IDX_QTY = 4
        IDX_PAQUETE = 12
        
        for p in pendientes:
            p_movil = str(p[IDX_MOVIL]).strip().upper()
            if p_movil == movil.strip().upper():
                sku = p[IDX_SKU]
                qty = int(p[IDX_QTY])
                paq_p = p[IDX_PAQUETE] if (len(p) > IDX_PAQUETE and p[IDX_PAQUETE]) else 'NINGUNO'
                
                if sku not in consumo_reportado: consumo_reportado[sku] = {}
                consumo_reportado[sku][paq_p] = consumo_reportado[sku].get(paq_p, 0) + qty
        return {'stock': stock_actual, 'consumo': consumo_reportado}

    def _on_data_loaded(self, data):
        self.session_data['stock_teorico'] = data['stock']
        self.session_data['consumo_app'] = data['consumo']
        self.update_consumo_ui()
        self.update_fisico_ui()

    def update_consumo_ui(self):
        for i in self.tree_consumo.get_children(): self.tree_consumo.delete(i)
        
        paquete_filtro = self.paquete_combo.get()
        from config import MATERIALES_COMPARTIDOS, PAQUETES_MATERIALES
        
        # Mapeo global de nombres para items extra
        if not hasattr(self, '_prod_name_map'):
            try:
                from database import obtener_todos_los_skus_para_movimiento
                self._prod_name_map = {p[1]: p[0] for p in obtener_todos_los_skus_para_movimiento()}
            except:
                self._prod_name_map = {}

        # Obtener SKUs del paquete seleccionado
        skus_paquete = []
        if paquete_filtro != "TODOS":
            skus_paquete = [sku for sku, cant in PAQUETES_MATERIALES.get(paquete_filtro, [])]
        
        # Incluimos TODOS los SKUs que tengan algún dato: App, Excel O Stock Asignado
        all_skus = (set(self.session_data['consumo_app'].keys()) | 
                    set([x['sku'] for x in self.session_data['excel_data']]) |
                    set(self.session_data['stock_teorico'].keys()))
        
        for sku in sorted(all_skus):
            # Filtrado por paquete
            is_shared = sku in MATERIALES_COMPARTIDOS
            is_in_package = sku in skus_paquete
            
            if paquete_filtro != "TODOS" and not is_shared and not is_in_package:
                continue

            name = "Desconocido"
            info = self.session_data['stock_teorico'].get(sku)
            if info:
                name = info['name']
            else:
                name = self._prod_name_map.get(sku, "Material Extra (No Asignado)")
            
            # Sumar consumo: Paquete Específico + Consumos sin paquete (viniendo de Render)
            prod_consumo_data = self.session_data['consumo_app'].get(sku, {})
            qty_app_total = sum(prod_consumo_data.values()) # Total móvil
            
            if paquete_filtro == "TODOS" or is_shared:
                qty_app = qty_app_total
            else:
                # Si filtramos por un paquete, sumamos el de ese paquete + lo que no tiene etiqueta (App Render)
                qty_app = prod_consumo_data.get(paquete_filtro, 0) + \
                          prod_consumo_data.get('NINGUNO', 0) + \
                          prod_consumo_data.get('SIN_PAQUETE', 0)
            
            qty_excel_total = 0
            for item in self.session_data['excel_data']:
                if item['sku'] == sku: qty_excel_total += item['qty']
            
            qty_excel = qty_excel_total
            
            # Almacenar el total verificado para la auditoría física. 
            # IMPORTANTE: Usamos el Máximo entre lo que dice la App y lo que dice Excel.
            self.session_data['consumo_verificado'][sku] = max(qty_app, qty_excel)

            # --- NUEVA LÓGICA DE VISIBILIDAD ESTRICTA PERO SEGURA ---
            if paquete_filtro != "TODOS":
                # REGLA 1: Solo mostrar si pertenece al paquete seleccionado O tiene stock personalizado O hay movimiento
                # Rule 1: Skip if not in package, not personalized, and NO MOVEMENT
                # (Shared materials should only show if they have movement or belong to the package context)
                has_perso = (info.get("PERSONALIZADO", 0) if info else 0) > 0
                has_movimiento = (qty_app > 0 or qty_excel > 0)
                
                if not is_in_package and not has_perso:
                    if not is_shared or not has_movimiento:
                        continue
                
                # Rule 2: Hide if no movement AND no assigned stock in this view
                if qty_app == 0 and qty_excel == 0:
                    stock_en_p = info.get(paquete_filtro, 0) if info else 0
                    if stock_en_p == 0 and not has_perso:
                         if not is_shared:
                             continue
                         else:
                             # Shared materials: only show if they have movement (covered by Rule 1 mostly)
                             continue

            diff = qty_excel - qty_app
            status = "Correcto" if diff == 0 else f"Dif: {diff}"
            tag = 'ok' if diff == 0 else 'error'
            
            self.tree_consumo.insert('', 'end', values=(name, qty_app, qty_excel, status), tags=(tag,))

        self.update_fisico_ui()

    def update_fisico_ui(self):
        for i in self.tree_fisico.get_children(): self.tree_fisico.delete(i)
        all_skus = set(self.session_data['stock_teorico'].keys()) | set(self.session_data['stock_fisico_escaneado'].keys())
        
        paquete_filtro = self.paquete_combo.get() # "TODOS", "PAQUETE A", etc.
        from config import MATERIALES_COMPARTIDOS, PAQUETES_MATERIALES

        # Mapeo global de nombres para items extra
        if not hasattr(self, '_prod_name_map'):
            try:
                self._prod_name_map = {p[1]: p[0] for p in obtener_todos_los_skus_para_movimiento()}
            except:
                self._prod_name_map = {}

        # Determinar SKUs que pertenecen al paquete actual
        skus_paquete = []
        if paquete_filtro != "TODOS":
            skus_paquete = [sku for sku, cant in PAQUETES_MATERIALES.get(paquete_filtro, [])]

        for sku in sorted(all_skus):
            info = self.session_data['stock_teorico'].get(sku)
            is_shared = sku in MATERIALES_COMPARTIDOS
            is_in_package = sku in skus_paquete

            # RETORNO: Nunca mostrar materiales compartidos (fibra, UTP, etc.)
            # Estos se manejan por separado y no se cuentan físicamente en retorno.
            if is_shared:
                continue

            if info:
                name = info['name']
            else:
                name = self._prod_name_map.get(sku, "Material Extra (No Asignado)")
            
            # --- LÓGICA DE CÁLCULO DE EXPECTED (CORREGIDA) ---
            # 1. Obtener Stock Bruto (Base)
            if paquete_filtro == "TODOS":
                gross = info.get('total', 0) if info else 0
            else:
                # Paquete específico: Sumamos lo del paquete + Personalizado + NINGUNO (Puente)
                # El stock 'NINGUNO' es stock base que no tiene etiqueta pero reside en el móvil.
                gross = (info.get(paquete_filtro, 0) if info else 0) + \
                        (info.get("PERSONALIZADO", 0) if info else 0) + \
                        (info.get("NINGUNO", 0) if info else 0)
            
            # ELIMINADO: Ya no restamos consumos_pendientes (consumed_total) porque la tabla 
            # asignacion_moviles ya se descuenta cuando el técnico reporta en la App.
            expected = gross

            # Si es equipo, intentar poner la MAC en el nombre para facilitar identificación
            display_name = name
            if sku in PRODUCTOS_CON_CODIGO_BARRA:
                series_data = obtener_series_por_sku_y_ubicacion(sku, self.session_data.get('movil'), self.paquete_combo.get())
                if series_data:
                    # series_data es [(serial, mac), ...] - extraemos el mejor id para mostrar
                    ids_to_show = []
                    for s, m in series_data:
                        best_id = m if m and str(m).strip() not in ['', 'N/A', 'None'] else s
                        ids_to_show.append(str(best_id))
                    
                    macs_str = ", ".join(ids_to_show[:2])
                    if len(ids_to_show) > 2: macs_str += "..."
                    display_name = f"{name} ({macs_str})"

            scanned = self.session_data['stock_fisico_escaneado'].get(sku, 0)
            
            # Lógica de filtrado de visualización (FILTRA RELEVANCIA)
            if paquete_filtro != "TODOS":
                # REGLA 1: Solo mostrar si pertenece al paquete seleccionado O tiene stock personalizado O NINGUNO
                has_base_stock = ((info.get(paquete_filtro, 0) if info else 0) > 0 or 
                                (info.get("PERSONALIZADO", 0) if info else 0) > 0 or
                                (info.get("NINGUNO", 0) if info else 0) > 0)
                
                # Si no es del paquete ni tiene stock base, ocultar si no hay escaneo
                if not is_in_package and not has_base_stock:
                    if scanned == 0:
                        continue

                # REGLA 2: Ocultar si no se espera nada y no se escaneó nada
                if expected == 0 and scanned == 0:
                    if not is_in_package:
                        continue

            if scanned == expected:
                state = "✅ OK"; tag = 'found'
            elif scanned < expected:
                state = f"❌ Faltan {expected - scanned}"; tag = 'missing'
            else:
                state = f"⚠️ Sobran {scanned - expected}"; tag = 'extra'
            
            self.tree_fisico.insert('', 'end', values=(sku, display_name, expected, scanned, state), tags=(tag,))
        
        if self.session_data['stock_fisico_escaneado']: 
            self.btn_procesar.config(state='normal')
            # Verificar si hay faltantes para habilitar el botón de auto-relleno
            faltantes_count = 0
            for i in self.tree_fisico.get_children():
                v = self.tree_fisico.item(i, 'values')
                try:
                    exp_c = int(v[2]); sca_c = int(v[3])
                    if sca_c < exp_c:
                        faltantes_count += (exp_c - sca_c)
                except: pass
            
            if faltantes_count > 0:
                self.btn_autorelleno.config(state='normal', 
                    text=f"🚀 Auto-Rellenar Faltantes ({faltantes_count} items)")
                self.lbl_faltantes_count.config(text=f"⚠️ {faltantes_count} items faltan")
            else:
                self.btn_autorelleno.config(state='disabled', text="🚀 Auto-Rellenar Faltantes")
                self.lbl_faltantes_count.config(text="✅ Sin faltantes")

    def mostrar_detalle_mac(self, event):
        """Muestra una ventana pequeña con las MACs registradas para el SKU seleccionado"""
        item = self.tree_fisico.identify_row(event.y)
        if not item: return
        
        values = self.tree_fisico.item(item, 'values')
        if not values: return
        
        sku = values[0]
        nombre = values[1]
        movil = self.session_data.get('movil')
        
        if not movil or movil == "--- Seleccionar Móvil ---":
            mostrar_mensaje_emergente(self.ventana, "Error", "Debe seleccionar un móvil primero.", "error")
            return
            
        # Obtener series
        series = obtener_series_por_sku_y_ubicacion(sku, movil, self.paquete_combo.get())
        
        # Crear popup
        popup = tk.Toplevel(self.ventana)
        popup.title(f"MACs: {nombre}")
        popup.geometry("400x450")
        popup.configure(bg='white')
        popup.transient(self.ventana)
        popup.grab_set()
        
        # Centrar relativo a la ventana principal
        x = self.ventana.winfo_rootx() + (self.ventana.winfo_width() // 2) - 200
        y = self.ventana.winfo_rooty() + (self.ventana.winfo_height() // 2) - 225
        popup.geometry(f"+{x}+{y}")
        
        header = tk.Frame(popup, bg=Styles.PRIMARY_COLOR, height=50)
        header.pack(fill='x')
        tk.Label(header, text="📡 SERIALES (MAC) REGISTRADOS", font=('Segoe UI', 10, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=12)
        
        info_frame = tk.Frame(popup, bg='#f8f9fa', pady=10)
        info_frame.pack(fill='x')
        tk.Label(info_frame, text=f"Móvil: {movil}", font=('Segoe UI', 9, 'bold'), bg='#f8f9fa').pack()
        tk.Label(info_frame, text=f"Producto: {nombre}", font=('Segoe UI', 9), bg='#f8f9fa').pack()
        tk.Label(info_frame, text=f"Total: {len(series)} equipos", font=('Segoe UI', 9, 'bold'), fg=Styles.SUCCESS_COLOR, bg='#f8f9fa').pack()
        
        # Lista con scroll
        list_frame = tk.Frame(popup, bg='white', pady=10)
        list_frame.pack(fill='both', expand=True, padx=20)
        
        listbox = tk.Listbox(list_frame, font=('Consolas', 10), relief='flat', highlightthickness=1, borderwidth=1)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        if not series:
            listbox.insert(tk.END, " No hay MACs registradas")
            listbox.insert(tk.END, " para este ítem en el móvil.")
            listbox.config(fg='gray')
        else:
            for s in sorted(series):
                listbox.insert(tk.END, f"  • {s}")
        
        tk.Button(popup, text="Cerrar", command=popup.destroy, bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'), pady=8).pack(fill='x', padx=20, pady=15)

    def load_excel_activations(self):
        filename = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")], parent=self.ventana)
        if not filename: return
        try:
            df = pd.read_excel(filename)
            map_sku = {}
            for n, s, _ in PRODUCTOS_INICIALES:
                key = str(n).upper().strip().replace(' ', '').replace('_', '')
                map_sku[key] = s
            found_data = []
            for col in df.columns:
                col_u = str(col).upper().strip().replace(' ', '').replace('_', '')
                sku_target = map_sku.get(col_u)
                if not sku_target:
                     for k, s in map_sku.items():
                         if k in col_u or col_u in k:
                             sku_target = s
                             break
                if sku_target:
                    try:
                        qty_col = pd.to_numeric(df[col], errors='coerce').fillna(0).sum()
                        if qty_col > 0: found_data.append({'sku': sku_target, 'qty': int(qty_col)})
                    except: pass
            
            self.session_data['excel_data'] = found_data
            self.update_consumo_ui()
            messagebox.showinfo("Carga Excel", f"Se detectaron {len(found_data)} productos con consumo en el Excel.", parent=self.ventana)
        except Exception as e:
            messagebox.showerror("Error Excel", f"Fallo al leer Excel: {e}", parent=self.ventana)

    def on_scan(self, event):
        code = self.entry_scan.get().strip().upper()
        if not code: return
        self.entry_scan.delete(0, tk.END)
        
        movil = self.session_data.get('movil')
        if not movil:
            messagebox.showerror("Error", "Debe seleccionar un móvil primero", parent=self.ventana)
            return
            
        # Pipeline de Identificación: Serial -> Barcode -> SKU
        sku_found = None
        is_serial = False
        
        # 1. Intentar como Serial (Equipo)
        sku_serial, ubicacion = obtener_info_serial(code)
        if sku_serial:
            if ubicacion != movil:
                # El usuario quiere poder retornar cosas aunque la BD diga que están en otro lado.
                # Permitimos la captura pero con un color de advertencia (amarillo/naranja).
                logger.warning(f"⚠️ Serial '{code}' registrado en {ubicacion}, pero se está retornando desde {movil}")
                self.entry_scan.config(bg='#ffeeba') # Color aviso
            
            sku_found = sku_serial
            is_serial = True
            
            key_serials = f"_seriales_{sku_found}"
            if key_serials not in self.session_data: self.session_data[key_serials] = []
            if code in self.session_data[key_serials]:
                 messagebox.showwarning("Duplicado",
                                        f"El serial / MAC '{code}' ya fue escaneado en esta sesión.\nNo se puede agregar dos veces.",
                                        parent=self.ventana)
                 self.entry_scan.config(bg='#fff3cd')
                 self.ventana.after(1000, lambda: self.entry_scan.config(bg='#e8f0fe'))
                 return
            self.session_data[key_serials].append(code)

        # 2. Intentar como Barcode (Material)
        if not sku_found:
            mapped_sku = obtener_sku_por_codigo_barra(code)
            if mapped_sku:
                sku_found = mapped_sku

        # 3. Intentar como SKU Directo (Incluso si no está en stock_teorico)
        if not sku_found:
             # Si el código es un SKU válido en el sistema (aunque no esté asignado al móvil)
             if not hasattr(self, '_prod_name_map'):
                 try: self._prod_name_map = {p[1]: p[0] for p in obtener_todos_los_skus_para_movimiento()}
                 except: self._prod_name_map = {}
             
             if code in self._prod_name_map:
                 sku_found = code

        # Procesar Hallazgo
        if sku_found:
            es_danado = getattr(self, 'var_danado', None) and self.var_danado.get()
            
            # Si es material (no serial), pedir cantidad
            qty_scanned = 1
            if not is_serial:
                from tkinter import simpledialog
                nombre_p = self._prod_name_map.get(sku_found, "Material")
                qty = simpledialog.askinteger("Cantidad Real", f"Producto: {nombre_p}\nSKU: {sku_found}\n\n¿Qué cantidad física está contando?", 
                                               parent=self.ventana, minvalue=0)
                if qty is None: return
                qty_scanned = qty
            
            # Registrar según su estado (Bueno o Dañado)
            if es_danado:
                self.session_data['stock_danado'][sku_found] = self.session_data['stock_danado'].get(sku_found, 0) + qty_scanned
                if is_serial:
                    if sku_found not in self.session_data['seriales_danados']:
                        self.session_data['seriales_danados'][sku_found] = []
                    self.session_data['seriales_danados'][sku_found].append(code)
                    
                    # Remover el serial de los 'buenos' para que NO se mande al Salida a Móvil
                    key_serials = f"_seriales_{sku_found}"
                    if key_serials in self.session_data and code in self.session_data[key_serials]:
                        self.session_data[key_serials].remove(code)
                
                # Alerta visual roja
                self.entry_scan.config(bg='#f8d7da')
                self.var_danado.set(False) # Resetear checkbox para el próximo scan
                logger.info(f"⚠️ Dañado registrado: {sku_found} -> Qty: {qty_scanned}")
                messagebox.showinfo("Dañado", f"Se registró {qty_scanned} ud(s) de '{sku_found}' como DAÑADO.", parent=self.ventana)
            else:
                # Actualizar contador físico normal
                if is_serial:
                    self.session_data['stock_fisico_escaneado'][sku_found] = self.session_data['stock_fisico_escaneado'].get(sku_found, 0) + 1
                else:
                    self.session_data['stock_fisico_escaneado'][sku_found] = qty_scanned
                
                self.entry_scan.config(bg='#d4edda')
                logger.info(f"✅ Auditado: {sku_found} -> Qty: {qty_scanned} ({'Serial' if is_serial else 'Material'})")
            
            self.ventana.after(500, lambda: self.entry_scan.config(bg='#e8f0fe'))
            self.update_fisico_ui()
        else:
            # No se encontró — mostrar error claro
            self.entry_scan.config(bg='#e74c3c')
            self.ventana.after(1200, lambda: self.entry_scan.config(bg='#e8f0fe'))
            messagebox.showerror("MAC / Código no reconocido",
                                 f"'{code}' no se encontró en el sistema o no pertenece a este móvil.\n\nVerifique el código e intente de nuevo.",
                                 parent=self.ventana)
            logger.warning(f"❌ Código '{code}' no reconocido en este móvil")

    def finalizar(self):
        if not messagebox.askyesno("Confirmar Cierre", "Se procesará el retorno y consumo. ¿Continuar?", parent=self.ventana): return
        self.btn_procesar.config(state='disabled', text="⏳ Procesando...")
        
        # Iniciar thread
        threading.Thread(target=self._procesar_async, daemon=True).start()

    def _procesar_async(self):
        # UI Feedback inmediato
        try:
            self.btn_procesar.config(state='disabled', text="⌛ Procesando Transacción...")
        except: pass

        faltantes_relleno = []
        paquete_objetivo = self.paquete_combo.get()
        exitos_consumo = 0
        exitos_retorno = 0
        errors = []
        reutilizar_items = []
        conn = None
        
        # 0. Verificar discrepancias antes de empezar
        faltantes_msg = ""
        sobrantes_msg = ""
        
        for i in self.tree_fisico.get_children():
            v = self.tree_fisico.item(i, 'values')
            sku_c, nom_c, exp_c, sca_c, st_c = v
            exp_c = int(exp_c); sca_c = int(sca_c)
            
            if sca_c < exp_c:
                faltantes_msg += f"\n- {nom_c}: Faltan {exp_c - sca_c}"
                faltantes_relleno.append({
                    'sku': sku_c,
                    'nombre': nom_c,
                    'cantidad': exp_c - sca_c,
                    'seriales': []
                })
            elif sca_c > exp_c:
                sobrantes_msg += f"\n- {nom_c}: Sobran {sca_c - exp_c}"
        
        discrepancias_msg = ""
        if faltantes_msg: discrepancias_msg += "\n⚠️ FALTANTES:" + faltantes_msg
        if sobrantes_msg: discrepancias_msg += "\n\n✅ SOBRANTES:" + sobrantes_msg
        
        # Agregar sumario de dañados a discrepancias_msg
        danados_msg = ""
        for sku_d, qty_d in self.session_data.get('stock_danado', {}).items():
             if qty_d > 0:
                  n_d = self._prod_name_map.get(sku_d, sku_d)
                  danados_msg += f"\n- {n_d}: {qty_d} Dañados"
        if danados_msg: discrepancias_msg += "\n\n♻️ DAÑADOS REPORTADOS:" + danados_msg
            
        movil = self.session_data['movil']
            
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            fecha_evento = self.entry_fecha.get()
            
            # --- NUEVA LÓGICA DE LIMPIEZA Y REINICIO ---
            from database import resetear_stock_movil, registrar_movimiento_gui, run_query, registrar_danado_directo
            
            # 0.5. Procesar equipos/materiales DAÑADOS escaneados durante el Retorno
            for sku_d, qty_d in self.session_data.get('stock_danado', {}).items():
                if qty_d > 0:
                    seriales_d = self.session_data.get('seriales_danados', {}).get(sku_d, [])
                    ok_d, msg_d = registrar_danado_directo(
                        sku=sku_d, 
                        cantidad=qty_d, 
                        tecnico=movil, 
                        seriales=seriales_d if seriales_d else None,
                        observaciones="Reporte de Dañado durante Auditoría/Retorno",
                        paquete=paquete_objetivo
                    )
                    if not ok_d:
                        errors.append(f"Dañado {sku_d}: {msg_d}")
                        logger.error(f"Fallo al registrar dañado {sku_d}: {msg_d}")

            # 1. Procesar CONSUMOS reales (Excel) primero para que se descuenten del stock asignado
            for sku, qty in self.session_data['consumo_verificado'].items():
                if qty > 0:
                    ok, msg = registrar_movimiento_gui(sku, 'CONSUMO_MOVIL', qty, movil, fecha_evento, paquete_objetivo, "Auditoría Automática (Excel)", existing_conn=conn)
                    if ok: exitos_consumo += 1
                    else: errors.append(f"Consumo {sku}: {msg}")
            
            # 2. Retornar formalmente a Bodega todo lo que QUEDA físicamente (stock teórico restante) 
            # para que 'productos' recupere su stock general y el móvil quede en cero matemáticamente.
            if paquete_objetivo == "TODOS":
                run_query(cursor, "SELECT sku_producto, SUM(cantidad) FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = UPPER(TRIM(?)) GROUP BY sku_producto", (movil,))
            else:
                run_query(cursor, "SELECT sku_producto, SUM(cantidad) FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = UPPER(TRIM(?)) AND COALESCE(paquete, 'NINGUNO') = ? GROUP BY sku_producto", (movil, paquete_objetivo))
            
            remanentes = cursor.fetchall()
            for r in remanentes:
                sku_r = r[0]
                qty_r = float(r[1])
                if qty_r > 0:
                    ok, msg = registrar_movimiento_gui(sku_r, 'RETORNO_MOVIL', qty_r, movil, fecha_evento, paquete_objetivo, "Auditoría Automática (Retorno a Bodega)", existing_conn=conn)
                    if not ok: errors.append(f"Retorno Auto {sku_r}: {msg}")

            # 3. Limpiar cualquier basura residual (seriales no retornados correctamente, asignaciones en 0, etc)
            # Esto vacía la tabla asignacion_moviles y desvincula las series de la móvil en la BD.
            # Como le pasamos una nueva conexión por dentro (no usa existing_conn), hacemos commit de nuestra transacción primero.
            conn.commit()
            
            ok_reset, msg_reset = resetear_stock_movil(movil, paquete_objetivo)
            if not ok_reset:
                logger.error(f"Fallo al limpiar stock previo de {movil} ({paquete_objetivo}): {msg_reset}")
                errors.append(f"Limpieza Residual: {msg_reset}")
            
            # 4. Calcular el éxito del retorno FÍSICO (lo que escaneó el usuario con la pistola = success del trabajo)
            from config import PRODUCTOS_CON_CODIGO_BARRA, MATERIALES_COMPARTIDOS
            
            for i in self.tree_fisico.get_children():
                v = self.tree_fisico.item(i, 'values')
                sku_c = v[0]
                sca_c = int(v[3]) # Cantidad Física Escaneada
                
                # Materiales compartidos no se tocan en el flujo de retorno regular
                if sku_c in MATERIALES_COMPARTIDOS: continue
                    
                if sca_c > 0:
                    exitos_retorno += sca_c # Lo contamos como "físicamente verificado" / retornado

            conn.commit()
        except Exception as e:
            logger.error(f"Error en _procesar_async de retorno: {e}")
            if conn: conn.rollback()
            errors.append(str(e))
        finally:
            if conn: conn.close()
        
        # 5. Resultado final
        summary = f"Auditoría Finalizada.\n\nConsumos Registrados: {exitos_consumo}\nEquipos Físicos Verificados: {exitos_retorno}"
        if errors: summary += "\n\nErrores:\n" + "\n".join(errors[:5])
        
        def final_ui_feedback():
            # Restaurar botón
            self.btn_procesar.config(state='normal', text="⚙️ Procesar")
            
            # Si hubo errores técnicos, avisar primero
            if errors:
                messagebox.showwarning("Proceso con Errores", summary, parent=self.ventana)
            
            try:
                # --- LÓGICA DE RELLENO (REFILL) BASADO EN PAQUETES ESTÁNDAR Y ASIGNACIONES ---
                from config import PAQUETES_MATERIALES, MATERIALES_COMPARTIDOS
                
                paquete_nombre = self.paquete_combo.get()
                if paquete_nombre == "TODOS":
                    paquete_nombre = "PAQUETE A" # Default de comparación
                
                objetivo_paquete = PAQUETES_MATERIALES.get(paquete_nombre, [])
                skus_paquete = [s for s, c in objetivo_paquete]
                
                faltantes_para_rellenar = []
                lineas_resumen = []

                # Evaluar todos los SKUs conocidos (los del paquete y los que tiene el móvil)
                skus_a_evaluar = set(skus_paquete) | set(self.session_data.get('stock_teorico', {}).keys())
                
                for sku_p in skus_a_evaluar:
                    info = self.session_data.get('stock_teorico', {}).get(sku_p, {})
                    if not isinstance(info, dict):
                         info = {}
                    scanned_qty = self.session_data.get('stock_fisico_escaneado', {}).get(sku_p, 0)
                    if scanned_qty is None: scanned_qty = 0
                    
                    is_shared = sku_p in MATERIALES_COMPARTIDOS
                    is_custom = info.get("PERSONALIZADO", 0) if isinstance(info.get("PERSONALIZADO"), (int, float)) else 0
                    is_custom = is_custom > 0
                    
                    # REQUERIMIENTO: No auto-rellenar materiales compartidos porque se quedan en la móvil permanentemente
                    if is_shared:
                        continue
                    
                    cant_ideal = 0
                    if paquete_nombre == "TODOS":
                        cant_ideal = info.get('total', 0) if isinstance(info.get('total'), (int, float)) else 0
                    else:
                        if sku_p in skus_paquete:
                            # Lo que manda la receta del paquete
                            cant_ideal = next((c for s, c in objetivo_paquete if s == sku_p), 0)
                            # Sumar personalizado adicional si tiene
                            perso_val = info.get("PERSONALIZADO", 0) if isinstance(info.get("PERSONALIZADO"), (int, float)) else 0
                            cant_ideal += perso_val
                        elif is_custom:
                            cant_ideal = info.get("PERSONALIZADO", 0) if isinstance(info.get("PERSONALIZADO"), (int, float)) else 0
                    
                    # Para mantener el móvil limpio, siempre requerimos despachar la cant_ideal (toda)
                    if cant_ideal > 0:
                        nombre_p = self._prod_name_map.get(sku_p, sku_p)
                        
                        seriales_a_reponer = []
                        is_equipo = sku_p in PRODUCTOS_CON_CODIGO_BARRA
                        if is_equipo:
                            seriales_escaneados = self.session_data.get(f'_seriales_{sku_p}', [])
                            seriales_a_reponer = seriales_escaneados[:cant_ideal]
                            
                            # Si es equipo pero NO se escaneó nada en el retorno, NO auto-rellenar
                            # para obligar a que se escanee con MAC real en la ventana de Salida.
                            if not seriales_a_reponer:
                                logger.info(f"Refill: Saltando equipo {sku_p} por falta de MACs escaneadas.")
                                continue
                            
                            cant_a_rellenar = len(seriales_a_reponer)
                        else:
                            cant_a_rellenar = cant_ideal

                        faltantes_para_rellenar.append({
                            'sku': sku_p, 
                            'nombre': nombre_p, 
                            'cantidad': cant_a_rellenar, 
                            'seriales': seriales_a_reponer
                        })
                        
                        tag_extra = f" (con {len(seriales_a_reponer)} MACs)" if is_equipo else ""
                        lineas_resumen.append(f"  • {nombre_p[:30]}: recargar {cant_a_rellenar}{tag_extra}")

                resumen_msg = "📊 AUDITORÍA Y RETORNO FINALIZADOS\n\nEl móvil ha sido vaciado temporalmente en el sistema.\n\n"
                
                # Mostrar primero las discrepancias físicas (pérdidas reales vs consumos esperados)
                hay_discrepancias = bool(discrepancias_msg.strip())
                if hay_discrepancias:
                    resumen_msg += "📌 RESULTADO FÍSICO (Pérdidas y Sobrantes del Retorno):" + discrepancias_msg + "\n\n"
                    
                if faltantes_para_rellenar:
                    resumen_msg += f"📦 RECARGA OBLIGATORIA (Salida a Móvil):\n"
                    resumen_msg += "\n".join(lineas_resumen[:12])
                    if len(lineas_resumen) > 12:
                        resumen_msg += f"\n... y {len(lineas_resumen)-12} más."
                    
                    resumen_msg += f"\n\n¿Deseas abrir la ventana de SALIDA ahora para realizar la recarga oficial de {paquete_nombre}?"
                    
                    if messagebox.askyesno("Confirmar Salida", resumen_msg, parent=self.ventana):
                        # FIX: Abrir el Scanner ANTES de destruir la ventana de Retorno
                        from ..mobile_output_scanner import MobileOutputScannerWindow
                        MobileOutputScannerWindow(
                            self.master_app, mode='SALIDA_MOVIL',
                            prefill_items=faltantes_para_rellenar,
                            initial_movil=movil,
                            initial_package=paquete_nombre
                        )
                        if self.ventana.winfo_exists():
                            self.ventana.destroy()
                        return
                    else:
                        messagebox.showinfo("Auditoría Finalizada", "Operación finalizada. El móvil ha quedado sin la asignación del paquete en el sistema.", parent=self.ventana)
                else:
                    messagebox.showinfo("Auditoría Finalizada", resumen_msg + "No hay recargas requeridas.", parent=self.ventana)

            except Exception as e:
                logger.error(f"Error parseando feedback final de retorno: {e}")
                # Mostrar error para no crashear en silencio
                messagebox.showinfo("Auditoría Finalizada (Con alerta UI)", 
                                  f"El retorno se guardó correctamente, pero ocurrió un error gráfico:\n{e}", 
                                  parent=self.ventana)
                                  
            if self.on_close_callback: self.on_close_callback()
            if self.ventana.winfo_exists():
                self.ventana.destroy()

        # Enviar feedback a UI thread
        self.ventana.after(0, final_ui_feedback)

    def auto_rellenar(self):
        """Abre la ventana de Salida pre-rellena con los items faltantes detectados en la auditoría,
        SIN necesidad de finalizar primero."""
        movil = self.session_data.get('movil')
        paquete_objetivo = self.paquete_combo.get() if hasattr(self, 'paquete_combo') else 'PAQUETE A'
        
        if not movil:
            from tkinter import messagebox
            messagebox.showerror("Error", "Debe seleccionar un móvil primero.", parent=self.ventana)
            return
        
        from config import PRODUCTOS_CON_CODIGO_BARRA, MATERIALES_COMPARTIDOS
        
        # Recopilar faltantes desde la tabla de auditoría física
        faltantes_relleno = []
        equipos_faltantes = []  # Equipment with missing units (requiring new scans)
        
        for i in self.tree_fisico.get_children():
            v = self.tree_fisico.item(i, 'values')
            sku_c, nom_c = v[0], v[1]
            try:
                exp_c = int(v[2]); sca_c = int(v[3])
                if sca_c >= exp_c: continue # No hay faltantes
                
                # Omitir compartidos de la recarga rápida
                if sku_c in MATERIALES_COMPARTIDOS: continue
                
                cant_falta = exp_c - sca_c
                
                if sku_c not in PRODUCTOS_CON_CODIGO_BARRA:
                    # Es un material regular
                    faltantes_relleno.append({
                        'sku': sku_c,
                        'nombre': nom_c,
                        'cantidad': cant_falta,
                        'seriales': []
                    })
                else:
                    # Es un equipo: intentar pre-cargar los seriales registrados en el móvil.
                    seriales_en_movil = []
                    try:
                        ya_escaneados = self.session_data.get(f'_seriales_{sku_c}', [])
                        todos_en_movil = obtener_series_por_sku_y_ubicacion(sku_c, movil, self.paquete_combo.get())
                        seriales_en_movil = [s for s in todos_en_movil if s not in ya_escaneados][:cant_falta]
                    except Exception as _e:
                        logger.warning(f"No se pudieron obtener seriales para {sku_c}: {_e}")
                    
                    if not seriales_en_movil:
                         logger.info(f"Auto-Refill: Omitiendo equipo {sku_c} por falta de MACs en BD para este móvil.")
                         continue

                    faltantes_relleno.append({
                        'sku': sku_c,
                        'nombre': nom_c,
                        'cantidad': len(seriales_en_movil),
                        'seriales': seriales_en_movil
                    })
                    equipos_faltantes.append(f"{nom_c}: {len(seriales_en_movil)} uds (MACs: {', '.join(seriales_en_movil[:1])}{'...' if len(seriales_en_movil)>1 else ''})")
                        
            except: pass
        
        if not faltantes_relleno and not equipos_faltantes:
            from tkinter import messagebox
            messagebox.showinfo("Sin Faltantes", "No se detectan faltantes en la auditoría actual (o solo son compartidos).", parent=self.ventana)
            return
        
        from tkinter import messagebox
        
        msg_body = ""
        materiales = [f for f in faltantes_relleno if f['sku'] not in PRODUCTOS_CON_CODIGO_BARRA]
        if materiales:
            resumen_mat = "\n".join([f"  • {f['nombre']}: faltan {f['cantidad']}" for f in materiales[:8]])
            msg_body += f"📦 Materiales a reponer:\n{resumen_mat}\n\n"
        
        if equipos_faltantes:
            resumen_ef = "\n".join([f"  • {e}" for e in equipos_faltantes[:5]])
            msg_body += f"⚠️ Equipos faltantes (Requerirá escanear nuevas MAC reales en Salida):\n{resumen_ef}\n\n"
        
        if not messagebox.askyesno("Abrir Salida para Rellenar", 
                                   f"{msg_body}"
                                   f"¿Desea abrir la ventana de Salida para completar el inventario de {movil}?",
                                   parent=self.ventana):
            return
        
        prefill_combinado = faltantes_relleno
        
        # FIX: Abrir Scanner ANTES de destruir la ventana
        from ..mobile_output_scanner import MobileOutputScannerWindow
        MobileOutputScannerWindow(self.master_app, mode='SALIDA_MOVIL',
                                  prefill_items=prefill_combinado,
                                  initial_movil=movil,
                                  initial_package=paquete_objetivo if paquete_objetivo != 'TODOS' else 'PAQUETE A')
        if self.ventana.winfo_exists():
            self.ventana.destroy()



class ConciliacionPaquetesWindow:
    def __init__(self, master_app, on_close_callback=None):
        self.master_app = master_app
        self.master = master_app.master
        self.on_close_callback = on_close_callback
        
        self.ventana = tk.Toplevel(self.master)
        self.ventana.title("⚖️ Conciliación - Con Paquetes")
        try: 
            self.ventana.state('zoomed')
        except tk.TclError: 
            self.ventana.wm_attributes('-fullscreen', True)
        self.ventana.configure(bg='#f8f9fa')
        self.ventana.grab_set()

        self.conciliacion_entries = {}
        self.moviles_db = obtener_nombres_moviles()
        
        self.construir_ui()

    def construir_ui(self):
        header_frame = tk.Frame(self.ventana, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="⚖️ CONCILIACIÓN", font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        frame_selector = tk.Frame(self.ventana, padx=20, pady=20, bg='#E1BEE7')
        frame_selector.pack(fill='x')
        
        tk.Label(frame_selector, text="Móvil:", font=('Segoe UI', 10, 'bold'), bg='#E1BEE7').pack(side=tk.LEFT)
        self.movil_combo = ttk.Combobox(frame_selector, values=self.moviles_db, state="readonly", width=15)
        self.movil_combo.set("--- Seleccionar Móvil ---")
        self.movil_combo.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_selector, text="Paquete Asignado:", font=('Segoe UI', 10, 'bold'), bg='#E1BEE7').pack(side=tk.LEFT, padx=(20, 5))
        self.paquete_combo = ttk.Combobox(frame_selector, values=["NINGUNO", "PAQUETE A", "PAQUETE B", "CARRO", "PERSONALIZADO"], state="readonly", width=15)
        self.paquete_combo.set("NINGUNO")
        self.paquete_combo.pack(side=tk.LEFT, padx=10)
        
        tk.Label(frame_selector, text="Fecha Evento (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#E1BEE7').pack(side=tk.LEFT, padx=(20, 5))
        self.fecha_entry = tk.Entry(frame_selector, width=15, font=('Segoe UI', 10))
        self.fecha_entry.insert(0, date.today().isoformat())
        self.fecha_entry.pack(side=tk.LEFT)
        
        canvas = tk.Canvas(self.ventana)
        scrollbar = ttk.Scrollbar(self.ventana, orient="vertical", command=canvas.yview)
        self.frame_productos = tk.Frame(canvas)
        canvas.create_window((0, 0), window=self.frame_productos, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        def on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass
        
        def _bind_mousewheel_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                _bind_mousewheel_recursive(child)
        
        _bind_mousewheel_recursive(canvas)
        _bind_mousewheel_recursive(self.frame_productos)
        
        self.movil_combo.bind("<<ComboboxSelected>>", self.cargar_productos_movil)
        self.paquete_combo.bind("<<ComboboxSelected>>", self.cargar_productos_movil)
        self.frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        tk.Button(self.ventana, text="Procesar Consumo", command=self.procesar_consiliacion, 
                  bg=Styles.WARNING_COLOR, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

    def cargar_productos_movil(self, event=None):
        movil = self.movil_combo.get()
        paquete_seleccionado = self.paquete_combo.get()
        if movil == "--- Seleccionar Móvil ---": return
        
        for widget in self.frame_productos.winfo_children(): widget.destroy()
        self.conciliacion_entries.clear()
        
        productos_asignados = obtener_asignacion_movil_con_paquetes(movil)
        if not productos_asignados:
             tk.Label(self.frame_productos, text="No hay productos asignados a este móvil", font=('Segoe UI', 10), fg='red').pack()
             return
             
        tk.Label(self.frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos, text="Stock Total Móvil", font=('Segoe UI', 10, 'bold'), fg='blue').grid(row=0, column=2, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos, text="Stock del Paquete", font=('Segoe UI', 10, 'bold'), fg='green').grid(row=0, column=3, padx=5, pady=5, sticky='w')
        tk.Label(self.frame_productos, text="Cant. Consumida", font=('Segoe UI', 10, 'bold')).grid(row=0, column=4, padx=5, pady=5, sticky='w')
        
        fila = 1
        for nombre, sku, total, paq_a, paq_b, carro, sin_paquete, personalizado in productos_asignados:
            kp = {'PAQUETE A': paq_a, 'PAQUETE B': paq_b, 'CARRO': carro, 'PERSONALIZADO': personalizado, 'NINGUNO': sin_paquete}
            cantidad_paquete = kp.get(paquete_seleccionado, 0)
            
            tk.Label(self.frame_productos, text=nombre, anchor='w').grid(row=fila, column=0, padx=5, pady=2, sticky='ew')
            tk.Label(self.frame_productos, text=sku, anchor='center').grid(row=fila, column=1, padx=5, pady=2, sticky='ew')
            tk.Label(self.frame_productos, text=str(total), anchor='center', fg='blue').grid(row=fila, column=2, padx=5, pady=2, sticky='ew')
            
            lbl_paq = str(cantidad_paquete) if (paquete_seleccionado == 'NINGUNO' or cantidad_paquete > 0) else "No disponible"
            col_paq = 'green' if cantidad_paquete > 0 else 'red'
            tk.Label(self.frame_productos, text=lbl_paq, anchor='center', fg=col_paq).grid(row=fila, column=3, padx=5, pady=2, sticky='ew')
            
            entry = tk.Entry(self.frame_productos, width=8)
            entry.grid(row=fila, column=4, padx=5, pady=2)
            if paquete_seleccionado != 'NINGUNO' and cantidad_paquete > 0: entry.insert(0, str(cantidad_paquete))
            self.conciliacion_entries[sku] = entry
            fila += 1

    def procesar_conciliacion(self):
        movil = self.movil_combo.get()
        fecha = self.fecha_entry.get().strip()
        paquete = self.paquete_combo.get() if self.paquete_combo.get() != 'NINGUNO' else None
        
        if movil == "--- Seleccionar Móvil ---" or not fecha:
             mostrar_mensaje_emergente(self.ventana, "Error", "Complete todos los campos.", "error")
             return

        exitos = 0; errores = 0; msg_error = ""
        for sku, entry in self.conciliacion_entries.items():
            try:
                val = entry.get().strip()
                if val and int(val) > 0:
                    ok, msg = registrar_movimiento_gui(sku, 'CONSUMO_MOVIL', int(val), movil, fecha, paquete)
                    if ok: exitos += 1
                    else: errores += 1; msg_error += f"\n{sku}: {msg}"
            except: pass
        
        if exitos > 0: mostrar_mensaje_emergente(self.master, "Éxito", f"Se procesaron {exitos} consumos.", "success")
        if errores > 0: mostrar_mensaje_emergente(self.ventana, "Errores", msg_error, "warning")
        
        if exitos > 0:
            if self.on_close_callback: self.on_close_callback()
            self.ventana.destroy()


