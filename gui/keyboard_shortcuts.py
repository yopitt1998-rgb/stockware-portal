"""
Sistema de Atajos de Teclado para StockWare
Maneja atajos globales de teclado para mejorar la productividad
"""
import tkinter as tk

class KeyboardShortcuts:
    """
    Maneja los atajos de teclado globales de la aplicación.
    """
    def __init__(self, root, main_app):
        self.root = root
        self.main_app = main_app
        self.shortcuts = {}
        self._setup_shortcuts()
        
    def _setup_shortcuts(self):
        """Configura todos los atajos de teclado"""
        # Atajos de inventario
        self.register("<Control-n>", self._nuevo_abasto, "Nuevo Abasto")
        self.register("<Control-N>", self._nuevo_abasto, "Nuevo Abasto")
        
        self.register("<Control-s>", self._salida_movil, "Salida a Móvil")
        self.register("<Control-S>", self._salida_movil, "Salida a Móvil")
        
        self.register("<Control-r>", self._retorno_movil, "Retorno de Móvil")
        self.register("<Control-R>", self._retorno_movil, "Retorno de Móvil")
        
        # Atajos de reportes
        self.register("<Control-e>", self._exportar, "Exportar")
        self.register("<Control-E>", self._exportar, "Exportar")
        
        # Atajos generales
        self.register("<F5>", self._actualizar_dashboard, "Actualizar Dashboard")
        
        self.register("<Control-f>", self._buscar, "Buscar/Filtrar")
        self.register("<Control-F>", self._buscar, "Buscar/Filtrar")
        
        # Atajo de ayuda
        self.register("<F1>", self._mostrar_ayuda, "Mostrar Ayuda")
        
    def register(self, key_sequence, callback, description=""):
        """
        Registra un atajo de teclado.
        
        Args:
            key_sequence: Secuencia de teclas (ej: "<Control-n>")
            callback: Función a ejecutar
            description: Descripción del atajo
        """
        self.root.bind(key_sequence, callback)
        self.shortcuts[key_sequence] = {
            'callback': callback,
            'description': description
        }
        
    def _nuevo_abasto(self, event=None):
        """Abre ventana de nuevo abasto"""
        try:
            if hasattr(self.main_app, 'inventory_tab'):
                self.main_app.main_notebook.select(1)  # Seleccionar tab de inventario
                self.main_app.inventory_tab.abrir_ventana_abasto()
        except Exception as e:
            print(f"Error al abrir nuevo abasto: {e}")
        return "break"
        
    def _salida_movil(self, event=None):
        """Abre ventana de salida a móvil"""
        try:
            if hasattr(self.main_app, 'inventory_tab'):
                self.main_app.main_notebook.select(1)
                self.main_app.inventory_tab.abrir_ventana_salida()
        except Exception as e:
            print(f"Error al abrir salida a móvil: {e}")
        return "break"
        
    def _retorno_movil(self, event=None):
        """Abre ventana de retorno de móvil"""
        try:
            if hasattr(self.main_app, 'inventory_tab'):
                self.main_app.main_notebook.select(1)
                self.main_app.inventory_tab.abrir_ventana_retorno()
        except Exception as e:
            print(f"Error al abrir retorno de móvil: {e}")
        return "break"
        
    def _exportar(self, event=None):
        """Exporta datos de la pestaña actual"""
        try:
            current_tab = self.main_app.main_notebook.index(self.main_app.main_notebook.select())
            # Tab 3 es Reportes
            if current_tab == 3 and hasattr(self.main_app, 'reports_tab'):
                self.main_app.reports_tab.exportar_a_excel()
        except Exception as e:
            print(f"Error al exportar: {e}")
        return "break"
        
    def _actualizar_dashboard(self, event=None):
        """Actualiza el dashboard"""
        try:
            if hasattr(self.main_app, 'dashboard_tab'):
                self.main_app.main_notebook.select(0)  # Seleccionar dashboard
                self.main_app.dashboard_tab.actualizar_metricas()
        except Exception as e:
            print(f"Error al actualizar dashboard: {e}")
        return "break"
        
    def _buscar(self, event=None):
        """Activa función de búsqueda en la pestaña actual"""
        # Por ahora solo muestra mensaje, se puede expandir
        print("Función de búsqueda - Por implementar en cada pestaña")
        return "break"
        
    def _mostrar_ayuda(self, event=None):
        """Muestra ventana de ayuda con atajos disponibles"""
        try:
            self._show_shortcuts_window()
        except Exception as e:
            print(f"Error al mostrar ayuda: {e}")
        return "break"
        
    def _show_shortcuts_window(self):
        """Muestra ventana con lista de atajos disponibles"""
        help_window = tk.Toplevel(self.root)
        help_window.title("⌨️ Atajos de Teclado")
        help_window.geometry("500x400")
        help_window.configure(bg='#f8f9fa')
        
        # Título
        tk.Label(help_window, text="⌨️ Atajos de Teclado Disponibles",
                font=('Segoe UI', 14, 'bold'), bg='#f8f9fa', fg='#2c3e50').pack(pady=20)
        
        # Frame con scroll
        frame = tk.Frame(help_window, bg='white', padx=20, pady=20)
        frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Lista de atajos
        shortcuts_text = [
            ("Ctrl+N", "Nuevo Abasto"),
            ("Ctrl+S", "Salida a Móvil"),
            ("Ctrl+R", "Retorno de Móvil"),
            ("Ctrl+E", "Exportar a Excel"),
            ("F5", "Actualizar Dashboard"),
            ("Ctrl+F", "Buscar/Filtrar"),
            ("F1", "Mostrar esta ayuda"),
        ]
        
        for key, desc in shortcuts_text:
            row = tk.Frame(frame, bg='white')
            row.pack(fill='x', pady=5)
            
            tk.Label(row, text=key, font=('Consolas', 10, 'bold'),
                    bg='#e8f4f8', fg='#2c3e50', padx=10, pady=5,
                    width=15, anchor='w').pack(side='left')
            
            tk.Label(row, text=desc, font=('Segoe UI', 10),
                    bg='white', fg='#34495e', anchor='w').pack(side='left', padx=10)
        
        # Botón cerrar
        tk.Button(help_window, text="Cerrar", command=help_window.destroy,
                 bg='#3498db', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=8, cursor='hand2').pack(pady=10)


def setup_keyboard_shortcuts(root, main_app):
    """
    Función helper para configurar atajos de teclado.
    
    Args:
        root: Ventana raíz de Tkinter
        main_app: Instancia de la aplicación principal
    
    Returns:
        KeyboardShortcuts: Instancia del manejador de atajos
    """
    return KeyboardShortcuts(root, main_app)
