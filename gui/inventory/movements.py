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
    obtener_series_por_sku_y_ubicacion
)
from config import TIPO_MOVIMIENTO_DESCARTE, PRODUCTOS_INICIALES, DATABASE_NAME

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
        canvas = tk.Canvas(self.ventana)
        scrollbar = ttk.Scrollbar(self.ventana, orient="vertical", command=canvas.yview)
        frame_productos = tk.Frame(canvas)
        canvas.create_window((0, 0), window=frame_productos, anchor="nw")
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
        _bind_mousewheel_recursive(frame_productos)
        
        self.entry_vars = {} 
        
        # Encabezados
        tk.Label(frame_productos, text="Producto", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        tk.Label(frame_productos, text="SKU", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        tk.Label(frame_productos, text="Stock Bodega", font=('Segoe UI', 10, 'bold'), fg='red').grid(row=0, column=2, padx=5, pady=5, sticky='w')
        tk.Label(frame_productos, text="Cant. a Procesar", font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, padx=5, pady=5, sticky='w')
        
        fila = 1
        for nombre, sku, stock_actual in productos:
            tk.Label(frame_productos, text=nombre, anchor='w', justify='left', font=('Segoe UI', 9), wraplength=300).grid(row=fila, column=0, padx=5, pady=2, sticky='w')
            tk.Label(frame_productos, text=sku, anchor='center', font=('Segoe UI', 9)).grid(row=fila, column=1, padx=5, pady=2, sticky='w')
            tk.Label(frame_productos, text=str(stock_actual), anchor='center', font=('Segoe UI', 9), fg='red').grid(row=fila, column=2, padx=5, pady=2, sticky='w')
            entry = tk.Entry(frame_productos, width=10, font=('Segoe UI', 9))
            entry.grid(row=fila, column=3, padx=5, pady=2)
            self.entry_vars[sku] = entry
            fila += 1
            
        frame_productos.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Scanner logic
        self.PRODUCTOS_CON_CODIGO_BARRA = [p[1] for p in productos]
        self.productos_cache = productos

        self.scan_entry.bind('<Return>', self.real_scan_handler)
        self.scan_entry.focus_set()
        
        tk.Button(self.ventana, text=btn_text, 
                command=self.procesar_salida_individual, 
                bg=header_color, fg='white', font=('Segoe UI', 12, 'bold')).pack(pady=10)

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
        tipo_mov = TIPO_MOVIMIENTO_DESCARTE if is_descarte else 'SALIDA'
        prefix_obs = "DESCARTE" if is_descarte else "SALIDA INDIVIDUAL"

        for sku, entry in self.entry_vars.items():
            try:
                cantidad_text = entry.get().strip()
                if cantidad_text:
                    cantidad = int(cantidad_text)
                    if cantidad > 0:
                        disponible, stock = verificar_stock_disponible(sku, cantidad)
                        if not disponible:
                            errores += 1
                            mensaje_error += f"\\n- {sku}: Stock insuficiente ({stock} < {cantidad})"
                            entry.configure(bg='#FFCDD2')
                            continue
                            
                        obs_final = f"{prefix_obs} - {observaciones}" if observaciones else prefix_obs
                        exito, mensaje = registrar_movimiento_gui(sku, tipo_mov, cantidad, None, fecha_evento, None, obs_final)
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
        if messagebox.askyesno("Limpiar", f"¿Está seguro de limpiar todos los {total} equipos escaneados?"):
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
            messagebox.showerror("Serial No Encontrado", f"El serial '{serial}' no existe en la base de datos.\\n\\nVerifique que fue registrado en Abasto.")
            self.entry_scan.delete(0, tk.END)
            self.entry_scan.focus_set()
            return
        
        if ubicacion != 'BODEGA':
            messagebox.showwarning("Serial Ya Asignado", f"El serial '{serial}' ya está asignado a: {ubicacion}\\n\\nNo se puede asignar nuevamente.")
            self.entry_scan.delete(0, tk.END)
            self.entry_scan.focus_set()
            return
        
        if serial in self.seriales_escaneados[sku]:
            messagebox.showinfo("Duplicado", f"El serial '{serial}' ya fue escaneado en esta sesión.")
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
        if not messagebox.askyesno("Confirmar Asignación", f"¿Confirma asignar {total_equipos} equipos escaneados a {movil}?"):
            return
        
        exitos = 0
        errores = 0
        errores_detalle = []
        
        for sku, seriales_list in self.seriales_escaneados.items():
            cantidad = len(seriales_list)
            exito_mov, mensaje_mov = registrar_movimiento_gui(
                sku, 'SALIDA_MOVIL', cantidad, movil, 
                fecha, paquete, f"Asignación por escaneo - {cantidad} equipos"
            )
            
            if not exito_mov:
                errores += cantidad
                errores_detalle.append(f"SKU {sku}: {mensaje_mov}")
                continue
            
            for serial in seriales_list:
                exito_ser, mensaje_ser = actualizar_ubicacion_serial(serial, movil, paquete=paquete)
                if exito_ser: exitos += 1
                else: 
                    errores += 1
                    errores_detalle.append(f"Serial {serial}: {mensaje_ser}")
        
        if errores == 0:
            mostrar_mensaje_emergente(self.master, "Éxito", f"Se asignaron {exitos} equipos exitosamente a {movil}.", "success")
            self.ofrecer_pdf(movil, self.seriales_escaneados.items())
            if self.on_close_callback: self.on_close_callback()
            self.ventana.destroy()
        else:
            mensaje = f"Se procesaron algunos items con errores:\\n\\nÉxitos: {exitos}\\nErrores: {errores}\\n\\nDetalles:\\n" + "\\n".join(errores_detalle[:5])
            mostrar_mensaje_emergente(self.ventana, "Proceso con Errores", mensaje, "warning")
            # MANTENER VENTANA ABIERTA PARA CORRECCIÓN
        
        if exitos > 0: self.crear_recordatorios_automaticos(fecha)

    def _procesar_modo_manual(self, movil, fecha, paquete):
        exitos = 0
        errores = 0
        errores_msg = []
        
        for sku, entry in self.salida_entries.items():
            cant_str = entry.get().strip()
            if cant_str and cant_str.isdigit() and int(cant_str) > 0:
                cantidad = int(cant_str)
                exito, msg = registrar_movimiento_gui(
                    sku, 'SALIDA_MOVIL', cantidad, 
                    movil_afectado=movil,
                    fecha_evento=fecha,
                    paquete_asignado=paquete,
                    observaciones="Salida Manual a Móvil"
                )
                if exito: exitos += 1
                else: 
                    errores += 1
                    errores_msg.append(f"{sku}: {msg}")
        
        if exitos > 0:
            mostrar_mensaje_emergente(self.ventana, "Éxito", f"{exitos} productos asignados a {movil}.", "success")
            # PDF Logic manual
            productos_pdf = []
            for sku, entry in self.salida_entries.items():
                 c_text = entry.get().strip()
                 if c_text and int(c_text) > 0:
                     productos_pdf.append((sku, c_text)) # Simplified, will resolve name in ofrecer_pdf adapter
            
            self.ofrecer_pdf_manual(movil, productos_pdf)
            
            if errores == 0:
                if self.on_close_callback: self.on_close_callback()
                self.ventana.destroy()
        
        if errores > 0:
            mostrar_mensaje_emergente(self.ventana, "Error parcial", f"Se registraron {exitos} productos pero hubo errores en {errores}:\\n{', '.join(errores_msg)}", "error")
        elif exitos == 0:
            mostrar_mensaje_emergente(self.ventana, "Información", "No se ingresaron cantidades válidas para procesar.", "info")

        if exitos > 0: self.crear_recordatorios_automaticos(fecha)

    def ofrecer_pdf(self, movil, items_iter):
        if messagebox.askyesno("Vale de Despacho", "¿Desea generar el Vale de Despacho en PDF para este movimiento?"):
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
        if messagebox.askyesno("Vale de Despacho", "¿Desea generar el Vale de Despacho en PDF para este movimiento?"):
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
        
        threading.Thread(target=self._load_moviles, daemon=True).start()

        self.entry_fecha = tk.Entry(top_panel, width=12)
        self.entry_fecha.insert(0, self.session_data['fecha'])
        self.entry_fecha.pack(side='left')

        tk.Label(top_panel, text="Filtrar por Paquete:", bg='white').pack(side='left', padx=(20, 10))
        self.paquete_combo = ttk.Combobox(top_panel, values=["TODOS", "PAQUETE A", "PAQUETE B", "CARRO", "PERSONALIZADO", "NINGUNO"], state='readonly', width=15)
        self.paquete_combo.set("TODOS")
        self.paquete_combo.pack(side='left', padx=5)
        self.paquete_combo.bind("<<ComboboxSelected>>", lambda e: self.update_fisico_ui())

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
        self.tree_fisico.tag_configure('missing', background='#f8d7da')
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
        
        self.btn_procesar = tk.Button(bottom_panel, text="✅ Finalizar Historial y Retorno", 
                               bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                               state='disabled', padx=20, pady=10, command=self.finalizar)
        self.btn_procesar.pack(side='right', padx=20, pady=10)

        # Bindings
        self.movil_combo.bind("<<ComboboxSelected>>", self.on_movil_select)
        self.entry_scan.bind("<Return>", self.on_scan)
        self.tree_fisico.bind("<Double-1>", self.mostrar_detalle_mac)
        self.entry_fecha.focus_set()

    def _load_moviles(self):
        ms = obtener_nombres_moviles()
        if self.ventana.winfo_exists():
            self.ventana.after(0, lambda: self._update_combo(ms))
            
    def _update_combo(self, values):
        self.movil_combo['values'] = values

    def reset_session(self):
        self.session_data['stock_teorico'] = {}
        self.session_data['consumo_app'] = {}
        self.session_data['consumo_verificado'] = {}
        self.session_data['stock_fisico_escaneado'] = {}
        self.session_data['excel_data'] = []
        for i in self.tree_consumo.get_children(): self.tree_consumo.delete(i)
        for i in self.tree_fisico.get_children(): self.tree_fisico.delete(i)
        self.btn_procesar.config(state='disabled')

    def on_movil_select(self, event):
        movil = self.movil_combo.get()
        if not movil: return
        self.session_data['movil'] = movil
        self.reset_session()
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
        consumo_reportado = {}
        for p in pendientes:
            if str(p[1]).strip().upper() == movil.strip().upper():
                sku = p[2]
                qty = int(p[4])
                consumo_reportado[sku] = consumo_reportado.get(sku, 0) + qty
        return {'stock': stock_actual, 'consumo': consumo_reportado}

    def _on_data_loaded(self, data):
        self.session_data['stock_teorico'] = data['stock']
        self.session_data['consumo_app'] = data['consumo']
        self.update_consumo_ui()
        self.update_fisico_ui()

    def update_consumo_ui(self):
        for i in self.tree_consumo.get_children(): self.tree_consumo.delete(i)
        all_skus = set(self.session_data['consumo_app'].keys()) | set([x['sku'] for x in self.session_data['excel_data']])
        
        for sku in all_skus:
            name = "Desconocido"
            if sku in self.session_data['stock_teorico']:
                name = self.session_data['stock_teorico'][sku]['name']
            
            qty_app = self.session_data['consumo_app'].get(sku, 0)
            qty_excel = 0
            for item in self.session_data['excel_data']:
                if item['sku'] == sku: qty_excel += item['qty']
            
            diff = qty_excel - qty_app
            status = "Correcto" if diff == 0 else f"Dif: {diff}"
            tag = 'ok' if diff == 0 else 'error'
            
            self.session_data['consumo_verificado'][sku] = qty_excel
            self.tree_consumo.insert('', 'end', values=(name, qty_app, qty_excel, status), tags=(tag,))

        self.update_fisico_ui()

    def update_fisico_ui(self):
        for i in self.tree_fisico.get_children(): self.tree_fisico.delete(i)
        all_skus = set(self.session_data['stock_teorico'].keys()) | set(self.session_data['stock_fisico_escaneado'].keys())
        
        paquete_filtro = self.paquete_combo.get() # "TODOS", "PAQUETE A", etc.

        # Mapeo global de nombres para items extra
        if not hasattr(self, '_prod_name_map'):
            try:
                self._prod_name_map = {p[1]: p[0] for p in obtener_todos_los_skus_para_movimiento()}
            except:
                self._prod_name_map = {}

        for sku in all_skus:
            info = self.session_data['stock_teorico'].get(sku)
            if info:
                name = info['name']
            else:
                # Buscar en catálogo global si no está en el móvil
                name = self._prod_name_map.get(sku, "Material Extra (No Asignado)")
            
            # Cantidad esperada según filtro
            if paquete_filtro == "TODOS":
                gross_assigned = info.get('total', 0)
            else:
                gross_assigned = info.get(paquete_filtro, 0)

            consumed = self.session_data['consumo_verificado'].get(sku, 0)
            # El consumo usualmente no está asociado a un paquete específico en la base de datos de movimientos?
            # En realidad, si filtramos por paquete A, deberíamos ver cuánto falta de ese paquete.
            # Pero el consumo verified es total. Esto es un poco ambiguo.
            # Usualmente el técnico consume de sus paquetes.
            # Por ahora, si gross_assigned es 0 para un paquete pero hay stock total, no debería restar consumo de ahí?
            # Vamos a simplificar: expected = gross_assigned. 
            # Si el usuario quiere ver "reales" vs "esperados en paquete", el consumo ya debió ser descontado del stock_teorico si es que se registró.
            # PERO `obtener_asignacion_movil_con_paquetes` ya devuelve el stock ACTUAL (total y por paquete).
            # Entonces `expected` debería ser simplemente `gross_assigned`.
            
            expected = gross_assigned 
            scanned = self.session_data['stock_fisico_escaneado'].get(sku, 0)
            
            # Si no hay nada esperado ni escaneado, saltar (si estamos filtrando)
            if paquete_filtro != "TODOS" and expected == 0 and scanned == 0:
                continue

            if scanned == expected:
                state = "✅ OK"; tag = 'found'
            elif scanned < expected:
                state = f"❌ Faltan {expected - scanned}"; tag = 'missing'
            else:
                state = f"⚠️ Sobran {scanned - expected}"; tag = 'extra'
            
            self.tree_fisico.insert('', 'end', values=(sku, name, expected, scanned, state), tags=(tag,))
        
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
        series = obtener_series_por_sku_y_ubicacion(sku, movil)
        
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
                 self.entry_scan.config(bg='#fff3cd') # Duplicado en esta sesión
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
            # Si es material (no serial), pedir cantidad
            qty_scanned = 1
            if not is_serial:
                from tkinter import simpledialog
                # Buscar nombre para el prompt
                nombre_p = self._prod_name_map.get(sku_found, "Material")
                qty = simpledialog.askinteger("Cantidad Real", f"Producto: {nombre_p}\nSKU: {sku_found}\n\n¿Qué cantidad física está contando?", 
                                               parent=self.ventana, minvalue=0)
                if qty is None: return # Cancelado
                qty_scanned = qty
            
            # Actualizar contador físico
            if is_serial:
                self.session_data['stock_fisico_escaneado'][sku_found] = self.session_data['stock_fisico_escaneado'].get(sku_found, 0) + 1
            else:
                # Los materiales se sobrescriben con la cantidad real contada/ingresada
                self.session_data['stock_fisico_escaneado'][sku_found] = qty_scanned
            
            self.entry_scan.config(bg='#d4edda')
            self.ventana.after(200, lambda: self.entry_scan.config(bg='#e8f0fe'))
            self.update_fisico_ui()
            logger.info(f"✅ Auditado: {sku_found} -> Qty: {qty_scanned} ({'Serial' if is_serial else 'Material'})")
        else:
            # No se encontró de ninguna forma
            self.entry_scan.config(bg='#f8d7da')
            self.ventana.after(1000, lambda: self.entry_scan.config(bg='#e8f0fe'))
            logger.warning(f"❌ Código '{code}' no reconocido en este móvil")

    def finalizar(self):
        if not messagebox.askyesno("Confirmar Cierre", "Se procesará el retorno y consumo. ¿Continuar?"): return
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
            
        movil = self.session_data['movil']
            
        try:
            conn = get_db_connection()
            fecha_evento = self.entry_fecha.get()
            
            # 1. Procesar CONSUMOS
            for sku, qty in self.session_data['consumo_verificado'].items():
                if qty > 0:
                    ok, msg = registrar_movimiento_gui(sku, 'CONSUMO_MOVIL', qty, movil, fecha_evento, None, "Auditoría Automática (Excel)", existing_conn=conn)
                    if ok: exitos_consumo += 1
                    else: errors.append(f"Consumo {sku}: {msg}")
            
            # 2. Procesar RETORNOS
            for sku, qty in self.session_data['stock_fisico_escaneado'].items():
                if qty > 0:
                     ok, msg = registrar_movimiento_gui(sku, 'RETORNO_MOVIL', qty, movil, fecha_evento, None, "Retorno Auditado", existing_conn=conn)
                     if ok: 
                         exitos_retorno += 1
                         # Preparar datos para reutilizar
                         nombre_p = "Producto"
                         for p_nom, p_sku, _ in self.productos:
                             if p_sku == sku:
                                 nombre_p = p_nom
                                 break
                         
                         seriales_ret = self.session_data.get(f"_seriales_{sku}", [])
                         reutilizar_items.append({
                             'sku': sku,
                             'nombre': nombre_p,
                             'cantidad': qty,
                             'seriales': seriales_ret
                         })
                     else: 
                         errors.append(f"Retorno {sku}: {msg}")
            
            # 3. Actualizar Seriales de forma masiva (Optimización)
            all_serials_to_return = []
            for key, seriales_list in self.session_data.items():
                if key.startswith("_seriales_"):
                    all_serials_to_return.extend(seriales_list)
            
            if all_serials_to_return:
                try:
                    placeholders = ', '.join(['?'] * len(all_serials_to_return))
                    sql_bulk = f"UPDATE series_registradas SET ubicacion = 'BODEGA', paquete = NULL WHERE serial_number IN ({placeholders})"
                    run_query(cursor, sql_bulk, all_serials_to_return)
                    logger.info(f"✅ {len(all_serials_to_return)} seriales retornados a BODEGA.")
                except Exception as e:
                    logger.error(f"Error en retorno masivo de seriales: {e}")
                    # Fallback uno a uno si falla el masivo por algun limite de DB
                    for serial in all_serials_to_return:
                        try: actualizar_ubicacion_serial(serial, 'BODEGA', existing_conn=conn)
                        except: pass

            conn.commit()
        except Exception as e:
            logger.error(f"Error en _procesar_async de retorno: {e}")
            if conn: conn.rollback()
            errors.append(str(e))
        finally:
            if conn: conn.close()
        
        # 4. Limpieza de Pendientes
        try:
            pendientes = obtener_consumos_pendientes()
            ids_to_clean = [p[0] for p in pendientes if str(p[1]).upper() == str(self.session_data['movil']).upper()]
            for pid in ids_to_clean: eliminar_consumo_pendiente(pid)
        except Exception as e: logger.error(f"Error limpiando pendientes: {e}")
        
        # 5. Resultado y Opción de Reutilizar
        summary = f"Proceso Completado.\n\nConsumos: {exitos_consumo}\nRetornos: {exitos_retorno}"
        if errors: summary += "\n\nErrores:\n" + "\n".join(errors[:5])
        
        def final_ui_feedback():
            # Restaurar botón
            self.btn_procesar.config(state='normal', text="✅ Finalizar Historial y Retorno")
            
            # Feedback inicial
            if errors:
                messagebox.showwarning("Proceso con Errores", summary, parent=self.ventana)
            else:
                if not discrepancias_msg:
                    messagebox.showinfo("Resultado", summary, parent=self.ventana)
            
            # 1. Discrepancias en la Auditoría (Faltantes contra lo que el sistema creía que tenían)
            if discrepancias_msg:
                msg_final = f"Auditoría Finalizada con Discrepancias:\n{discrepancias_msg}\n\n¿Desea procesar el retorno de lo contado y luego ver opciones de relleno?"
                if not messagebox.askyesno("Confirmar Resultado", msg_final, parent=self.ventana):
                     return

            # 2. Opción de Rellenar Faltantes (Lo que no se encontró en la auditoría física)
            if faltantes_relleno:
                if messagebox.askyesno("Rellenar Faltantes", "¿Desea abrir la ventana de Salida para RELLENAR los faltantes detectados en la auditoría?", parent=self.ventana):
                    self.ventana.destroy()
                    from ..mobile_output_scanner import MobileOutputScannerWindow
                    MobileOutputScannerWindow(self.master_app, mode='SALIDA_MOVIL', 
                                              prefill_items=faltantes_relleno,
                                              initial_movil=movil,
                                              initial_package=paquete_objetivo)
                    return

            # 3. Opción de Reutilizar lo devuelto (Equipos que volvieron y queremos asignar a otro paquete o móvil)
            if exitos_retorno > 0:
                if messagebox.askyesno("Reutilizar", "¿Desea reutilizar estos equipos/materiales para una nueva SALIDA inmediata?", parent=self.ventana):
                    self.ventana.destroy()
                    from ..mobile_output_scanner import MobileOutputScannerWindow
                    MobileOutputScannerWindow(self.master_app, mode='SALIDA_MOVIL', 
                                              prefill_items=reutilizar_items,
                                              initial_movil=movil,
                                              initial_package=paquete_objetivo)
                    return
            
            # 4. Opción de Rellenar el paquete estándar (si no está completo)
            # Intentamos detectar si algún paquete (A o B) está incompleto si no se seleccionó uno
            paquetes_a_revisar = [paquete_objetivo] if paquete_objetivo != "TODOS" else ["PAQUETE A", "PAQUETE B"]
            
            # Obtener stock actual del móvil tras el commit para ver qué falta
            actual_stock_post = obtener_asignacion_movil_con_paquetes(movil)
            from config import PAQUETES_MATERIALES
            
            for paq_test in paquetes_a_revisar:
                standard_items = PAQUETES_MATERIALES.get(paq_test, [])
                if not standard_items: continue
                
                # Mapear paq_test a índice
                idx = {"PAQUETE A": 3, "PAQUETE B": 4, "CARRO": 5, "PERSONALIZADO": 7, "NINGUNO": 6}.get(paq_test, 2)
                current_map = {item_p[1]: item_p[idx] for item_p in actual_stock_post}

                relleno_list = []
                for sku_s, qty_s in standard_items:
                    actual_q = current_map.get(sku_s, 0)
                    if actual_q < qty_s:
                        nombre_s = "Desconocido"
                        for p_nom, p_sku, _ in self.productos:
                            if p_sku == sku_s:
                                nombre_s = p_nom
                                break
                        relleno_list.append({
                            'sku': sku_s,
                            'nombre': nombre_s,
                            'cantidad': qty_s - actual_q,
                            'seriales': []
                        })
                
                if relleno_list:
                    if messagebox.askyesno("Rellenar Paquete", f"El {paq_test} aún no está completo.\n¿Desea abrir la ventana de Salida para completarlo?", parent=self.ventana):
                        self.ventana.destroy()
                        from ..mobile_output_scanner import MobileOutputScannerWindow
                        MobileOutputScannerWindow(self.master_app, mode='SALIDA_MOVIL', 
                                                  prefill_items=relleno_list,
                                                  initial_movil=movil,
                                                  initial_package=paq_test)
                        return

            # Si llegamos aquí y no hubo errores críticos, cerramos
            if not errors:
                 messagebox.showinfo("Éxito", "Operación finalizada correctamente.", parent=self.ventana)
                 self.ventana.destroy()

            if self.on_close_callback: self.on_close_callback()

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
        
        # Recopilar faltantes desde la tabla
        faltantes_relleno = []
        for i in self.tree_fisico.get_children():
            v = self.tree_fisico.item(i, 'values')
            sku_c, nom_c = v[0], v[1]
            try:
                exp_c = int(v[2]); sca_c = int(v[3])
                if sca_c < exp_c:
                    faltantes_relleno.append({
                        'sku': sku_c,
                        'nombre': nom_c,
                        'cantidad': exp_c - sca_c,
                        'seriales': []
                    })
            except: pass
        
        if not faltantes_relleno:
            from tkinter import messagebox
            messagebox.showinfo("Sin Faltantes", "No se detectan faltantes en la auditoría actual. Escanea items para comparar.", parent=self.ventana)
            return
        
        from tkinter import messagebox
        resumen = "\n".join([f"  • {f['nombre']}: faltan {f['cantidad']}" for f in faltantes_relleno[:10]])
        if not messagebox.askyesno("Abrir Salida para Rellenar", 
                                   f"Se detectaron {len(faltantes_relleno)} productos con faltantes:\n\n{resumen}\n\n"
                                   f"¿Abrir Salida a {movil} para rellenar estos items?",
                                   parent=self.ventana):
            return
        
        self.ventana.destroy()
        from ..mobile_output_scanner import MobileOutputScannerWindow
        MobileOutputScannerWindow(self.master_app, mode='SALIDA_MOVIL',
                                  prefill_items=faltantes_relleno,
                                  initial_movil=movil,
                                  initial_package=paquete_objetivo if paquete_objetivo != 'TODOS' else 'PAQUETE A')



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


