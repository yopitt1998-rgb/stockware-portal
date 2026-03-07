import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime

from database import obtener_historial_completo, buscar_equipo_global, logger
from gui.styles import Styles

class HistoryLogTab(tk.Frame):
    def __init__(self, notebook, main_app):
        super().__init__(notebook, bg='#f8f9fa')
        self.notebook = notebook
        self.main_app = main_app
        self.setup_ui()
        self.refresh_historial()

    def setup_ui(self):
        # --- CONTENEDOR CON SCROLL (Para todo el Tab) ---
        self.canvas = tk.Canvas(self, bg='#f8f9fa', highlightthickness=0)
        self.scrollbar_v = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#f8f9fa')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Crear ventana en canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Ajustar ancho del frame al ancho del canvas
        def _on_canvas_configure(e):
            self.canvas.itemconfig(self.canvas_window, width=e.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        self.canvas.configure(yscrollcommand=self.scrollbar_v.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar_v.pack(side="right", fill="y")

        # --- BUSCADOR GLOBAL (TOP) ---
        search_panel = tk.Frame(self.scrollable_frame, bg='white', relief='flat', padx=20, pady=20)
        search_panel.pack(fill='x', padx=20, pady=10)
        
        tk.Label(search_panel, text="🔍 BUSCADOR DE EQUIPO (MAC / SERIAL):", 
                 font=('Segoe UI', 11, 'bold'), bg='white', fg=Styles.PRIMARY_COLOR).pack(side='left')
        
        self.mac_search_var = tk.StringVar()
        self.mac_search_entry = ttk.Entry(search_panel, textvariable=self.mac_search_var, font=('Segoe UI', 12), width=35)
        self.mac_search_entry.pack(side='left', padx=15)
        self.mac_search_entry.bind('<Return>', lambda e: self.search_mac())
        
        btn_search = tk.Button(search_panel, text="BUSCAR ESTADO", command=self.search_mac,
                               bg=Styles.PRIMARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                               relief='flat', padx=15, pady=5)
        btn_search.pack(side='left')

        # --- PANEL DE RESULTADO MAC (FIX 6: Empacado en orden pero oculto) ---
        self.result_frame = tk.Frame(self.scrollable_frame, bg='#e3f2fd', highlightbackground='#90caf9', highlightthickness=1)
        # Se mantiene sin widgets y sin pack visible hasta la búsqueda

        # --- SECCIÓN HISTORIAL ---
        history_panel = tk.Frame(self.scrollable_frame, bg='white', padx=20, pady=10)
        history_panel.pack(fill='both', expand=True, padx=20, pady=10)
        
        header_h = tk.Frame(history_panel, bg='white')
        header_h.pack(fill='x', pady=(0, 10))
        
        tk.Label(header_h, text="📜 HISTORIAL DE MOVIMIENTOS", 
                 font=('Segoe UI', 12, 'bold'), bg='white', fg=Styles.DARK_TEXT).pack(side='left')
        
        # Filtro de texto para el historial
        self.hist_filter_var = tk.StringVar()
        self.hist_filter_entry = ttk.Entry(header_h, textvariable=self.hist_filter_var, font=('Segoe UI', 10), width=30)
        self.hist_filter_entry.pack(side='right', padx=10)
        self.hist_filter_entry.bind('<KeyRelease>', lambda e: self.refresh_historial())
        tk.Label(header_h, text="Filtrar:", bg='white').pack(side='right')

        # Tabla de historial con scrollbars
        self.tree_container = tk.Frame(history_panel, bg='white')
        self.tree_container.pack(fill='both', expand=True)
        
        cols = ("ID", "Fecha/Hora", "Tipo", "Producto", "Cant.", "Destino/Detalle", "Observaciones")
        self.tree = ttk.Treeview(self.tree_container, columns=cols, show='headings', style='Modern.Treeview', height=15)
        
        for col in cols: self.tree.heading(col, text=col)
        self.tree.column("ID", width=60, anchor='center')
        self.tree.column("Fecha/Hora", width=150, anchor='center')
        self.tree.column("Tipo", width=150)
        self.tree.column("Producto", width=250)
        self.tree.column("Cant.", width=60, anchor='center')
        self.tree.column("Destino/Detalle", width=150)
        self.tree.column("Observaciones", width=300)
        
        # Scrollbars locales para el treeview
        scroll_y = ttk.Scrollbar(self.tree_container, orient='vertical', command=self.tree.yview)
        scroll_x = ttk.Scrollbar(history_panel, orient='horizontal', command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        # Layout del container del Tree
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        self.tree_container.columnconfigure(0, weight=1)
        self.tree_container.rowconfigure(0, weight=1)
        
        scroll_x.pack(side='bottom', fill='x')

    def search_mac(self):
        term = self.mac_search_var.get().strip()
        if not term: return

        # Limpiar panel anterior
        for widget in self.result_frame.winfo_children(): widget.destroy()
        self.result_frame.pack_forget()

        res = buscar_equipo_global(term)
        
        self.result_frame.pack(fill='x', padx=20, pady=5, after=self.scrollable_frame.winfo_children()[0])
        
        if not res:
            tk.Label(self.result_frame, text=f"❌ No se encontró ningún equipo con MAC/Serial: {term}", 
                     font=('Segoe UI', 10, 'bold'), bg='#ffebee', fg='#c62828', pady=10).pack()
            return

        # Ahora res tiene 9 elementos si se encontró algo extendido
        sn, mac, sku, nombre, ubicacion, estado, paquete, *extra = res
        movil_c = extra[0] if len(extra) > 0 else None
        contrato_c = extra[1] if len(extra) > 1 else None
        
        # Formatear ubicación para el usuario
        color_status = '#2e7d32' # Verde (OK)
        if ubicacion == 'CONSUMIDO':
            disp_loc = "🏠 CONSUMIDO / INSTALADO"
            color_status = '#1565c0'
        elif ubicacion == 'DESCARTE':
            disp_loc = "⚠️ DAÑADO / DESCARTE"
            color_status = '#c62828'
        elif ubicacion == 'BODEGA':
            disp_loc = "🏢 BODEGA (Disponible)"
        else:
            disp_loc = f"🚚 MOVIL: {ubicacion}"
            color_status = '#ef6c00'

        content = tk.Frame(self.result_frame, bg='#e3f2fd', padx=20, pady=15)
        content.pack(fill='x')
        
        l_info = tk.Label(content, text=f"📍 ESTADO ACTUAL: {disp_loc}", font=('Segoe UI', 14, 'bold'), bg='#e3f2fd', fg=color_status)
        l_info.grid(row=0, column=0, columnspan=2, sticky='w')
        
        tk.Label(content, text=f"Producto: {nombre} ({sku})", font=('Segoe UI', 11), bg='#e3f2fd').grid(row=1, column=0, sticky='w', pady=2)
        tk.Label(content, text=f"Serial: {sn} | MAC: {mac}", font=('Segoe UI', 11), bg='#e3f2fd').grid(row=2, column=0, sticky='w', pady=2)
        
        # MOSTRAR CONTRATO Y MOVIL CON ESTILO DESTACADO
        if contrato_c:
             extra_frame = tk.Frame(content, bg='white', highlightbackground="#1a237e", highlightthickness=1, padx=10, pady=5)
             extra_frame.grid(row=3, column=0, columnspan=2, sticky='we', pady=(10, 0))
             
             tk.Label(extra_frame, text=f"📄 CONTRATO: {contrato_c}", 
                      font=('Segoe UI', 12, 'bold'), bg='white', fg='#1a237e').pack(side='left', padx=10)
             tk.Label(extra_frame, text=f"🔧 MÓVIL: {movil_c}", 
                      font=('Segoe UI', 12, 'bold'), bg='white', fg='#1a237e').pack(side='left', padx=10)
        
        if paquete and paquete != 'NINGUNO':
            # Moverlo a la derecha del estado actual
            tk.Label(content, text=f"📦 Paquete: {paquete}", font=('Segoe UI', 11, 'bold'), bg='#e3f2fd', fg='#4527a0').grid(row=0, column=1, sticky='e', padx=20)
        
        # AUTO-FILTRAR EL HISTORIAL DE ABAJO PARA ESTE SERIAL (NUEVO)
        self.hist_filter_var.set(sn if sn else mac)
        
        # Guardar contexto para búsqueda inteligente si el historial sale vacío
        self.current_search_sku = sku
        self.current_search_paquete = paquete
        
        self.refresh_historial()

        # Forzar actualización del canvas para mostrar el nuevo resultado
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def refresh_historial(self):
        filter_t = self.hist_filter_var.get()
        
        def _load():
            # PLAN A: Búsqueda por serial/texto
            data = obtener_historial_completo(limite=300, filtro_texto=filter_t)
            
            # PLAN B (Inteligente): Si no hay nada por serial y tenemos SKU/Paquete, buscar por SKU y Paquete
            if not data and hasattr(self, 'current_search_sku') and self.current_search_sku:
                # Intentamos buscar por SKU y Paquete en las observaciones o doc_ref
                # Esto es más útil que dejar la tabla vacía
                data = obtener_historial_completo(limite=50, filtro_texto=self.current_search_sku)
                # Filtrar en Python para mayor precisión si se desea, o dejarlo así para que vea el contexto
            
            # Use main_app.master instead of just self to ensure after is called on a valid root/top
            try: self.main_app.master.after(0, lambda: self._update_tree(data))
            except: pass
            
        threading.Thread(target=_load, daemon=True).start()

    def _update_tree(self, data):
        # Verificar si el widget aún existe antes de actualizar
        if not self.tree.winfo_exists(): return
        for i in self.tree.get_children(): self.tree.delete(i)
        for row in data:
            self.tree.insert('', 'end', values=row)
