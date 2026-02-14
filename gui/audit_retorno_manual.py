    def abrir_retorno_manual(self):
        """Abre diálogo para registrar un retorno manual desde móvil a bodega"""
        from collections import defaultdict
        from database import obtener_asignacion_movil_activa, procesar_retorno_manual
        
        ventana = tk.Toplevel(self)
        ventana.title("📥 Retorno Manual de Materiales")
        ventana.geometry("600x650")
        ventana.transient(self.main_app.master)
        ventana.grab_set()
        ventana.configure(bg='#f8f9fa')
        
        # Centrar ventana
        ventana.update_idletasks()
        x = (ventana.winfo_screenwidth() // 2) - (600 // 2)
        y = (ventana.winfo_screenheight() // 2) - (650 // 2)
        ventana.geometry(f"+{x}+{y}")
        
        # Frame superior: Información
        info_frame = tk.Frame(ventana, bg='#E3F2FD', padx=15, pady=10)
        info_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(info_frame, text="ℹ️ RETORNO MANUAL", 
                font=('Segoe UI', 12, 'bold'), bg='#E3F2FD', fg=Styles.PRIMARY_COLOR).pack()
        tk.Label(info_frame, 
                text="Devuelve materiales desde un móvil a la bodega.\\nUsado para equipos no consumidos.",
                font=('Segoe UI', 9), bg='#E3F2FD', fg='#555').pack(pady=5)
        
        # Frame formulario
        form_frame = tk.LabelFrame(ventana, text="Datos del Retorno", 
                                  font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', padx=20, pady=15)
        form_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 1. Selector de Móvil
        tk.Label(form_frame, text="Móvil:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').grid(row=0, column=0, sticky='w', pady=5)
        
        from config import CURRENT_CONTEXT
        moviles_disponibles = CURRENT_CONTEXT.get('MOVILES', obtener_nombres_moviles())
        
        movil_var = tk.StringVar()
        movil_combo = ttk.Combobox(form_frame, textvariable=movil_var, 
                                  values=moviles_disponibles, state='readonly', width=30)
        movil_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # 2. Fecha
        tk.Label(form_frame, text="Fecha:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').grid(row=1, column=0, sticky='w', pady=5)
        
        fecha_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        fecha_entry = tk.Entry(form_frame, textvariable=fecha_var, width=32)
        fecha_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # 3. Frame para materiales disponibles
        materiales_frame = tk.LabelFrame(form_frame, text="Materiales Disponibles en Móvil", 
                                        font=('Segoe UI', 9, 'bold'), bg='#f8f9fa')
        materiales_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)
        
        # TreeView para mostrar materiales
        cols = ('Producto', 'SKU', 'Disponible', 'Retornar')
        tree_materiales = ttk.Treeview(materiales_frame, columns=cols, show='headings', height=8)
        
        tree_materiales.heading('Producto', text='Producto')
        tree_materiales.heading('SKU', text='SKU')
        tree_materiales.heading('Disponible', text='Disponible')
        tree_materiales.heading('Retornar', text='Cantidad a Retornar')
        
        tree_materiales.column('Producto', width=200)
        tree_materiales.column('SKU', width=80, anchor='center')
        tree_materiales.column('Disponible', width=80, anchor='center')
        tree_materiales.column('Retornar', width=120, anchor='center')
        
        tree_materiales.pack(fill='both', expand=True, padx=5, pady=5)
        
        # ScrollBar
        scroll_y = ttk.Scrollbar(materiales_frame, orient='vertical', command=tree_materiales.yview)
        tree_materiales.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side='right', fill='y')
        
        # Diccionario para almacenar entries de cantidad
        entries_cantidad = {}
        
        def cargar_materiales_movil():
            """Carga los materiales asignados al móvil seleccionado"""
            # Limpiar tabla
            for item in tree_materiales.get_children():
                tree_materiales.delete(item)
            entries_cantidad.clear()
            
            movil = movil_var.get()
            if not movil:
                return
            
            materiales = obtener_asignacion_movil_activa(movil)
            
            if not materiales:
                messagebox.showinfo("Sin Materiales", 
                                  f"El móvil {movil} no tiene materiales asignados actualmente.")
                return
            
            for sku, nombre, cantidad in materiales:
                item_id = tree_materiales.insert('', 'end', 
                                               values=(nombre, sku, cantidad, '0'))
                entries_cantidad[item_id] = {'sku': sku, 'nombre': nombre, 'max': cantidad}
        
        # Bind de selección de móvil
        movil_combo.bind('<<ComboboxSelected>>', lambda e: cargar_materiales_movil())
        
        # Función para editar cantidad en la tabla
        def on_double_click(event):
            """Permite editar la cantidad a retornar con doble click"""
            item = tree_materiales.identify_row(event.y)
            column = tree_materiales.identify_column(event.x)
            
            if not item or column != '#4':  # Solo columna "Retornar"
                return
            
            # Obtener valor actual
            current_value = tree_materiales.item(item, 'values')[3]
            max_cantidad = entries_cantidad[item]['max']
            
            # Crear entry para editar
            x, y, width, height = tree_materiales.bbox(item, column)
            
            entry_edit = tk.Entry(tree_materiales, width=10)
            entry_edit.place(x=x, y=y, width=width, height=height)
            entry_edit.insert(0, current_value)
            entry_edit.focus_set()
            entry_edit.select_range(0, tk.END)
            
            def guardar_valor(event=None):
                try:
                    nuevo_valor = int(entry_edit.get())
                    if nuevo_valor < 0:
                        raise ValueError("Cantidad negativa")
                    if nuevo_valor > max_cantidad:
                        messagebox.showwarning("Cantidad Excedida", 
                                             f"La cantidad máxima disponible es {max_cantidad}")
                        entry_edit.delete(0, tk.END)
                        entry_edit.insert(0, max_cantidad)
                        return
                    
                    # Actualizar valor en tabla
                    valores = list(tree_materiales.item(item, 'values'))
                    valores[3] = nuevo_valor
                    tree_materiales.item(item, values=valores)
                    entry_edit.destroy()
                except ValueError:
                    messagebox.showerror("Error", "Ingrese un número válido")
                    entry_edit.focus_set()
            
            entry_edit.bind('<Return>', guardar_valor)
            entry_edit.bind('<FocusOut>', guardar_valor)
            entry_edit.bind('<Escape>', lambda e: entry_edit.destroy())
        
        tree_materiales.bind('<Double-1>', on_double_click)
        
        # 4. Observaciones
        tk.Label(form_frame, text="Observaciones:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').grid(row=3, column=0, sticky='nw', pady=5)
        
        obs_text = tk.Text(form_frame, height=3, width=32, font=('Segoe UI', 9))
        obs_text.grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        form_frame.columnconfigure(1, weight=1)
        
        # Botones de acción
        btn_frame = tk.Frame(ventana, bg='#f8f9fa')
        btn_frame.pack(fill='x', padx=20, pady=20)
        
        def procesar_retornos():
            """Procesa todos los retornos marcados"""
            movil = movil_var.get()
            fecha = fecha_var.get()
            obs = obs_text.get('1.0', tk.END).strip()
            
            if not movil:
                messagebox.showerror("Error", "Debe seleccionar un móvil")
                return
            
            if not fecha:
                messagebox.showerror("Error", "Debe ingresar una fecha")
                return
            
            # Recopilar items a retornar
            retornos = []
            for item in tree_materiales.get_children():
                valores = tree_materiales.item(item, 'values')
                cantidad_retornar = int(valores[3])
                
                if cantidad_retornar > 0:
                    sku = entries_cantidad[item]['sku']
                    nombre = entries_cantidad[item]['nombre']
                    retornos.append((sku, nombre, cantidad_retornar))
            
            if not retornos:
                messagebox.showwarning("Sin Retornos", 
                                     "Debe especificar al menos un material a retornar.\\n\\n"
                                     "Doble click en la columna 'Cantidad a Retornar' para editar")
                return
            
            # Confirmar
            total_items = sum(r[2] for r in retornos)
            if not messagebox.askyesno("Confirmar Retornos",
                                       f"¿Confirma retornar {total_items} unidades de {len(retornos)} productos\\n"
                                       f"desde {movil} a BODEGA?"):
                return
            
            # Procesar retornos
            exitos = 0
            errores = 0
            errores_detalle = []
            
            for sku, nombre, cantidad in retornos:
                exito, mensaje = procesar_retorno_manual(movil, sku, cantidad, fecha, obs)
                
                if exito:
                    exitos += cantidad
                else:
                    errores += cantidad
                    errores_detalle.append(f"{nombre}: {mensaje}")
            
            # Mostrar resultado
            if errores == 0:
                mostrar_mensaje_emergente(self.main_app.master, "Retornos Completados",
                                         f"Se retornaron {exitos} unidades exitosamente a BODEGA.",
                                         "success")
                ventana.destroy()
                self.cargar_datos_pendientes()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
            else:
                msg = f"Éxitos: {exitos} | Errores: {errores}\\n\\nDetalles:\\n"
                msg += "\\n".join(errores_detalle[:3])
                if len(errores_detalle) > 3:
                    msg += f"\\n... y {len(errores_detalle) - 3} más"
                mostrar_mensaje_emergente(ventana, "Proceso Completado con Errores", msg, "warning")
        
        tk.Button(btn_frame, text="✅ Procesar Retornos", command=procesar_retornos,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                 relief='flat', padx=30, pady=10).pack(side='right')
        
        tk.Button(btn_frame, text="❌ Cancelar", command=ventana.destroy,
                 bg='#9E9E9E', fg='white', font=('Segoe UI', 10),
                 relief='flat', padx=20, pady=8).pack(side='right', padx=10)
