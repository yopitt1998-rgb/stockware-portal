import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime

from database import (
    obtener_todos_los_skus_para_movimiento,
    obtener_info_serial,
    logger
)
from config import COLORS, PRODUCTOS_CON_CODIGO_BARRA

class SantiagoAuditPhysTab:
    def __init__(self, master, app_instance):
        self.master = master
        self.app = app_instance
        self.conteo_fisico = {} # {sku: {'nombre': str, 'cantidad': int, 'seriales': set}}
        self.setup_ui()

    def setup_ui(self):
        # Main container
        self.main_frame = tk.Frame(self.master, bg='#f8f9fa', padx=20, pady=20)
        self.main_frame.pack(fill='both', expand=True)

        # Header
        header = tk.Frame(self.main_frame, bg='white', relief='flat', pady=15, padx=20)
        header.pack(fill='x', pady=(0, 20))
        
        tk.Label(header, text="🔫 Auditoría Física (Conteo Ciego)", 
                 font=('Segoe UI', 18, 'bold'), bg='white', fg='#455A64').pack(anchor='w')
        tk.Label(header, text="Escanee todos los productos físicos. Luego presione 'Comparar' para ver diferencias con el sistema.", 
                 font=('Segoe UI', 9), bg='white', fg='gray').pack(anchor='w')

        # Control Panel (Scanning)
        scan_panel = tk.Frame(self.main_frame, bg='white', padx=20, pady=20)
        scan_panel.pack(fill='x')

        tk.Label(scan_panel, text="Escanee SKU o Serial:", font=('Segoe UI', 11, 'bold'), bg='white').pack(side='left', padx=(0, 10))
        
        self.scan_var = tk.StringVar()
        self.scan_entry = ttk.Entry(scan_panel, textvariable=self.scan_var, font=('Segoe UI', 12), width=40)
        self.scan_entry.pack(side='left', padx=10)
        self.scan_entry.focus_set()
        self.scan_entry.bind('<Return>', lambda e: self.procesar_escaneo())

        tk.Button(scan_panel, text="COMPARAR CON SISTEMA", command=self.realizar_comparacion,
                  bg='#2E7D32', fg='white', font=('Segoe UI', 10, 'bold'), relief='flat', padx=20, pady=8).pack(side='right')

        tk.Button(scan_panel, text="Limpiar Conteo", command=self.limpiar_conteo,
                  bg='#e0e0e0', font=('Segoe UI', 9), relief='flat', padx=10).pack(side='right', padx=10)

        # Split View: Left (Scanned) | Right (Comparison Result)
        paned = ttk.PanedWindow(self.main_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, pady=10)

        # Left: Physical Count
        left_frame = tk.Frame(paned, bg='white')
        paned.add(left_frame, weight=1)
        
        tk.Label(left_frame, text="📦 Conteo Físico Actual", font=('Segoe UI', 10, 'bold'), bg='white', pady=5).pack(anchor='w', padx=10)
        
        cols_scanned = ('SKU', 'Nombre', 'Cantidad', 'Seriales')
        self.tree_scanned = ttk.Treeview(left_frame, columns=cols_scanned, show='headings', height=10)
        for col in cols_scanned: self.tree_scanned.heading(col, text=col)
        self.tree_scanned.column('SKU', width=100)
        self.tree_scanned.column('Nombre', width=250)
        self.tree_scanned.column('Cantidad', width=80, anchor='center')
        self.tree_scanned.pack(fill='both', expand=True, padx=5, pady=5)

        # Right: Discrepancies
        right_frame = tk.Frame(paned, bg='white')
        paned.add(right_frame, weight=1)
        
        tk.Label(right_frame, text="📊 Discrepancias (Sistema vs Físico)", font=('Segoe UI', 10, 'bold'), bg='white', pady=5).pack(anchor='w', padx=10)
        
        cols_diff = ('SKU', 'Sistema', 'Físico', 'Diferencia', 'Estado')
        self.tree_diff = ttk.Treeview(right_frame, columns=cols_diff, show='headings', height=10)
        for col in cols_diff: self.tree_diff.heading(col, text=col)
        self.tree_diff.column('Sistema', width=80, anchor='center')
        self.tree_diff.column('Físico', width=80, anchor='center')
        self.tree_diff.column('Diferencia', width=80, anchor='center')
        self.tree_diff.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tree_diff.tag_configure('missing', foreground='red')
        self.tree_diff.tag_configure('extra', foreground='blue')
        self.tree_diff.tag_configure('ok', foreground='green')

    def procesar_escaneo(self):
        val = self.scan_var.get().strip().upper()
        self.scan_var.set("")
        if not val: return

        # 1. ¿Es un serial/MAC?
        sku_found, loc = obtener_info_serial(val)
        if sku_found:
            self.registrar_item_conteo(sku_found, serial=val)
            return

        # 2. ¿Es un SKU? (Busca en cache de productos)
        # Cargamos productos si no los tenemos
        if not hasattr(self, 'all_products_cache'):
            self.all_products_cache = {p[1]: p[0] for p in obtener_todos_los_skus_para_movimiento()}
        
        if val in self.all_products_cache:
            self.registrar_item_conteo(val)
        else:
            messagebox.showwarning("No Encontrado", f"El valor '{val}' no corresponde a un SKU o Serial válido.")

    def registrar_item_conteo(self, sku, serial=None):
        # Obtener nombre si es nuevo
        if sku not in self.conteo_fisico:
            nombre = "Desconocido"
            if hasattr(self, 'all_products_cache'):
                nombre = self.all_products_cache.get(sku, "Producto")
            else:
                p_list = obtener_todos_los_skus_para_movimiento()
                self.all_products_cache = {p[1]: p[0] for p in p_list}
                nombre = self.all_products_cache.get(sku, "Producto")
            
            self.conteo_fisico[sku] = {
                'nombre': nombre,
                'cantidad': 0,
                'seriales': set()
            }

        data = self.conteo_fisico[sku]
        
        if serial:
            if serial in data['seriales']:
                messagebox.showinfo("Duplicado", f"El serial {serial} ya fue escaneado.")
                return
            data['seriales'].add(serial)
            data['cantidad'] += 1
        else:
            # Material normal, sumamos 1 (o preguntar cantidad)
            data['cantidad'] += 1

        self.actualizar_tabla_conteo()

    def actualizar_tabla_conteo(self):
        for item in self.tree_scanned.get_children(): self.tree_scanned.delete(item)
        for sku, data in self.conteo_fisico.items():
            txt_seriales = ", ".join(list(data['seriales'])[:3]) + ("..." if len(data['seriales']) > 3 else "")
            self.tree_scanned.insert('', 'end', values=(sku, data['nombre'], data['cantidad'], txt_seriales))

    def realizar_comparacion(self):
        if not self.conteo_fisico:
            messagebox.showwarning("Vacio", "No hay nada escaneado para comparar.")
            return

        # Obtener stock actual del sistema
        try:
            stock_sistema = {p[1]: p[2] for p in obtener_todos_los_skus_para_movimiento()}
            
            for item in self.tree_diff.get_children(): self.tree_diff.delete(item)
            
            # Unir todos los SKUs (de sistema y de conteo físico)
            todos_skus = set(stock_sistema.keys()) | set(self.conteo_fisico.keys())
            
            for sku in sorted(list(todos_skus)):
                cant_sys = stock_sistema.get(sku, 0)
                cant_phys = self.conteo_fisico.get(sku, {}).get('cantidad', 0)
                diff = cant_phys - cant_sys
                
                estado = "CORRECTO"
                tag = 'ok'
                if diff < 0:
                    estado = f"FALTAN {abs(diff)}"
                    tag = 'missing'
                elif diff > 0:
                    estado = f"SOBRAN {diff}"
                    tag = 'extra'
                
                # Solo mostrar si hay diferencia o si el usuario quiere ver todo? 
                # Por ahora mostramos discrepancias únicamente para limpiar la vista, o todo si el físico tiene algo.
                if cant_sys > 0 or cant_phys > 0:
                    self.tree_diff.insert('', 'end', 
                                         values=(sku, cant_sys, cant_phys, diff, estado), 
                                         tags=(tag,))
            
            messagebox.showinfo("Auditoría", "Comparación completada.")
            
        except Exception as e:
            logger.error(f"Error en auditoría física: {e}")
            messagebox.showerror("Error", "No se pudo obtener el stock del sistema.")

    def limpiar_conteo(self):
        if messagebox.askyesno("Limpiar", "¿Desea borrar todo el conteo actual?"):
            self.conteo_fisico = {}
            for item in self.tree_scanned.get_children(): self.tree_scanned.delete(item)
            for item in self.tree_diff.get_children(): self.tree_diff.delete(item)
            self.scan_entry.focus_set()
