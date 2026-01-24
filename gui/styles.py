from tkinter import ttk

class Styles:
    """Manages the application styles and colors."""
    
    # Colores modernos
    PRIMARY_COLOR = '#2c3e50'
    SECONDARY_COLOR = '#3498db'
    ACCENT_COLOR = '#e74c3c'
    SUCCESS_COLOR = '#27ae60'
    WARNING_COLOR = '#f39c12'
    INFO_COLOR = '#17a2b8'
    LIGHT_BG = '#ecf0f1'
    DARK_TEXT = '#2c3e50'
    LIGHT_TEXT = '#ecf0f1'

    @classmethod
    def setup_styles(cls):
        """Configura estilos modernos para la aplicación"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar estilos
        style.configure('Modern.TFrame', background=cls.LIGHT_BG)
        style.configure('Header.TFrame', background=cls.PRIMARY_COLOR)
        style.configure('Card.TFrame', background='white', relief='raised', borderwidth=0)
        
        style.configure('Title.TLabel', 
                    background=cls.PRIMARY_COLOR, 
                    foreground='white',
                    font=('Segoe UI', 18, 'bold'))
        
        style.configure('Subtitle.TLabel',
                    background=cls.LIGHT_BG,
                    foreground=cls.DARK_TEXT,
                    font=('Segoe UI', 12, 'bold'))
        
        style.configure('Modern.TButton',
                    background=cls.SECONDARY_COLOR,
                    foreground='white',
                    font=('Segoe UI', 10, 'bold'),
                    borderwidth=0,
                    focuscolor='none',
                    padding=(15, 8))
        
        style.map('Modern.TButton',
                background=[('active', '#2980b9'), ('pressed', '#21618c')])
        
        style.configure('Success.TButton',
                    background=cls.SUCCESS_COLOR,
                    foreground='white',
                    font=('Segoe UI', 10, 'bold'))
        
        style.map('Success.TButton',
                background=[('active', '#219a52'), ('pressed', '#1e7e48')])
        
        style.configure('Warning.TButton',
                    background=cls.WARNING_COLOR,
                    foreground='white',
                    font=('Segoe UI', 10, 'bold'))
        
        style.configure('Danger.TButton',
                    background=cls.ACCENT_COLOR,
                    foreground='white',
                    font=('Segoe UI', 10, 'bold'))
        
        style.configure('Info.TButton',
                    background=cls.INFO_COLOR,
                    foreground='white',
                    font=('Segoe UI', 10, 'bold'))
        
        style.configure('Modern.TEntry',
                    fieldbackground='white',
                    borderwidth=1,
                    relief='flat',
                    padding=(8, 6))
        
        style.configure('Modern.TCombobox',
                    fieldbackground='white',
                    background=cls.SECONDARY_COLOR,
                    arrowcolor='white')
        
        style.configure('Modern.Treeview',
                    background='white',
                    fieldbackground='white',
                    foreground=cls.DARK_TEXT,
                    rowheight=25)
        
        style.configure('Modern.Treeview.Heading',
                    background=cls.PRIMARY_COLOR,
                    foreground='white',
                    font=('Segoe UI', 10, 'bold'))
        
        style.map('Modern.Treeview',
                background=[('selected', cls.SECONDARY_COLOR)])
