import tkinter as tk
from tkinter import ttk, messagebox
from database import obtener_moviles, crear_movil, editar_movil, eliminar_movil
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente

class MobilesManager(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("🚚 Gestión de Móviles")
        self.geometry("800x600")
        self.configure(bg='#f8f9fa')
        self.grab_set()
        
        self.create_widgets()
        self.cargar_datos()

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self, bg=Styles.SECONDARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="🚚 GESTIÓN DE MÓVILES", 
                font=('Segoe UI', 16, 'bold'), bg=Styles.SECONDARY_COLOR, fg='white').pack(pady=20)
        
        # Main content
        content_frame = tk.Frame(self, padx=20, pady=20, bg='#f8f9fa')
        content_frame.pack(fill='both', expand=True)
        
        # Form frame
        form_frame = tk.LabelFrame(content_frame, text=" Registrar / Editar Móvil ", 
                                  font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', padx=10, pady=10)
        form_frame.pack(fill='x', pady=(0, 20))
        
        # Inputs
        tk.Label(form_frame, text="Nombre del Móvil:", bg='#f8f9fa').grid(row=0, column=0, sticky='w', pady=5)
        self.nombre_entry = ttk.Entry(form_frame, width=30)
        self.nombre_entry.grid(row=0, column=1, sticky='w', padx=10, pady=5)
        
        tk.Label(form_frame, text="Patente:", bg='#f8f9fa').grid(row=0, column=2, sticky='w', pady=5)
        self.patente_entry = ttk.Entry(form_frame, width=20)
        self.patente_entry.grid(row=0, column=3, sticky='w', padx=10, pady=5)
        
        tk.Label(form_frame, text="Técnico 1:", bg='#f8f9fa').grid(row=1, column=0, sticky='w', pady=5)
        self.conductor_entry = ttk.Entry(form_frame, width=30)
        self.conductor_entry.grid(row=1, column=1, sticky='w', padx=10, pady=5)

        tk.Label(form_frame, text="Técnico 2:", bg='#f8f9fa').grid(row=1, column=2, sticky='w', pady=5)
        self.ayudante_entry = ttk.Entry(form_frame, width=30)
        self.ayudante_entry.grid(row=1, column=3, sticky='w', padx=10, pady=5)

        
        # Buttons
        btn_frame = tk.Frame(form_frame, bg='#f8f9fa')
        btn_frame.grid(row=2, column=0, columnspan=4, pady=15)
        
        self.btn_guardar = tk.Button(btn_frame, text="➕ Guardar Nuevo", command=self.guardar_movil,
                                   bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                                   relief='flat', padx=15, pady=5, cursor='hand2')
        self.btn_guardar.pack(side='left', padx=5)
        
        self.btn_tecnicos = tk.Button(btn_frame, text="👥 Gestionar Técnicos", command=self.abrir_gestor_tecnicos,
                                   bg='#6c757d', fg='white', font=('Segoe UI', 9, 'bold'),
                                   relief='flat', padx=15, pady=5, cursor='hand2')
        self.btn_tecnicos.pack(side='left', padx=5)

        self.btn_editar = tk.Button(btn_frame, text="✏️ Actualizar Seleccionado", command=self.actualizar_movil,
                                  bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                                  relief='flat', padx=15, pady=5, cursor='hand2', state='disabled')
        self.btn_editar.pack(side='left', padx=5)
        
        self.btn_limpiar = tk.Button(btn_frame, text="🧹 Limpiar", command=self.limpiar_form,
                                   bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                                   relief='flat', padx=15, pady=5, cursor='hand2')
        self.btn_limpiar.pack(side='left', padx=5)
        
        # Table frame
        table_frame = tk.Frame(content_frame, bg='#f8f9fa')
        table_frame.pack(fill='both', expand=True)
        
        columns = ("Nombre", "Patente", "Técnico 1", "Técnico 2", "Estado")
        self.tabla = ttk.Treeview(table_frame, columns=columns, show='headings', style='Modern.Treeview')
        
        for col in columns:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, anchor='center', width=130)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        
        self.tabla.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.tabla.bind("<<TreeviewSelect>>", self.on_select)
        
        # Context menu
        self.menu_contextual = tk.Menu(self, tearoff=0)
        self.menu_contextual.add_command(label="Eliminar/Desactivar", command=self.desactivar_movil)

        def show_menu(event):
            item = self.tabla.identify_row(event.y)
            if item:
                self.tabla.selection_set(item)
                self.menu_contextual.post(event.x_root, event.y_root)

        self.tabla.bind("<Button-3>", show_menu)

    def cargar_datos(self):
        for item in self.tabla.get_children():
            self.tabla.delete(item)
            
        moviles = obtener_moviles(solo_activos=False)
        for nombre, patente, conductor, ayudante, activo in moviles:
            estado = "Activo" if activo else "Inactivo"
            tags = () if activo else ('inactivo',)
            self.tabla.insert('', tk.END, values=(nombre, patente, conductor, ayudante, estado), tags=tags)
        
        self.tabla.tag_configure('inactivo', foreground='gray')

    def abrir_gestor_tecnicos(self):
        TechnicianManager(self)

    def on_select(self, event):
        seleccion = self.tabla.selection()
        if seleccion:
            valores = self.tabla.item(seleccion[0])['values']
            self.nombre_actual = valores[0]
            
            self.nombre_entry.delete(0, tk.END)
            self.nombre_entry.insert(0, valores[0])
            
            self.patente_entry.delete(0, tk.END)
            self.patente_entry.insert(0, " " if valores[1] == "None" else valores[1])
            
            self.conductor_entry.delete(0, tk.END)
            self.conductor_entry.insert(0, "" if not valores[2] or valores[2] == "None" else valores[2])
            
            self.ayudante_entry.delete(0, tk.END)
            self.ayudante_entry.insert(0, "" if not valores[3] or valores[3] == "None" else valores[3])
            
            self.btn_editar.config(state='normal')
            self.btn_guardar.config(state='disabled')

    def limpiar_form(self):
        self.nombre_entry.delete(0, tk.END)
        self.patente_entry.delete(0, tk.END)
        self.conductor_entry.delete(0, tk.END)
        self.ayudante_entry.delete(0, tk.END)
        self.btn_editar.config(state='disabled')
        self.btn_guardar.config(state='normal')

    def guardar_movil(self):
        nombre = self.nombre_entry.get().strip()
        patente = self.patente_entry.get().strip()
        conductor = self.conductor_entry.get().strip()
        ayudante = self.ayudante_entry.get().strip()
        
        if not nombre:
            mostrar_mensaje_emergente(self, "Error", "El nombre es obligatorio.", "error")
            return
            
        exito, mensaje = crear_movil(nombre, patente, conductor, ayudante)
        if exito:
            mostrar_mensaje_emergente(self, "Éxito", mensaje, "success")
            self.limpiar_form()
            self.cargar_datos()
        else:
            mostrar_mensaje_emergente(self, "Error", mensaje, "error")

    def actualizar_movil(self):
        nuevo_nombre = self.nombre_entry.get().strip()
        nueva_patente = self.patente_entry.get().strip()
        nuevo_conductor = self.conductor_entry.get().strip()
        nuevo_ayudante = self.ayudante_entry.get().strip()
        
        if not nuevo_nombre:
            mostrar_mensaje_emergente(self, "Error", "El nombre es obligatorio.", "error")
            return
            
        exito, mensaje = editar_movil(self.nombre_actual, nuevo_nombre, nueva_patente, nuevo_conductor, nuevo_ayudante)
        if exito:
            mostrar_mensaje_emergente(self, "Éxito", mensaje, "success")
            self.limpiar_form()
            self.cargar_datos()
        else:
            mostrar_mensaje_emergente(self, "Error", mensaje, "error")

    def desactivar_movil(self):
        seleccion = self.tabla.selection()
        if not seleccion: return
        
        nombre = self.tabla.item(seleccion[0])['values'][0]
        if messagebox.askyesno("Confirmar", f"¿Desea archivar/desactivar el móvil '{nombre}'?"):
            exito, mensaje = eliminar_movil(nombre)
            if exito:
                mostrar_mensaje_emergente(self, "Éxito", mensaje, "success")
                self.cargar_datos()
            else:
                mostrar_mensaje_emergente(self, "Error", mensaje, "error")


class TechnicianManager(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("👥 Gestión de Técnicos")
        self.geometry("600x500")
        self.configure(bg='#f8f9fa')
        self.grab_set()
        
        from database import obtener_tecnicos, crear_tecnico, editar_tecnico, eliminar_tecnico
        self.db_funcs = {
            'list': obtener_tecnicos,
            'create': crear_tecnico,
            'edit': editar_tecnico,
            'delete': eliminar_tecnico
        }
        
        self.create_widgets()
        self.cargar_datos()

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self, bg='#34495e', height=60)
        header_frame.pack(fill='x')
        tk.Label(header_frame, text="👥 MAESTRO DE TÉCNICOS", 
                font=('Segoe UI', 14, 'bold'), bg='#34495e', fg='white').pack(pady=15)
        
        # Content
        content = tk.Frame(self, padx=20, pady=20, bg='#f8f9fa')
        content.pack(fill='both', expand=True)
        
        # Form
        entry_frame = tk.Frame(content, bg='#f8f9fa')
        entry_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(entry_frame, text="Nombre del Técnico:", bg='#f8f9fa').pack(side='left')
        self.nombre_var = tk.StringVar()
        self.entry_nombre = ttk.Entry(entry_frame, textvariable=self.nombre_var, width=30)
        self.entry_nombre.pack(side='left', padx=10)
        
        self.btn_add = tk.Button(entry_frame, text="➕ Añadir", command=self.guardar,
                               bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                               relief='flat', padx=10, pady=2)
        self.btn_add.pack(side='left')
        
        # Table
        table_frame = tk.Frame(content)
        table_frame.pack(fill='both', expand=True)
        
        self.tree = ttk.Treeview(table_frame, columns=("ID", "Nombre", "Estado"), show='headings')
        self.tree.heading("ID", text="ID")
        self.tree.heading("Nombre", text="Nombre")
        self.tree.heading("Estado", text="Estado")
        self.tree.column("ID", width=50, anchor='center')
        self.tree.column("Nombre", width=300)
        self.tree.column("Estado", width=100, anchor='center')
        self.tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        # Delete button
        self.btn_del = tk.Button(content, text="🗑️ Eliminar/Desactivar Seleccionado", command=self.eliminar,
                               bg=Styles.DANGER_COLOR, fg='white', font=('Segoe UI', 9, 'bold'),
                               relief='flat', pady=5)
        self.btn_del.pack(fill='x', pady=(10, 0))

    def cargar_datos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        tecnicos = self.db_funcs['list']()
        for tid, nombre, activo in tecnicos:
            estado = "Activo" if activo else "Inactivo"
            self.tree.insert('', tk.END, values=(tid, nombre, estado))

    def guardar(self):
        nombre = self.nombre_var.get().strip()
        if not nombre: return
        
        exito, msg = self.db_funcs['create'](nombre)
        if exito:
            self.nombre_var.set("")
            self.cargar_datos()
        else:
            messagebox.showerror("Error", msg)

    def eliminar(self):
        sel = self.tree.selection()
        if not sel: return
        
        tid = self.tree.item(sel[0])['values'][0]
        nombre = self.tree.item(sel[0])['values'][1]
        
        if messagebox.askyesno("Confirmar", f"¿Desactivar al técnico {nombre}?"):
            exito, msg = self.db_funcs['delete'](tid)
            if exito:
                self.cargar_datos()
            else:
                messagebox.showerror("Error", msg)
