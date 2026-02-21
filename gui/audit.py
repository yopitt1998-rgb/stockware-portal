import tkinter as tk
import threading

from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from .styles import Styles
from .utils import mostrar_mensaje_emergente
from database import (
    obtener_consumos_pendientes,
    obtener_nombres_moviles
)
from config import CURRENT_CONTEXT

class AuditTab(tk.Frame):
    """
    Pestaña de Historial de Instalaciones.
    Muestra el consumo reportado por los móviles.
    """
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        self.configure(bg='#f8f9fa')
        
        self.datos_excel = None
        self.moviles_seleccionados = []  # Inicializar lista de móviles seleccionados
        self.create_widgets()
        self.cargar_datos_pendientes()

    def create_widgets(self):
        # Layout principal
        main_container = tk.Frame(self, bg='#f8f9fa', padx=20, pady=20)
        main_container.pack(fill='both', expand=True)

        # --- SECCIÓN SUPERIOR: ACCIONES ---
        top_frame = tk.Frame(main_container, bg='#f8f9fa')
        top_frame.pack(side='top', fill='x', pady=(0, 20))

        tk.Label(top_frame, text="📋 HISTORIAL DE INSTALACIONES", font=('Segoe UI', 16, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(side='left')
        
        # Filtros de fecha
        dates_frame = tk.Frame(top_frame, bg='#f8f9fa')
        dates_frame.pack(side='left', padx=20)

        tk.Label(dates_frame, text="Desde:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left')
        self.fecha_inicio = tk.Entry(dates_frame, width=12, font=('Segoe UI', 9))
        self.fecha_inicio.pack(side='left', padx=5)
        # Default: Hace 7 días
        self.fecha_inicio.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
        tk.Label(dates_frame, text="Hasta:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(10, 0))
        self.fecha_fin = tk.Entry(dates_frame, width=12, font=('Segoe UI', 9))
        self.fecha_fin.pack(side='left', padx=5)
        # Default: Hoy
        self.fecha_fin.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Filtro de Móvil (MODIFICADO: MULTI-SELECCIÓN)
        tk.Label(dates_frame, text="Móviles:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(10, 0))
        
        self.moviles_seleccionados = [] # Lista de móviles seleccionados (vacío = Todos)
        self.btn_moviles = tk.Button(dates_frame, text="Todos los Móviles", command=self.abrir_selector_moviles,
                                    width=20, font=('Segoe UI', 9), relief='groove', bg='white')
        self.btn_moviles.pack(side='left', padx=5)

        # Filtro de Texto (Buscador)
        tk.Label(dates_frame, text="Buscar:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(10, 0))
        self.filtro_entry = ttk.Entry(dates_frame, width=25, font=('Segoe UI', 9))
        self.filtro_entry.pack(side='left', padx=5)
        self.filtro_entry.bind('<Return>', lambda e: self.cargar_datos_pendientes())
        
        # Botón Buscar explícito (UX mejora)
        tk.Button(dates_frame, text="🔍", command=self.cargar_datos_pendientes,
                 bg='#00897B', fg='white', font=('Segoe UI', 8, 'bold'), relief='flat').pack(side='left', padx=0)
        
        # Botón de reset filtros
        tk.Button(dates_frame, text="✖", command=lambda: [self.filtro_entry.delete(0, 'end'), self.cargar_datos_pendientes()],
                 bg='#e0e0e0', font=('Segoe UI', 8), relief='flat').pack(side='left', padx=2)

        btn_frame = tk.Frame(top_frame, bg='#f8f9fa')
        btn_frame.pack(side='right')

        # Botones filtrado (Mantener solo Cargar/Filtrar)
        tk.Button(btn_frame, text="🔍 Cargar Historial", command=self.cargar_datos_pendientes,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=10, pady=4).pack(side='left', padx=5)

        # --- SECCIÓN INFERIOR ---
        bottom_frame = tk.Frame(main_container, bg='#f8f9fa', pady=10)
        bottom_frame.pack(side='bottom', fill='x')

        tk.Label(bottom_frame, text="* Vista de Historial de Instalaciones y Consumo Reportado de Técnicos.", 
                font=('Segoe UI', 9, 'italic'), bg='#f8f9fa', fg='#666').pack(side='left', padx=10)

        # === CONTENEDOR DE TABLA DE HISTORIAL ===
        self.bottom_section = tk.LabelFrame(main_container, text="📜 HISTORIAL DE INSTALACIONES (REPORTADO)", 
                                    font=('Segoe UI', 11, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR, 
                                    relief='groove', borderwidth=2, padx=5, pady=5)
        self.bottom_section.pack(side='top', fill='both', expand=True, pady=(10, 0))
        
        self.table_frame = tk.Frame(self.bottom_section, bg='white', relief='flat')
        self.table_frame.pack(fill='both', expand=True)

        self.columnas_base = ["Móvil", "Contrato", "Fecha Cierre", "Colilla TV"]
        self.columnas_materiales = []
        self._row_ids = {}

        # Tabla inicial (Base + Seriales al final)
        self._crear_tabla_con_columnas(self.columnas_base + ["Seriales"])

        # Binding para ver detalle de seriales
        self.tabla.bind("<Double-1>", self.mostrar_detalle_series)

        # Context Menu (Desactivado para vista de solo lectura)
        self.context_menu = None

    def abrir_selector_moviles(self):
        """Abre un diálogo modal para seleccionar múltiples móviles"""
        dialog = tk.Toplevel(self)
        dialog.title("Seleccionar Móviles")
        dialog.geometry("350x450")
        dialog.transient(self)
        dialog.grab_set()
        
        def aplicar():
            seleccion = [m for m, var in vars_moviles.items() if var.get()]
            if len(seleccion) == len(todos_moviles) or len(seleccion) == 0:
                self.moviles_seleccionados = []
                self.btn_moviles.config(text="Todos los Móviles")
            else:
                self.moviles_seleccionados = seleccion
                txt = f"{len(seleccion)} Seleccionados" if len(seleccion) > 1 else seleccion[0]
                self.btn_moviles.config(text=txt)
            
            self.cargar_datos_pendientes()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", aplicar)
        
        # Centrar
        x = self.main_app.master.winfo_x() + (self.main_app.master.winfo_width() // 2) - 175
        y = self.main_app.master.winfo_y() + (self.main_app.master.winfo_height() // 2) - 225
        dialog.geometry(f"+{x}+{y}")
        
        main_fr = tk.Frame(dialog, padx=10, pady=10)
        main_fr.pack(fill='both', expand=True)
        
        btn_fr = tk.Frame(main_fr)
        btn_fr.pack(fill='x', pady=(0, 10))
        
        vars_moviles = {} 
        
        def toggle_all(state):
            for var in vars_moviles.values():
                var.set(state)
        
        tk.Button(btn_fr, text="Seleccionar Todos", command=lambda: toggle_all(True), font=('Segoe UI', 8)).pack(side='left', expand=True, fill='x', padx=2)
        tk.Button(btn_fr, text="Desmarcar Todos", command=lambda: toggle_all(False), font=('Segoe UI', 8)).pack(side='left', expand=True, fill='x', padx=2)

        # Lista Scrollable
        canvas = tk.Canvas(main_fr, borderwidth=0, background='#ffffff')
        frame = tk.Frame(canvas, background='#ffffff')
        vsb = tk.Scrollbar(main_fr, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((4,4), window=frame, anchor="nw")

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        frame.bind("<Configure>", on_frame_configure)
        
        # Cargar Móviles
        from config import CURRENT_CONTEXT
        todos_moviles = CURRENT_CONTEXT.get('MOVILES', [])
        
        if not todos_moviles:
             try:
                todos_moviles = obtener_nombres_moviles()
             except:
                todos_moviles = []
            
        todos_moviles = sorted(list(set(todos_moviles)))
            
        for movil in todos_moviles:
            var = tk.BooleanVar(value=True if not self.moviles_seleccionados or movil in self.moviles_seleccionados else False)
            if not self.moviles_seleccionados: var.set(True)
            
            chk = tk.Checkbutton(frame, text=movil, variable=var, bg='white', anchor='w')
            chk.pack(fill='x', padx=5, pady=2)
            vars_moviles[movil] = var

        tk.Button(dialog, text="✅ APLICAR FILTRO", command=aplicar, 
                  bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                  pady=8).pack(side='bottom', fill='x', padx=10, pady=10)
    
    def _crear_tabla_con_columnas(self, columnas):
        """Recrea el widget Treeview con las columnas especificadas"""
        for widget in self.table_frame.winfo_children():
            widget.destroy()
            
        scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical")
        scroll_x = ttk.Scrollbar(self.table_frame, orient="horizontal")

        self.tabla = ttk.Treeview(self.table_frame, columns=columnas, show='headings',
                                 yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=self.tabla.yview)
        scroll_x.config(command=self.tabla.xview)
        
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        self.tabla.pack(side='left', fill='both', expand=True, padx=2, pady=2)
        
        for col in columnas:
            self.tabla.heading(col, text=col)
            width = 100
            if col in ["Técnico", "Ayudante", "Móvil"]: width = 150
            if col in ["Fecha", "Fecha Cierre"]: width = 110
            if col == "Contrato": width = 150
            if col == "Seriales": width = 250 
            
            self.tabla.column(col, width=width, anchor='center')

        self.tabla.tag_configure('evenrow', background='#f2f2f2')
        self.tabla.tag_configure('oddrow', background='white')

    def cargar_datos_pendientes(self):
        """Carga los datos en un hilo separado"""
        inicio = self.fecha_inicio.get().strip()
        fin = self.fecha_fin.get().strip()
        texto_buscar = self.filtro_entry.get().strip().upper()
        filtro_moviles = list(self.moviles_seleccionados) if self.moviles_seleccionados else None 

        def run_load():
            try:
                moviles_sql = filtro_moviles
                if not moviles_sql:
                    from config import CURRENT_CONTEXT
                    allowed_moviles = CURRENT_CONTEXT.get('MOVILES', [])
                    if allowed_moviles:
                        moviles_sql = allowed_moviles
                
                consumos = obtener_consumos_pendientes(
                    fecha_inicio=inicio, 
                    fecha_fin=fin,
                    moviles_filtro=moviles_sql
                )
                
                if texto_buscar:
                    consumos_filtrados = []
                    for c in consumos:
                        datos_fila = [str(c[1]), str(c[5]), str(c[6]), str(c[8]), str(c[9]), str(c[10])]
                        if any(texto_buscar in d.upper() for d in datos_fila if d):
                            consumos_filtrados.append(c)
                    consumos = consumos_filtrados
                
                self.after(0, lambda: self._aplicar_pendientes_ui(consumos))
            except Exception as e:
                print(f"⚠️ Error al cargar historial: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _aplicar_pendientes_ui(self, consumos):
        """Aplica los datos a la tabla con columnas dinámicas"""
        if not consumos:
            self._crear_tabla_con_columnas(self.columnas_base + ["Seriales"])
            return

        from collections import defaultdict
        ordenes = defaultdict(list)
        seriales_agrupados = {} 
        todos_productos = set() 

        for c in consumos:
            id_c, movil, sku, nombre, qty, tecnico, ticket, fecha, colilla, contrato, ayudante, seriales_usados = c
            key = (movil, fecha, tecnico, contrato or ticket or "S/C", colilla or "", contrato or ticket or "", ayudante or "")
            
            if seriales_usados:
                if key not in seriales_agrupados: seriales_agrupados[key] = set()
                for s in str(seriales_usados).split(','):
                    if s.strip(): seriales_agrupados[key].add(s.strip())

            ordenes[key].append({
                'id': id_c,
                'sku': sku,
                'nombre': nombre or f"SKU: {sku}",
                'cantidad': qty
            })
            todos_productos.add(nombre or f"SKU: {sku}")
        
        productos_ordenados = sorted(list(todos_productos))
        self.columnas_materiales = productos_ordenados
        columnas_completas = self.columnas_base + productos_ordenados + ["Seriales"]
        
        self._crear_tabla_con_columnas(columnas_completas)
        
        row_num = 0
        self._row_ids = {} 
        
        for key, materiales in ordenes.items():
            movil, fecha, tecnico, ticket, colilla, contrato, ayudante = key
            ids = ",".join([str(m['id']) for m in materiales])
            
            cantidades_por_producto = {}
            for m in materiales:
                nombre_p = m['nombre']
                cantidades_por_producto[nombre_p] = cantidades_por_producto.get(nombre_p, 0) + m['cantidad']
            
            txt_seriales = ", ".join(sorted(list(seriales_agrupados.get(key, []))))
            valores = [movil, contrato or ticket, fecha, colilla]

            for producto in productos_ordenados:
                cant = cantidades_por_producto.get(producto, 0)
                valores.append(cant if cant > 0 else "")

            valores.append(txt_seriales)
            tag = 'evenrow' if row_num % 2 == 0 else 'oddrow'
            item_id = self.tabla.insert('', 'end', values=valores, tags=(tag,))
            self._row_ids[item_id] = ids
            row_num += 1

    def mostrar_detalle_series(self, event):
        """Muestra una ventana pequeña con los seriales detallados para la fila seleccionada"""
        item = self.tabla.identify_row(event.y)
        if not item: return
        
        values = self.tabla.item(item, 'values')
        if not values: return
        
        # El campo 'Seriales' es la última columna
        seriales_str = values[-1]
        movil = values[0]
        contrato = values[1]
        
        if not seriales_str or seriales_str.strip() == "":
            return # No hay seriales que mostrar
            
        seriales = [s.strip() for s in seriales_str.split(',')]
        
        # Crear popup
        popup = tk.Toplevel(self)
        popup.title(f"Seriales: {contrato}")
        popup.geometry("350x400")
        popup.configure(bg='white')
        popup.transient(self.main_app.master)
        popup.grab_set()
        
        # Centrar relativo a la ventana principal
        x = self.main_app.master.winfo_rootx() + (self.main_app.master.winfo_width() // 2) - 175
        y = self.main_app.master.winfo_rooty() + (self.main_app.master.winfo_height() // 2) - 200
        popup.geometry(f"+{x}+{y}")
        
        header = tk.Frame(popup, bg=Styles.PRIMARY_COLOR, height=50)
        header.pack(fill='x')
        tk.Label(header, text="📡 SERIALES (MAC) DETALLADOS", font=('Segoe UI', 10, 'bold'), 
                 bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=12)
        
        info_frame = tk.Frame(popup, bg='#f8f9fa', pady=10)
        info_frame.pack(fill='x')
        tk.Label(info_frame, text=f"Móvil: {movil}", font=('Segoe UI', 9, 'bold'), bg='#f8f9fa').pack()
        tk.Label(info_frame, text=f"Contrato/Ticket: {contrato}", font=('Segoe UI', 9), bg='#f8f9fa').pack()
        tk.Label(info_frame, text=f"Total: {len(seriales)} equipos", font=('Segoe UI', 9, 'bold'), 
                 fg=Styles.SUCCESS_COLOR, bg='#f8f9fa').pack()
        
        # Lista con scroll
        list_frame = tk.Frame(popup, bg='white', pady=10)
        list_frame.pack(fill='both', expand=True, padx=20)
        
        listbox = tk.Listbox(list_frame, font=('Consolas', 10), relief='flat', 
                            highlightthickness=1, borderwidth=1)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        for s in sorted(seriales):
            listbox.insert(tk.END, f"  • {s}")
        
        tk.Button(popup, text="Cerrar", command=popup.destroy, bg=Styles.SECONDARY_COLOR, 
                  fg='white', font=('Segoe UI', 10, 'bold'), pady=8).pack(fill='x', padx=20, pady=15)
