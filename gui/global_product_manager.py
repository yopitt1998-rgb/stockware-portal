import tkinter as tk
from tkinter import ttk, messagebox
from data_layer.inventory import obtener_skus_globales, anadir_producto_global, eliminar_producto_global, obtener_todos_los_skus_para_movimiento
from .styles import Styles

class GlobalProductManagerDialog:
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Administrar Asignación Global")
        self.dialog.geometry("600x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.configure(bg='#f8f9fa')
        
        self.skus_globales = set(obtener_skus_globales())
        self.all_products = obtener_todos_los_skus_para_movimiento() # [(nombre, sku, cant), ...]
        
        self.create_widgets()
        self.actualizar_lista()

    def create_widgets(self):
        # Header
        header = tk.Frame(self.dialog, bg=Styles.PRIMARY_COLOR, height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(header, text="🌐 Asignación Global de Productos", font=('Segoe UI', 13, 'bold'), 
                 fg='white', bg=Styles.PRIMARY_COLOR).pack(pady=15)

        # Main Content
        content = tk.Frame(self.dialog, bg='#f8f9fa', padx=20, pady=20)
        content.pack(fill='both', expand=True)

        tk.Label(content, text="Los productos marcados aquí se compartirán automáticamente\ncon todos los móviles reflejando el stock total de bodega.", 
                 font=('Segoe UI', 9), bg='#f8f9fa', justify='center', fg='#666').pack(pady=(0, 20))

        # Selector Row
        sel_frame = tk.Frame(content, bg='#f8f9fa')
        sel_frame.pack(fill='x', pady=5)
        
        tk.Label(sel_frame, text="Buscar Producto:", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(side='left')
        
        # Product Search / Combo
        prod_options = [f"{sku} | {nombre}" for nombre, sku, cant in self.all_products]
        self.prod_var = tk.StringVar()
        self.combo_prod = ttk.Combobox(sel_frame, textvariable=self.prod_var, values=prod_options, width=40, state='readonly')
        self.combo_prod.pack(side='left', padx=10)
        
        tk.Button(sel_frame, text="➕ Agregar", command=self.agregar_global,
                  bg=Styles.SUCCESS_COLOR, fg='white', relief='flat', padx=10).pack(side='left')

        # List of Current Globals
        tk.Label(content, text="Productos con Asignación Global Activa:", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(20, 5))
        
        list_frame = tk.Frame(content, bg='white', highlightthickness=1, highlightbackground='#ddd')
        list_frame.pack(fill='both', expand=True)
        
        self.tree = ttk.Treeview(list_frame, columns=("SKU", "Nombre"), show='headings', height=8)
        self.tree.heading("SKU", text="SKU")
        self.tree.heading("Nombre", text="Producto")
        self.tree.column("SKU", width=100)
        self.tree.column("Nombre", width=350)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Action Buttons
        btn_frame = tk.Frame(content, bg='#f8f9fa')
        btn_frame.pack(fill='x', pady=(15, 0))
        
        tk.Button(btn_frame, text="🗑️ Quitar Asignación Global", command=self.quitar_global,
                  bg=Styles.ACCENT_COLOR, fg='white', relief='flat', padx=20, pady=8).pack(side='left')
        
        tk.Button(btn_frame, text="Cerrar", command=self.dialog.destroy,
                  bg='#95a5a6', fg='white', relief='flat', padx=20, pady=8).pack(side='right')

    def actualizar_lista(self):
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Refetch (just in case)
        self.skus_globales = set(obtener_skus_globales())
        
        # Map SKU to Name for better display
        map_names = {sku: nombre for nombre, sku, cant in self.all_products}
        
        for sku in sorted(self.skus_globales):
            self.tree.insert("", "end", values=(sku, map_names.get(sku, "Desconocido")))

    def agregar_global(self):
        val = self.prod_var.get()
        if not val: return
        
        sku = val.split(" | ")[0]
        if sku in self.skus_globales:
            messagebox.showinfo("Información", f"El producto {sku} ya es global.")
            return
            
        exito, msg = anadir_producto_global(sku)
        if exito:
            self.actualizar_lista()
        else:
            messagebox.showerror("Error", msg)

    def quitar_global(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Seleccione un producto de la lista para quitarle la asignación global.")
            return
            
        sku = self.tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirmar", f"¿Realmente desea quitar la asignación global al SKU {sku}?\n\nLos técnicos dejarán de ver el stock total de bodega."):
            exito, msg = eliminar_producto_global(sku)
            if exito:
                self.actualizar_lista()
            else:
                messagebox.showerror("Error", msg)
