import tkinter as tk
from tkinter import ttk, messagebox
import importlib
import types
import logging

logger = logging.getLogger(__name__)

class TabManager:
    """Manages the lazy loading and switching of tabs in the main notebook."""
    
    def __init__(self, app):
        self.app = app
        self.master = app.master
        self.main_notebook = app.main_notebook
        self.tabs_data = app.tabs_data
        self.nav_buttons = app.nav_buttons
        
        # Bind tab change event
        self.main_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        """Handle notebook tab change event."""
        try:
            current_tab_index = self.main_notebook.index(self.main_notebook.select())
            tab_name = self.main_notebook.tab(current_tab_index, "text")
            
            # Update navigation button styles
            self._update_nav_buttons(tab_name)
                    
            # Lazy load the tab if needed
            self.load_tab(tab_name)
        except Exception as e:
            logger.error(f"Error in on_tab_changed: {e}")

    def _update_nav_buttons(self, active_tab_name):
        """Update the sidebar buttons to reflect the active tab."""
        for name, btn in self.nav_buttons.items():
            if name == active_tab_name:
                btn.configure(bg='#34495e', fg='#3498db', font=('Segoe UI', 11, 'bold'))
            else:
                btn.configure(bg='#2c3e50', fg='#ecf0f1', font=('Segoe UI', 11))

    def load_tab(self, tab_name):
        """Load a tab module and instantiate its class."""
        data = self.tabs_data.get(tab_name)
        if not data or data['loaded']:
            return
            
        # Add .add() adapter if not present
        if not hasattr(data['frame'], 'add'):
            def _fake_add(frame_instance, child, **kwargs):
                child.pack(fill='both', expand=True)
            data['frame'].add = types.MethodType(_fake_add, data['frame'])

        # Show loading indicator
        loading_label = tk.Label(data['frame'],
                                text="⏳  Cargando...",
                                font=('Segoe UI', 18, 'bold'),
                                fg='#3498db', bg='#ecf0f1')
        loading_label.place(relx=0.5, rely=0.5, anchor='center')
        data['frame'].update_idletasks()

        logger.info(f"Lazy loading tab: {tab_name}...")
        
        try:
            module = importlib.import_module(data['module'])
            cls = getattr(module, data['class'])
            
            # Remove loading indicator
            if loading_label.winfo_exists():
                loading_label.destroy()
            
            # Clear frame
            for widget in data['frame'].winfo_children():
                widget.destroy()
                
            # Instantiate class
            instance = cls(data['frame'], self.app)
                
            if isinstance(instance, tk.Widget):
                instance.pack(fill='both', expand=True)
            
            # Store reference in app
            class_key = data['class'].lower()
            setattr(self.app, class_key, instance) 
            
            # Legacy mappings
            self._apply_legacy_mappings(tab_name, instance)
            
            data['loaded'] = True
            logger.info(f"Tab {tab_name} loaded successfully.")
            
        except Exception as e:
            if loading_label.winfo_exists():
                loading_label.destroy()

            logger.error(f"Error loading tab {tab_name}: {e}")
            import traceback
            traceback.print_exc()
            tk.Label(data['frame'], text=f"Error cargando módulo:\n{e}", fg='red').pack()

    def _apply_legacy_mappings(self, tab_name, instance):
        """Maintain legacy attribute names for compatibility."""
        mappings = {
            "Dashboard": "dashboard_tab",
            "Inventario": "inventory_tab",
            "Historial": "audit_tab",
            "Productos": "products_tab",
            "Configuración": "settings_tab",
            "Registro Global": "history_tab"
        }
        if tab_name in mappings:
            setattr(self.app, mappings[tab_name], instance)

    def switch_to_tab(self, tab_name):
        """Programmatically switch to a tab by name."""
        for i, name in enumerate(self.tabs_data.keys()):
            # Note: name here is the key in tabs_data, but notebook uses displayed text
            # We need to match displayed text
            try:
                if self.main_notebook.tab(i, "text") == tab_name:
                    self.main_notebook.select(i)
                    return
            except Exception:
                continue
