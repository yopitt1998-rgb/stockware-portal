"""
Sistema de Gestión de Temas para StockWare
Permite cambiar entre tema claro y oscuro
"""
import tkinter as tk
from tkinter import ttk
import json
import os

class ThemeManager:
    """
    Maneja los temas de la aplicación (claro/oscuro).
    """
    
    # Definición de temas
    THEMES = {
        'light': {
            'name': 'Claro',
            'bg_primary': '#f8f9fa',
            'bg_secondary': '#ffffff',
            'bg_accent': '#e8f4f8',
            'fg_primary': '#2c3e50',
            'fg_secondary': '#34495e',
            'fg_accent': '#3498db',
            'button_bg': '#3498db',
            'button_fg': '#ffffff',
            'button_hover': '#2980b9',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'border': '#bdc3c7',
            'card_bg': '#ffffff',
            'card_shadow': '#ecf0f1',
        },
        'dark': {
            'name': 'Oscuro',
            'bg_primary': '#1e1e1e',
            'bg_secondary': '#2d2d2d',
            'bg_accent': '#3d3d3d',
            'fg_primary': '#e0e0e0',
            'fg_secondary': '#b0b0b0',
            'fg_accent': '#4a9eff',
            'button_bg': '#4a9eff',
            'button_fg': '#ffffff',
            'button_hover': '#357abd',
            'success': '#2ecc71',
            'warning': '#f1c40f',
            'danger': '#e74c3c',
            'border': '#4d4d4d',
            'card_bg': '#2d2d2d',
            'card_shadow': '#1a1a1a',
        }
    }
    
    def __init__(self, root, config_file='theme_config.json'):
        self.root = root
        self.config_file = config_file
        self.current_theme = self._load_theme_preference()
        self.widgets_to_update = []
        
    def _load_theme_preference(self):
        """Carga la preferencia de tema guardada"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('theme', 'light')
        except Exception as e:
            print(f"Error al cargar preferencia de tema: {e}")
        return 'light'
        
    def _save_theme_preference(self):
        """Guarda la preferencia de tema"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'theme': self.current_theme}, f)
        except Exception as e:
            print(f"Error al guardar preferencia de tema: {e}")
            
    def get_color(self, color_key):
        """
        Obtiene un color del tema actual.
        
        Args:
            color_key: Clave del color (ej: 'bg_primary', 'fg_primary')
        
        Returns:
            str: Código de color hexadecimal
        """
        return self.THEMES[self.current_theme].get(color_key, '#000000')
        
    def toggle_theme(self):
        """Cambia entre tema claro y oscuro"""
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self._save_theme_preference()
        self.apply_theme()
        
    def set_theme(self, theme_name):
        """
        Establece un tema específico.
        
        Args:
            theme_name: 'light' o 'dark'
        """
        if theme_name in self.THEMES:
            self.current_theme = theme_name
            self._save_theme_preference()
            self.apply_theme()
            
    def register_widget(self, widget, widget_type='frame'):
        """
        Registra un widget para actualización automática de tema.
        
        Args:
            widget: Widget a registrar
            widget_type: Tipo de widget ('frame', 'label', 'button', etc.)
        """
        self.widgets_to_update.append({
            'widget': widget,
            'type': widget_type
        })
        
    def apply_theme(self):
        """Aplica el tema actual a todos los widgets registrados"""
        theme = self.THEMES[self.current_theme]
        
        # Actualizar root
        self.root.configure(bg=theme['bg_primary'])
        
        # Actualizar widgets registrados
        for item in self.widgets_to_update:
            widget = item['widget']
            w_type = item['type']
            
            try:
                if w_type == 'frame':
                    widget.configure(bg=theme['bg_secondary'])
                elif w_type == 'label':
                    widget.configure(bg=theme['bg_secondary'], fg=theme['fg_primary'])
                elif w_type == 'button':
                    widget.configure(bg=theme['button_bg'], fg=theme['button_fg'])
                # Agregar más tipos según necesidad
            except Exception as e:
                print(f"Error al aplicar tema a widget: {e}")
                
    def create_theme_toggle_button(self, parent):
        """
        Crea un botón para cambiar de tema.
        
        Args:
            parent: Widget padre donde colocar el botón
        
        Returns:
            tk.Button: Botón de cambio de tema
        """
        icon = "🌙" if self.current_theme == 'light' else "☀️"
        text = "Modo Oscuro" if self.current_theme == 'light' else "Modo Claro"
        
        button = tk.Button(
            parent,
            text=f"{icon} {text}",
            command=self._toggle_and_update_button,
            bg=self.get_color('button_bg'),
            fg=self.get_color('button_fg'),
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2'
        )
        
        self.theme_button = button
        return button
        
    def _toggle_and_update_button(self):
        """Cambia tema y actualiza el botón"""
        self.toggle_theme()
        
        # Actualizar texto e icono del botón
        if hasattr(self, 'theme_button'):
            icon = "🌙" if self.current_theme == 'light' else "☀️"
            text = "Modo Oscuro" if self.current_theme == 'light' else "Modo Claro"
            self.theme_button.configure(
                text=f"{icon} {text}",
                bg=self.get_color('button_bg'),
                fg=self.get_color('button_fg')
            )


def create_theme_manager(root):
    """
    Función helper para crear el gestor de temas.
    
    Args:
        root: Ventana raíz de Tkinter
    
    Returns:
        ThemeManager: Instancia del gestor de temas
    """
    return ThemeManager(root)
