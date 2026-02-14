
    def mostrar_detalle_series(self, event):
        """Muestra las series (MACs) asignadas al producto seleccionado"""
        item = self.tabla_fisica.identify_row(event.y)
        if not item: return
        
        vals = self.tabla_fisica.item(item, 'values')
        if not vals or len(vals) < 2: return
        
        # Validar si es una fila de datos (no separador o mensaje)
        tags = self.tabla_fisica.item(item, 'tags')
        if 'separator' in tags or 'total' in tags: return
        
        nombre = vals[0]
        sku = vals[1]
        
        # Obtener móvil seleccionado (asumiendo uno solo seleccionado para ver esta tabla)
        if len(self.moviles_seleccionados) != 1:
            return
            
        movil = self.moviles_seleccionados[0]
        
        # Consultar series
        series = obtener_series_por_sku_y_ubicacion(sku, movil)
        
        if not series:
            messagebox.showinfo("Sin Series", f"No se encontraron series registradas para {sku} en {movil}.")
            return
            
        # Mostrar Popup
        popup = tk.Toplevel(self)
        popup.title(f"Series de {sku}")
        popup.geometry("400x400")
        popup.transient(self)
        popup.grab_set()
        
        tk.Label(popup, text=f"Series Asignadas: {len(series)}", font=('Segoe UI', 10, 'bold')).pack(pady=10)
        tk.Label(popup, text=f"{nombre}", font=('Segoe UI', 9)).pack(pady=0)
        
        # Listbox con scroll
        frame_list = tk.Frame(popup)
        frame_list.pack(fill='both', expand=True, padx=10, pady=10)
        
        listbox = tk.Listbox(frame_list, font=('Consolas', 10))
        scroll = tk.Scrollbar(frame_list, orient='vertical', command=listbox.yview)
        listbox.config(yscrollcommand=scroll.set)
        
        scroll.pack(side='right', fill='y')
        listbox.pack(side='left', fill='both', expand=True)
        
        for s in series:
            listbox.insert('end', s)
            
        tk.Button(popup, text="Cerrar", command=popup.destroy).pack(pady=10)
