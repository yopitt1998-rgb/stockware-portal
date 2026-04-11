import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import date

from database import (
    obtener_todos_los_skus_para_movimiento,
    registrar_danado_directo,
    registrar_consumo_no_registrado,
    obtener_info_serial,
    obtener_sku_por_codigo_barra,
    obtener_nombres_moviles,
    logger
)
from config import COLORS, PRODUCTOS_CON_CODIGO_BARRA
from .utils import ScrollableFrame

class SantiagoDanadosTab:
    def __init__(self, master, app_instance):
        self.master = master
        self.app = app_instance
        self.cart_items = []
        
        self.scroll_container = None
        self.main_frame = None
        self.btn_procesar_carrito = None
        self.btn_reversa = None
        self.info_frame = None
        self.lbl_info_title = None
        self.lbl_info_status = None
        self.modo_registro = "DAÑADO"
        self.rb_danado = None
        self.rb_consumo = None
        self.reporter_entry = None
        self.obs_entry = None
        self.direct_scan_var = tk.StringVar()
        self.direct_scan_entry = None
        self.search_var = tk.StringVar()
        self.search_entry = None
        self.cart_tree = None
        self.tree = None
        self.all_products = []
        
        self.setup_ui()
        self.cargar_datos_iniciales()

    def setup_ui(self):
        # Layout principal con ScrollableFrame para asegurar visibilidad en cualquier pantalla
        self.scroll_container = ScrollableFrame(self.master, bg='#f8f9fa')
        self.scroll_container.pack(fill='both', expand=True)
        
        self.main_frame = self.scroll_container.scrollable_frame
        self.main_frame.configure(padx=20, pady=20)

        # Header
        header = tk.Frame(self.main_frame, bg='white', relief='flat', pady=15, padx=20)
        header.pack(fill='x', pady=(0, 20))
        
        tk.Label(header, text="📑 Registro de Bajas y Consumos Externos", 
                 font=('Segoe UI', 18, 'bold'), bg='white', fg='#2c3e50').pack(anchor='w')
        tk.Label(header, text="Use esta pestaña para reportar material dañado o equipos usados fuera del portal que no fueron registrados.", 
                 font=('Segoe UI', 9), bg='white', fg='gray').pack(anchor='w')

        # BOTÓN PROCESAR EN EL HEADER PARA QUE SEA VISIBLE (FRENTE)
        self.btn_procesar_carrito = tk.Button(header, text="🚀 PROCESAR Y GUARDAR", state='disabled',
                                              command=self.procesar_y_guardar_carrito, bg='#27ae60', fg='white', 
                                              font=('Segoe UI', 11, 'bold'), padx=20, pady=10, relief='flat')
        self.btn_procesar_carrito.pack(side='right', padx=10)

        # Info / Status Frame (Highlighted)
        self.info_frame = tk.Frame(self.main_frame, bg='#eef2f7', bd=1, relief='solid', padx=15, pady=10)
        self.info_frame.pack(fill='x', pady=(0, 15))
        
        self.lbl_info_title = tk.Label(self.info_frame, text="🔍 Información del Ítem detectado:", font=('Segoe UI', 9, 'bold'), bg='#eef2f7', fg='#555')
        self.lbl_info_title.grid(row=0, column=0, sticky='w')
        
        self.lbl_info_status = tk.Label(self.info_frame, text="Escanee un producto para ver detalles...", font=('Segoe UI', 10), bg='#eef2f7', fg='#2c3e50')
        self.lbl_info_status.grid(row=1, column=0, sticky='w')

        # Form Area (Input Data)
        form_frame = tk.Frame(self.main_frame, bg='white', padx=25, pady=20, relief='flat')
        form_frame.pack(fill='x', pady=(0, 20))
        
        from config import CURRENT_CONTEXT
        branch_name = CURRENT_CONTEXT.get('BRANCH', 'SANTIAGO')
        
        # Row 1: Tipo de Registro
        tk.Label(form_frame, text="1. ¿Qué está reportando?", font=('Segoe UI', 10, 'bold'), bg='white').grid(row=0, column=0, sticky='w', pady=5)
        
        mode_frame = tk.Frame(form_frame, bg='white')
        mode_frame.grid(row=0, column=1, columnspan=2, sticky='w', padx=10)
        
        self.modo_registro = tk.StringVar(value="DANADO")
        self.rb_danado = tk.Radiobutton(mode_frame, text="⚠️ Dañado / Malo", variable=self.modo_registro, 
                                        value="DANADO", bg='white', font=('Segoe UI', 10), command=self._on_modo_change)
        self.rb_danado.pack(side='left', padx=(0, 20))
        
        self.rb_consumo = tk.Radiobutton(mode_frame, text="📝 Consumo Externo (No Registrado)", variable=self.modo_registro, 
                                         value="CONSUMO", bg='white', font=('Segoe UI', 10), command=self._on_modo_change)
        self.rb_consumo.pack(side='left')

        # Row 2: Origen / Reportado por
        tk.Label(form_frame, text="2. Origen / Reportado por:", font=('Segoe UI', 10, 'bold'), bg='white').grid(row=1, column=0, sticky='w', pady=10)
        
        self.reporter_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), width=40)

        self.reporter_entry.grid(row=1, column=1, sticky='w', padx=10)
        self.reporter_entry.insert(0, f"Bodega {branch_name}")
        
        tk.Label(form_frame, text="(Detectado automático al escanear equipo)", font=('Segoe UI', 8), bg='white', fg='gray').grid(row=1, column=2, sticky='w')

        # Row 3: Observación
        tk.Label(form_frame, text="3. Observación:", font=('Segoe UI', 10, 'bold'), bg='white').grid(row=2, column=0, sticky='w', pady=5)
        self.obs_entry = ttk.Entry(form_frame, font=('Segoe UI', 10), width=60)
        self.obs_entry.grid(row=2, column=1, columnspan=2, sticky='w', padx=10)
        self.obs_entry.insert(0, "Material Dañado / Defectuoso")


        # Container for Search & Cart
        middle_wrapper = tk.Frame(self.main_frame, bg='#f8f9fa')
        middle_wrapper.pack(fill='both', expand=True, pady=(0, 20))
        
        # Search & Quick Scan
        search_panel = tk.Frame(middle_wrapper, bg='white', padx=20, pady=20)
        search_panel.pack(fill='x', pady=(0, 10))
        
        tk.Label(search_panel, text="🔫 ESCANEAR MAC / SERIAL / CÓDIGO MAESTRO:", bg='white', font=('Segoe UI', 11, 'bold'), fg='#c0392b').pack(side='left')
        self.direct_scan_var = tk.StringVar()
        self.direct_scan_entry = ttk.Entry(search_panel, textvariable=self.direct_scan_var, font=('Segoe UI', 14), width=30)
        self.direct_scan_entry.pack(side='left', padx=15)
        self.direct_scan_entry.focus_set()
        self.direct_scan_entry.bind('<Return>', lambda e: self.procesar_escaneo_directo())

        tk.Label(search_panel, text="O busque por nombre:", bg='white', font=('Segoe UI', 9), fg='gray').pack(side='left', padx=(50, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filtrar_productos)
        self.search_entry = ttk.Entry(search_panel, textvariable=self.search_var, font=('Segoe UI', 10))
        self.search_entry.pack(side='left', fill='x', expand=True)

        # Cart Treeview
        cart_frame = tk.Frame(middle_wrapper, bg='white', padx=20, pady=10)
        cart_frame.pack(fill='both', expand=True)
        
        tk.Label(cart_frame, text="🛒 Lista de Ítems a Reportar", font=('Segoe UI', 11, 'bold'), anchor='w', bg='white', fg='#2c3e50').pack(fill='x', pady=(0, 5))
        
        cols = ('Descripción', 'SKU', 'Cantidad', 'Serial/MAC', 'Origen')
        self.cart_tree = ttk.Treeview(cart_frame, columns=cols, show='headings', height=6, style='Modern.Treeview')
        for col in cols: self.cart_tree.heading(col, text=col)
        self.cart_tree.column('Descripción', width=300)
        self.cart_tree.column('SKU', width=120)
        self.cart_tree.column('Cantidad', width=80, anchor='center')
        self.cart_tree.column('Serial/MAC', width=200)
        self.cart_tree.column('Origen', width=150)
        
        c_scroll = ttk.Scrollbar(cart_frame, orient='vertical', command=self.cart_tree.yview)
        self.cart_tree.configure(yscroll=c_scroll.set)
        self.cart_tree.pack(side='left', fill='both', expand=True)
        c_scroll.pack(side='right', fill='y')
        
        self.cart_tree.bind('<Delete>', self.remover_del_carrito)
        
        # ---- Tabla de Productos (abajo) ----
        self._setup_product_list()

    def _setup_product_list(self):
        """Creates the product list Treeview once. Call from setup_ui only."""
        tree_frame = tk.Frame(self.main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('Nombre', 'SKU', 'Stock en Bodega', 'Tipo')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse', style='Modern.Treeview')
        
        for col in columns: 
            self.tree.heading(col, text=col)
        
        self.tree.column('Nombre', width=400)
        self.tree.column('SKU', width=120)
        self.tree.column('Stock en Bodega', width=120, anchor='center')
        self.tree.column('Tipo', width=80, anchor='center')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.tree.bind('<Double-1>', lambda e: self.abrir_ventana_danado())

    def _on_modo_change(self):

        modo = self.modo_registro.get()
        if modo == "DANADO":
            self.obs_entry.delete(0, tk.END)
            self.obs_entry.insert(0, "Material Dañado / Defectuoso")
            self.direct_scan_entry.config(foreground='#c0392b')
            self.lbl_info_status.config(text="Modo: REPORTE DE DAÑO. Escanee para detectar origen.")
        else:
            self.obs_entry.delete(0, tk.END)
            self.obs_entry.insert(0, "Consumo fuera del portal / Uso técnico")
            self.direct_scan_entry.config(foreground='#27ae60')
            self.lbl_info_status.config(text="Modo: CONSUMO EXTERNO. Escanee para detectar origen.")


    def remover_del_carrito(self, event=None):
        selected = self.cart_tree.selection()
        if not selected: return
        idx = self.cart_tree.index(selected[0])
        self.cart_tree.delete(selected[0])
        if 0 <= idx < len(self.cart_items):
            self.cart_items.pop(idx)
            self._actualizar_estado_boton_carrito()

    def _actualizar_estado_boton_carrito(self):
        if self.cart_items:
            self.btn_procesar_carrito.config(state='normal', text=f"🚀 PROCESAR Y GUARDAR ({len(self.cart_items)} ITEMS)")
        else:
            self.btn_procesar_carrito.config(state='disabled', text="🚀 PROCESAR Y GUARDAR")

    def procesar_escaneo_directo(self):
        sn = self.direct_scan_var.get().strip().upper()
        self.direct_scan_var.set("")
        if not sn: return

        reporter = self.reporter_entry.get().strip()
        if not reporter:
            messagebox.showwarning("Faltan Datos", "Indique el origen o quién reporta (Bodega o Móvil).")
            return

        try:
            # 1. Intentar identificar el código maestro de un MATERIAL
            sku_material = obtener_sku_por_codigo_barra(sn)
            
            if sku_material and sku_material not in PRODUCTOS_CON_CODIGO_BARRA:
                # Es un material, pedir cantidad
                nombre_prod = "Material"
                stock_disponible = 0
                from tkinter import simpledialog
                if hasattr(self, 'all_products'):
                    for p in self.all_products:
                        if p[1] == sku_material:
                            nombre_prod = p[0]
                            stock_disponible = p[2]
                            break
                
                # Check if it was already added to the cart
                qty_in_cart = 0
                for item in self.cart_items:
                    if item['sku'] == sku_material:
                        qty_in_cart += item['qty']
                            
                qty_str = simpledialog.askstring("Cantidad", f"Material: {nombre_prod}\nSKU: {sku_material}\nStock en bodega: {stock_disponible}\nYa en lista: {qty_in_cart}\n\n¿Qué cantidad reportará como dañada?", parent=self.master)
                if not qty_str: return
                
                try:
                    qty = int(qty_str)
                    if qty <= 0: return
                    if (qty + qty_in_cart) > stock_disponible:
                        messagebox.showerror("Stock Insuficiente", f"No puede reportar {qty + qty_in_cart} daños porque solo hay {stock_disponible} en BODEGA.")
                        return
                except ValueError:
                    messagebox.showerror("Error", "Cantidad inválida.")
                    return
                
                # Check if item exists in cart to update qty, else create new
                found = False
                for item in self.cart_items:
                    if item['sku'] == sku_material:
                        item['qty'] += qty
                        found = True
                        break
                
                if not found:
                    self.cart_items.append({
                        'sku': sku_material, 
                        'nombre': nombre_prod, 
                        'qty': qty, 
                        'seriales': [], 
                        'tipo': 'MATERIAL',
                        'origen': reporter
                    })

                
                self._render_cart()
                return

            # 2. Si no es un material (o no se encontró), intentar buscar como serial/MAC de equipo
            sku_db, loc = obtener_info_serial(sn)
            if not sku_db:
                self.lbl_info_status.config(text=f"❌ No encontrado: {sn}", fg='red')
                messagebox.showerror("No Encontrado", f"El código {sn} no corresponde a un material ni el serial/MAC está registrado en el sistema.")
                return

            # AUTO-DETECCION DE ORIGEN
            if loc:
                from config import CURRENT_CONTEXT
                branch_name = CURRENT_CONTEXT.get('BRANCH', 'SANTIAGO')
                
                # Formatear ubicacion para el campo Origen
                origin_val = loc
                if loc.upper() == "BODEGA":
                    origin_val = f"Bodega {branch_name}"
                
                # Actualizar campos automáticamente
                self.reporter_entry.delete(0, tk.END)
                self.reporter_entry.insert(0, origin_val)
                
                # Actualizar observacion sugerida
                if "MOVIL" in loc.upper():
                    self.obs_entry.delete(0, tk.END)
                    if self.modo_registro.get() == "DANADO":
                        self.obs_entry.insert(0, f"Dañado detectado en {loc}")
                    else:
                        self.obs_entry.insert(0, f"Consumo reportado de {loc}")

                self.lbl_info_status.config(text=f"✅ detected: {sku_db} | Ubicación: {loc}", fg='#2c3e50')
            else:
                self.lbl_info_status.config(text=f"✅ detected: {sku_db} | Ubicación: Desconocida", fg='#2c3e50')


            # Avoid duplicates in cart
            for item in self.cart_items:
                if sn in item['seriales']:
                    messagebox.showwarning("Duplicado", f"El serial/MAC {sn} ya está en la lista de daños a procesar.")
                    return

            nombre_prod = "Equipo"
            if hasattr(self, 'all_products'):
                for p in self.all_products:
                    if p[1] == sku_db:
                        nombre_prod = p[0]
                        break

            # Check if SKU exists to group serials, else create new
            found = False
            for item in self.cart_items:
                if item['sku'] == sku_db and item['tipo'] == 'EQUIPO':
                    item['seriales'].append(sn)
                    item['qty'] += 1
                    found = True
                    break
            
            if not found:
                self.cart_items.append({
                    'sku': sku_db, 
                    'nombre': nombre_prod, 
                    'qty': 1, 
                    'seriales': [sn], 
                    'tipo': 'EQUIPO',
                    'origen': reporter
                })


            self._render_cart()

        except Exception as e:
            logger.error(f"Error en escaneo directo Dañados: {e}")
            messagebox.showerror("Error", f"Fallo al procesar escaneo: {e}")

    def _render_cart(self):
        for i in self.cart_tree.get_children(): self.cart_tree.delete(i)
        for item in self.cart_items:
            serials_str = ", ".join(item['seriales']) if item['seriales'] else "N/A"
            self.cart_tree.insert('', 'end', values=(item['nombre'], item['sku'], item['qty'], serials_str, item.get('origen', 'N/A')))

        self._actualizar_estado_boton_carrito()

    def procesar_y_guardar_carrito(self):
        if not self.cart_items: return
        
        modo = self.modo_registro.get()
        tipo_str = "dañados" if modo == "DANADO" else "consumos externos"
        
        if not messagebox.askyesno("Confirmar", f"¿Registrar {len(self.cart_items)} tipos de ítems como {tipo_str}?"):
            return

        exitos = 0
        errores = []
        
        self.btn_procesar_carrito.config(state='disabled', text="⏳ PROCESANDO...")
        
        # Obtener Observación actual (común para toda la carga)
        obs = self.obs_entry.get().strip()
        
        # Procesar todos los ítems de la lista
        for item in self.cart_items:
            sku = item['sku']
            qty = item['qty']
            seriales = item['seriales'] if item['seriales'] else None
            reporter = item.get('origen', self.reporter_entry.get())
            
            if modo == "DANADO":
                exito, msg = registrar_danado_directo(sku, qty, reporter, obs, seriales)
            else:
                # Consumo Fuera del Portal
                exito, msg = registrar_consumo_no_registrado(
                    sku=sku, 
                    cantidad=qty, 
                    movil=reporter, 
                    fecha_evento=date.today().isoformat(),
                    seriales=seriales,
                    observaciones=obs
                )

            
            if exito:
                exitos += 1
            else:
                errores.append(f"Error en {sku}: {msg}")
                
        if errores:
            err_str = "\n".join(errores[:5])
            if len(errores) > 5: err_str += f"\n... y {len(errores)-5} más."
            messagebox.showwarning("Proceso Completado con Errores", f"Éxitos: {exitos}\nErrores:\n{err_str}")
        else:
            msg_exito = "Todos los registros han sido guardados correctamente." if modo == "DANADO" else "Consumos externos registrados correctamente."
            messagebox.showinfo("Éxito", msg_exito)
            
        self.cart_items.clear()
        self._render_cart()
        # Refresh data only (don't recreate the tree widget)
        self.cargar_datos_iniciales()
        # Restore focus and re-enable form
        self.btn_procesar_carrito.config(state='disabled', text="🚀 PROCESAR Y GUARDAR")
        self.direct_scan_entry.focus_set()

    def cargar_datos_iniciales(self):
        """Loads/refreshes product data. Does NOT recreate the tree widget."""
        try:
            self.all_products = obtener_todos_los_skus_para_movimiento()
            self.filtrar_productos()
        except Exception as e:
            logger.error(f"Error cargando stock Dañados: {e}")

    def abrir_reverso_consumo(self):
        """Abre ventana para reversar consumos erróneos (Desde Santiago)"""
        try:
            from gui.inventory.reverso import ReversoConsumoScannerWindow
            ReversoConsumoScannerWindow(self.app)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la ventana de reverso: {e}")
            logger.error(f"Error abriendo reverso en Santiago: {e}")

    def filtrar_productos(self, *args):
        search_term = self.search_var.get().lower()
        for item in self.tree.get_children(): self.tree.delete(item)
        
        for p in self.all_products:
            nombre, sku, cant = p
            es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA
            tipo = "EQUIPO" if es_equipo else "MATERIAL"
            
            if search_term in nombre.lower() or search_term in sku.lower():
                self.tree.insert('', 'end', values=(nombre, sku, cant, tipo))

    def abrir_ventana_danado(self):
        selected = self.tree.selection()
        if not selected: return
        
        nombre, sku, stock, tipo = self.tree.item(selected)['values']
        reporter = self.reporter_entry.get().strip()
        
        if not reporter:
            messagebox.showwarning("Faltan Datos", "Indique el origen o quién reporta.")
            return

        self.ventana_accion_danado(sku, nombre, stock, reporter)

    def ventana_accion_danado(self, sku, nombre, stock, reporter):
        vent = tk.Toplevel(self.app.master)
        vent.title("Reportar Daño")
        vent.geometry("500x350")
        vent.configure(bg='white')
        vent.grab_set()

        # Centrar
        x = vent.master.winfo_x() + (vent.master.winfo_width()//2) - (500//2)
        y = vent.master.winfo_y() + (vent.master.winfo_height()//2) - (350//2)
        vent.geometry(f"+{x}+{y}")

        main = tk.Frame(vent, bg='white', padx=30, pady=30)
        main.pack(fill='both', expand=True)

        tk.Label(main, text="Confirmar Reporte de Daño", font=('Segoe UI', 10), bg='white').pack()
        tk.Label(main, text=nombre, font=('Segoe UI', 12, 'bold'), bg='white', fg='#c0392b', wraplength=400).pack(pady=10)
        
        es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA

        if es_equipo:
            tk.Label(main, text="Escanee Serial/MAC del equipo dañado:", bg='white').pack(pady=(10, 5))
            entry = ttk.Entry(main, font=('Segoe UI', 12))
            entry.pack(fill='x', pady=5)
            entry.focus_set()
            
            def procesar():
                sn = entry.get().strip().upper()
                if not sn: return
                sku_db, loc = obtener_info_serial(sn)
                if sku_db != sku:
                    messagebox.showerror("Error", "El serial no corresponde al producto.")
                    return
                
                modo = self.modo_registro.get()
                if modo == "DANADO":
                    exito, msg = registrar_danado_directo(sku, 1, reporter, self.obs_entry.get(), [sn])
                else:
                    exito, msg = registrar_consumo_no_registrado(sku, 1, reporter, date.today().isoformat(), seriales=[sn], observaciones=self.obs_entry.get())

                if exito:
                    vent.destroy()
                    messagebox.showinfo("Éxito", "Registro completado.")
                    self.cargar_datos_iniciales()
                else:
                    messagebox.showerror("Error", msg)

            btn_txt = "⚠️ REGISTRAR DAÑO" if self.modo_registro.get() == "DANADO" else "📝 REGISTRAR CONSUMO"
            btn_bg = "#c0392b" if self.modo_registro.get() == "DANADO" else "#27ae60"
            
            tk.Button(main, text=btn_txt, command=procesar, bg=btn_bg, fg='white', 
                      font=('Segoe UI', 11, 'bold'), relief='flat', pady=10).pack(fill='x', pady=20)
            vent.bind('<Return>', lambda e: procesar())
        else:
            tk.Label(main, text="Cantidad dañada:", bg='white').pack(pady=(10, 5))
            cnt = ttk.Entry(main, font=('Segoe UI', 12), justify='center')
            cnt.insert(0, "1")
            cnt.pack(pady=5)
            cnt.focus_set()

            def procesar():
                try:
                    q = int(cnt.get())
                    if q <= 0 or q > stock: raise ValueError()
                except:
                    messagebox.showerror("Error", "Cantidad inválida.")
                    return
                
                modo = self.modo_registro.get()
                if modo == "DANADO":
                    exito, msg = registrar_danado_directo(sku, q, reporter, self.obs_entry.get())
                else:
                    exito, msg = registrar_consumo_no_registrado(sku, q, reporter, date.today().isoformat(), observaciones=self.obs_entry.get())
                    
                if exito:
                    vent.destroy()
                    messagebox.showinfo("Éxito", "Registro completado.")
                    self.cargar_datos_iniciales()
                else:
                    messagebox.showerror("Error", msg)

            btn_txt = "⚠️ REGISTRAR DAÑO" if self.modo_registro.get() == "DANADO" else "📝 REGISTRAR CONSUMO"
            btn_bg = "#c0392b" if self.modo_registro.get() == "DANADO" else "#27ae60"

            tk.Button(main, text=btn_txt, command=procesar, bg=btn_bg, fg='white', 
                      font=('Segoe UI', 11, 'bold'), relief='flat', pady=10).pack(fill='x', pady=20)
            vent.bind('<Return>', lambda e: procesar())
