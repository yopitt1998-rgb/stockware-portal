import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import date
import json

from database import (
    obtener_todos_los_skus_para_movimiento,
    registrar_consumo_directo,
    obtener_nombres_moviles,
    obtener_info_serial,
    logger
)
from config import COLORS, MOVILES_SANTIAGO, PRODUCTOS_CON_CODIGO_BARRA

class SantiagoConsumoTab:
    def __init__(self, master, app_instance):
        self.master = master
        self.app = app_instance
        self.setup_ui()
        self.cargar_datos_iniciales()

    def setup_ui(self):
        # Main container with padding (using tk.Frame instead of ttk to control bg easily)
        self.main_frame = tk.Frame(self.master, bg='#f8f9fa', padx=20, pady=20)
        self.main_frame.pack(fill='both', expand=True)

        # Header custom card
        header = tk.Frame(self.main_frame, bg='white', relief='flat', pady=15, padx=20)
        header.pack(fill='x', pady=(0, 20))
        
        header_text = tk.Frame(header, bg='white')
        header_text.pack(side='left')
        
        tk.Label(header_text, text="⚡ Registro de Consumo Directo", 
                 font=('Segoe UI', 18, 'bold'), bg='white', fg=COLORS['primary']).pack(anchor='w')
        tk.Label(header_text, text="Modelo Santiago: Descuento inmediato de stock de bodega", 
                 font=('Segoe UI', 9), bg='white', fg='gray').pack(anchor='w')

        # Form Layer - Panel de datos del servicio
        form_frame = tk.LabelFrame(self.main_frame, text=" Datos del Técnico / Servicio ", 
                                  bg='white', font=('Segoe UI', 10, 'bold'), padx=20, pady=20)
        form_frame.pack(fill='x')

        # Grid config
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        # Mobile Selection
        tk.Label(form_frame, text="Móvil:", font=('Segoe UI', 10), bg='white').grid(row=0, column=0, sticky='w', pady=10)
        self.movil_combo = ttk.Combobox(form_frame, values=MOVILES_SANTIAGO, state='readonly', font=('Segoe UI', 10))
        self.movil_combo.grid(row=0, column=1, padx=10, pady=10, sticky='ew')
        if MOVILES_SANTIAGO: self.movil_combo.current(0)

        # Tech Details
        tk.Label(form_frame, text="Técnico:", font=('Segoe UI', 10), bg='white').grid(row=1, column=0, sticky='w', pady=10)
        self.tecnico_entry = ttk.Entry(form_frame, font=('Segoe UI', 10))
        self.tecnico_entry.grid(row=1, column=1, padx=10, pady=10, sticky='ew')

        # Contract Details
        tk.Label(form_frame, text="Contrato / Ticket:", font=('Segoe UI', 10), bg='white').grid(row=0, column=2, sticky='w', padx=(40, 0), pady=10)
        self.ticket_entry = ttk.Entry(form_frame, font=('Segoe UI', 10))
        self.ticket_entry.grid(row=0, column=3, padx=10, pady=10, sticky='ew')

        # Observations
        tk.Label(form_frame, text="Observaciones:", font=('Segoe UI', 10), bg='white').grid(row=1, column=2, sticky='w', padx=(40, 0), pady=10)
        self.obs_entry = ttk.Entry(form_frame, font=('Segoe UI', 10))
        self.obs_entry.grid(row=1, column=3, padx=10, pady=10, sticky='ew')

        # Search Layer
        search_panel = tk.Frame(self.main_frame, bg='#f8f9fa')
        search_panel.pack(fill='x', pady=(20, 5))
        
        tk.Label(search_panel, text=" Buscar Material: ", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filtrar_productos)
        self.search_entry = ttk.Entry(search_panel, textvariable=self.search_var, font=('Segoe UI', 12))
        self.search_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.search_entry.focus_set()

        # Treeview for Products in Warehouse
        tree_frame = tk.Frame(self.main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('Nombre', 'SKU', 'Stock disponible', 'Categoría')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse', style='Modern.Treeview')
        
        for col in columns: 
            self.tree.heading(col, text=col)
        
        self.tree.column('Nombre', width=400)
        self.tree.column('SKU', width=120)
        self.tree.column('Stock disponible', width=120, anchor='center')
        self.tree.column('Categoría', width=150, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.tree.bind('<Double-1>', lambda e: self.abrir_ventana_accion())

        # Footer / Legend
        footer = tk.Frame(self.main_frame, bg='#f8f9fa')
        footer.pack(fill='x', pady=5)
        tk.Label(footer, text="💡 Tip: Haga doble click sobre un producto para registrar su consumo.", 
                 bg='#f8f9fa', fg='#7f8c8d', font=('Segoe UI', 9, 'italic')).pack(side='left')
        
        btn_refresh = tk.Button(footer, text="🔄 Actualizar Stock", command=self.cargar_datos_iniciales,
                               bg=COLORS['secondary'], fg='white', font=('Segoe UI', 9, 'bold'),
                               relief='flat', padx=15, pady=5, cursor='hand2')
        btn_refresh.pack(side='right')

    def cargar_datos_iniciales(self):
        try:
            self.all_products = obtener_todos_los_skus_para_movimiento() # Retorna (nombre, sku, cant)
            self.filtrar_productos()
        except Exception as e:
            logger.error(f"Error cargando stock Santiago: {e}")

    def filtrar_productos(self, *args):
        search_term = self.search_var.get().lower()
        for item in self.tree.get_children(): self.tree.delete(item)
        
        for p in self.all_products:
            nombre, sku, cant = p
            es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA
            cat = "EQUIPO (Escaneo)" if es_equipo else "MATERIAL (Cantidad)"
            
            if search_term in nombre.lower() or search_term in sku.lower():
                tag = 'equipo' if es_equipo else 'material'
                self.tree.insert('', 'end', values=(nombre, sku, cant, cat), tags=(tag,))
        
        # Estilos visuales para el árbol
        self.tree.tag_configure('equipo', foreground='#2980b9')

    def abrir_ventana_accion(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Seleccione un producto de la lista.")
            return
        
        nombre, sku, stock, cat = self.tree.item(selected)['values']
        movil = self.movil_combo.get()
        tecnico = self.tecnico_entry.get().strip()
        ticket = self.ticket_entry.get().strip()

        if not tecnico or not ticket:
            messagebox.showwarning("Campos Requeridos", "Debe completar el Técnico y el Ticket/Contrato antes de registrar.")
            self.tecnico_entry.focus_set()
            return

        self.ventana_consumo(sku, nombre, stock, movil, tecnico, ticket)

    def ventana_consumo(self, sku, nombre, stock, movil, tecnico, ticket):
        vent = tk.Toplevel(self.app.master)
        vent.title(f"Registrar Consumo")
        vent.geometry("500x380")
        vent.configure(bg='white')
        vent.resizable(False, False)
        vent.transient(self.app.master)
        vent.grab_set()

        # Centrar
        x = vent.master.winfo_x() + (vent.master.winfo_width()//2) - (500//2)
        y = vent.master.winfo_y() + (vent.master.winfo_height()//2) - (380//2)
        vent.geometry(f"+{x}+{y}")

        main = tk.Frame(vent, bg='white', padx=30, pady=30)
        main.pack(fill='both', expand=True)

        tk.Label(main, text=f"Confirmar Consumo Directo", font=('Segoe UI', 10), bg='white').pack()
        tk.Label(main, text=f"{nombre}", font=('Segoe UI', 14, 'bold'), 
                 bg='white', fg=COLORS['primary'], wraplength=400).pack(pady=10)
        
        info_frame = tk.Frame(main, bg='#f8f9fa', padx=10, pady=10)
        info_frame.pack(fill='x', pady=5)
        tk.Label(info_frame, text=f"Móvil: {movil}  |  Stock Bodega: {stock}", 
                 font=('Segoe UI', 10), bg='#f8f9fa').pack()

        es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA

        if es_equipo:
            tk.Label(main, text=" ESCANEE EL SERIAL / MAC: ", font=('Segoe UI', 11, 'bold'), 
                     bg='white', pady=10).pack()
            
            serial_entry = ttk.Entry(main, font=('Segoe UI', 14))
            serial_entry.pack(fill='x', pady=5)
            serial_entry.focus_set()
            
            def procesar_equipo(event=None):
                sn = serial_entry.get().strip().upper()
                if not sn: return
                
                # Validar serial
                sku_db, loc = obtener_info_serial(sn)
                if not sku_db:
                    messagebox.showerror("Error", f"El serial '{sn}' no existe en la base de datos.")
                    serial_entry.delete(0, tk.END)
                    return
                if sku_db != sku:
                    messagebox.showerror("Error", f"Este serial pertenece a un {sku_db}, no al producto seleccionado.")
                    return
                if loc != 'BODEGA':
                    messagebox.showerror("No Disponible", f"Este equipo está registrado en: {loc}.\nSolo puede consumir equipos en BODEGA.")
                    return
                
                # Ejecutar
                exito, msg = registrar_consumo_directo(
                    sku=sku, cantidad=1, movil=movil, tecnico=tecnico, 
                    ticket=ticket, seriales=[sn], observaciones=self.obs_entry.get()
                )
                if exito:
                    vent.destroy()
                    messagebox.showinfo("Éxito", msg)
                    self.cargar_datos_iniciales()
                else:
                    messagebox.showerror("Error", msg)

            btn = tk.Button(main, text="✅ REGISTRAR CONSUMO EQUIPO", command=procesar_equipo,
                      bg=COLORS['success'], fg='white', font=('Segoe UI', 11, 'bold'),
                      relief='flat', pady=12, cursor='hand2')
            btn.pack(fill='x', pady=20)
            vent.bind('<Return>', procesar_equipo)
            
        else:
            tk.Label(main, text=" CANTIDAD A CONSUMIR: ", font=('Segoe UI', 11, 'bold'), 
                     bg='white', pady=10).pack()
            
            cant_entry = ttk.Entry(main, font=('Segoe UI', 14), justify='center')
            cant_entry.insert(0, "1")
            cant_entry.pack(pady=5)
            cant_entry.focus_set()
            cant_entry.selection_range(0, tk.END)

            def procesar_material(event=None):
                try:
                    qty = int(cant_entry.get())
                    if qty <= 0: raise ValueError()
                    if qty > stock:
                        if not messagebox.askyesno("Stock Insuficiente", f"La bodega solo tiene {stock} unidades. ¿Desea forzar el consumo de {qty}?"):
                            return
                except ValueError:
                    messagebox.showerror("Error", "Ingrese una cantidad numérica válida.")
                    return
                
                # Ejecutar
                exito, msg = registrar_consumo_directo(
                    sku=sku, cantidad=qty, movil=movil, tecnico=tecnico, 
                    ticket=ticket, observaciones=self.obs_entry.get()
                )
                if exito:
                    vent.destroy()
                    messagebox.showinfo("Éxito", msg)
                    self.cargar_datos_iniciales()
                    self.search_entry.focus_set()
                    self.search_var.set("") # Limpiar búsqueda
                else:
                    messagebox.showerror("Error", msg)

            btn = tk.Button(main, text="✅ REGISTRAR CONSUMO MATERIAL", command=procesar_material,
                      bg=COLORS['success'], fg='white', font=('Segoe UI', 11, 'bold'),
                      relief='flat', pady=12, cursor='hand2')
            btn.pack(fill='x', pady=20)
            vent.bind('<Return>', procesar_material)
