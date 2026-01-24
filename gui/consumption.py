import tkinter as tk
from tkinter import ttk
from .styles import Styles
from .utils import mostrar_mensaje_emergente
from database import (
    obtener_nombres_moviles,
    obtener_asignacion_movil,
    registrar_movimiento_gui
)
from datetime import date

class ConsumoTecnicoWindow(tk.Toplevel):
    """
    Ventana para registrar el consumo real realizado por un técnico desde su móvil (Punto 3).
    """
    def __init__(self, master, refresh_callback=None):
        super().__init__(master)
        self.title("📥 Registro de Consumo de Técnico")
        self.geometry("900x700")
        self.configure(bg='#f8f9fa')
        self.grab_set()
        self.refresh_callback = refresh_callback
        
        self.entries = {}
        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self, bg=Styles.INFO_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📥 REGISTRO DE CONSUMO REAL", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.INFO_COLOR, fg='white').pack(pady=20)
        
        # Frame de selección
        frame_selector = tk.Frame(self, padx=20, pady=20, bg='#E1F5FE')
        frame_selector.pack(fill='x')
        
        tk.Label(frame_selector, text="Móvil del Técnico:", font=('Segoe UI', 10, 'bold'), bg='#E1F5FE').pack(side=tk.LEFT)
        self.movil_combo = ttk.Combobox(frame_selector, values=obtener_nombres_moviles(), state="readonly", width=25)
        self.movil_combo.set("--- Seleccionar Móvil ---")
        self.movil_combo.pack(side=tk.LEFT, padx=10)
        self.movil_combo.bind("<<ComboboxSelected>>", self.cargar_productos_movil)
        
        tk.Label(frame_selector, text="Referencia (Ticket/Acta):", font=('Segoe UI', 10, 'bold'), bg='#E1F5FE').pack(side=tk.LEFT, padx=(20, 5))
        self.ticket_entry = tk.Entry(frame_selector, width=20, font=('Segoe UI', 10))
        self.ticket_entry.pack(side=tk.LEFT, padx=10)
        
        # Canvas para scroll de productos
        self.canvas = tk.Canvas(self, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.frame_productos = tk.Frame(self.canvas, bg='#f8f9fa', padx=20)
        
        self.canvas.create_window((0, 0), window=self.frame_productos, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        self.frame_productos.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Footer
        footer = tk.Frame(self, bg='#f8f9fa', pady=15)
        footer.pack(fill='x')
        
        tk.Button(footer, text="✅ Procesar Consumo", command=self.procesar_consumo,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                 relief='flat', padx=30, pady=10).pack()

    def cargar_productos_movil(self, event=None):
        movil = self.movil_combo.get()
        if movil == "--- Seleccionar Móvil ---": return
        
        # Limpiar
        for widget in self.frame_productos.winfo_children():
            widget.destroy()
        self.entries.clear()
        
        productos = obtener_asignacion_movil(movil)
        
        if not productos:
            tk.Label(self.frame_productos, text="El móvil no tiene productos asignados actualmente.", 
                    font=('Segoe UI', 11), bg='#f8f9fa', fg='red').pack(pady=50)
            return

        # Encabezados
        header_grid = tk.Frame(self.frame_productos, bg='#f8f9fa')
        header_grid.pack(fill='x', pady=10)
        
        tk.Label(header_grid, text="PRODUCTO / SKU", font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', width=50, anchor='w').grid(row=0, column=0)
        tk.Label(header_grid, text="EN MÓVIL", font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', width=15).grid(row=0, column=1)
        tk.Label(header_grid, text="CANT. USADA", font=('Segoe UI', 9, 'bold'), bg='#f8f9fa', width=15).grid(row=0, column=2)

        for i, (nombre, sku, cantidad) in enumerate(productos):
            row_frame = tk.Frame(self.frame_productos, bg='white' if i % 2 == 0 else '#f1f1f1', pady=5)
            row_frame.pack(fill='x')
            
            tk.Label(row_frame, text=f"{nombre}\n({sku})", font=('Segoe UI', 9), bg=row_frame['bg'], width=50, anchor='w', justify='left').pack(side=tk.LEFT)
            tk.Label(row_frame, text=str(cantidad), font=('Segoe UI', 10, 'bold'), bg=row_frame['bg'], width=15, fg='#1976D2').pack(side=tk.LEFT)
            
            entry = tk.Entry(row_frame, width=10, font=('Segoe UI', 10), justify='center')
            entry.pack(side=tk.LEFT, padx=25)
            self.entries[sku] = (entry, cantidad)

    def procesar_consumo(self):
        movil = self.movil_combo.get()
        ticket = self.ticket_entry.get().strip()
        
        if movil == "--- Seleccionar Móvil ---":
            mostrar_mensaje_emergente(self, "Error", "Debe seleccionar un móvil.", "error")
            return
            
        exitos = 0
        error_msgs = []
        
        for sku, (entry, stock_movil) in self.entries.items():
            cant_text = entry.get().strip()
            if not cant_text: continue
            
            try:
                cantidad = int(cant_text)
                if cantidad <= 0: continue
                
                if cantidad > stock_movil:
                    error_msgs.append(f"SKU {sku}: No puedes consumir {cantidad} si solo quedan {stock_movil}")
                    continue
                
                obs = f"Consumo Técnico - Ref: {ticket}" if ticket else "Consumo Técnico"
                exito, mensaje = registrar_movimiento_gui(sku, 'CONSUMO_MOVIL', cantidad, movil, date.today().isoformat(), None, obs)
                
                if exito: exitos += 1
                else: error_msgs.append(f"SKU {sku}: {mensaje}")
                
            except ValueError:
                error_msgs.append(f"SKU {sku}: Cantidad no válida")

        if exitos > 0:
            mostrar_mensaje_emergente(self, "Éxito", f"Se registraron {exitos} consumos correctamente.", "success")
            if self.refresh_callback: self.refresh_callback()
            self.destroy()
        elif error_msgs:
            mostrar_mensaje_emergente(self, "Errores", "\n".join(error_msgs), "error")
        else:
            mostrar_mensaje_emergente(self, "Aviso", "No se ingresó ningún consumo para procesar.", "info")
