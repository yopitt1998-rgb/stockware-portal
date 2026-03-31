import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from config import PAQUETES_MATERIALES, save_custom_packages
import copy
from gui.styles import Styles

class PackageEditorDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("📦 Editar Progreso de Paquetes")
        self.geometry("700x550")
        self.configure(bg='#f8f9fa')
        self.transient(master)
        self.grab_set()
        
        # Load products for names mapping
        try:
            from database import obtener_productos
            prods = obtener_productos()
            self.prod_map = {p[1]: p[0] for p in prods}
        except:
            self.prod_map = {}
            
        # Working copy
        self.pack_data = copy.deepcopy(PAQUETES_MATERIALES)
        
        self.create_widgets()
        
        if "PAQUETE A" in self.pack_data:
            self.combo_pack.set("PAQUETE A")
            self.load_package("PAQUETE A")
        elif self.pack_data:
            first = list(self.pack_data.keys())[0]
            self.combo_pack.set(first)
            self.load_package(first)

    def create_widgets(self):
        header = tk.Frame(self, bg=Styles.PRIMARY_COLOR, pady=15)
        header.pack(fill='x')
        tk.Label(header, text="⚙️ Configuración de Progreso de Paquetes", 
                 font=('Segoe UI', 14, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack()
                 
        top_frame = tk.Frame(self, bg='#f8f9fa', pady=10, padx=20)
        top_frame.pack(fill='x')
        
        tk.Label(top_frame, text="Seleccione un Paquete:", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0,10))
        
        self.combo_pack = ttk.Combobox(top_frame, values=list(self.pack_data.keys()), state='readonly', width=30)
        self.combo_pack.pack(side='left')
        self.combo_pack.bind("<<ComboboxSelected>>", lambda e: self.load_package(self.combo_pack.get()))
        
        # main list
        list_frame = tk.Frame(self, bg='#f8f9fa', padx=20, pady=10)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('SKU', 'Nombre', 'Cantidad Objetivo')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        self.tree.heading('SKU', text='SKU')
        self.tree.heading('Nombre', text='Nombre Producto')
        self.tree.heading('Cantidad Objetivo', text='Cantidad Objetivo (100%)', anchor='center')
        
        self.tree.column('SKU', width=120)
        self.tree.column('Nombre', width=300)
        self.tree.column('Cantidad Objetivo', width=150, anchor='center')
        self.tree.pack(fill='both', expand=True, side='left')
        
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.bind("<Double-1>", self.editar_item)
        
        # text hint
        tk.Label(self, text="💡 Doble clic en un ítem para modificar la cantidad objetivo. Esto cambiará cómo se calcula el progreso en Salidas.",
                 bg='#e8f0fe', fg='#1967d2', font=('Segoe UI', 9)).pack(fill='x', padx=20, pady=5)
                 
        # btn frame
        btn_frame = tk.Frame(self, bg='#f8f9fa', pady=15)
        btn_frame.pack(fill='x')
        
        tk.Button(btn_frame, text="✅ Guardar Cambios", command=self.guardar,
                  bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                  padx=20, pady=8, relief='flat').pack(side='right', padx=20)
                  
        tk.Button(btn_frame, text="❌ Cancelar", command=self.destroy,
                  bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                  padx=20, pady=8, relief='flat').pack(side='right')

    def load_package(self, pkg_name):
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        items = self.pack_data.get(pkg_name, [])
        for sku, cant in items:
            nombre = self.prod_map.get(sku, "Desconocido / Compartido / No en DB")
            self.tree.insert('', 'end', values=(sku, nombre, cant))

    def editar_item(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id: return
        
        vals = self.tree.item(item_id, 'values')
        sku, nombre, cant_actual = vals
        
        nueva_cant = simpledialog.askinteger("Editar Cantidad", 
                                             f"SKU: {sku}\nNombre: {nombre}\nNueva cantidad objetivo:",
                                             initialvalue=int(cant_actual), parent=self)
        if nueva_cant is not None and nueva_cant >= 0:
            self.tree.item(item_id, values=(sku, nombre, nueva_cant))
            
            # Update memory dict
            pkg_name = self.combo_pack.get()
            # find and replace
            new_list = []
            for s, c in self.pack_data[pkg_name]:
                if s == sku:
                    new_list.append((s, nueva_cant))
                else:
                    new_list.append((s, c))
            self.pack_data[pkg_name] = new_list

    def guardar(self):
        if messagebox.askyesno("Confirmar", "¿Desea aplicar y guardar la configuración de progreso de estos paquetes?"):
            PAQUETES_MATERIALES.clear()
            PAQUETES_MATERIALES.update(self.pack_data)
            save_custom_packages()
            messagebox.showinfo("Éxito", "Configuración de paquetes actualizada correctamente.")
            self.destroy()
