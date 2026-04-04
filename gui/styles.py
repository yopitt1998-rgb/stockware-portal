from tkinter import ttk

class Styles:
    """Manages the application styles and colors."""
    
    # Colores Premium (Slate & Indigo Palette)
    PRIMARY_COLOR = '#0f172a'   # Slate 900
    SECONDARY_COLOR = '#4f46e5' # Indigo 600
    ACCENT_COLOR = '#f43f5e'    # Rose 500
    SUCCESS_COLOR = '#10b981'   # Emerald 500
    DANGER_COLOR = '#f43f5e'    # Rose 500
    WARNING_COLOR = '#f59e0b'   # Amber 500
    INFO_COLOR = '#0ea5e9'      # Sky 500
    LIGHT_BG = '#f8fafc'        # Slate 50
    BG_COLOR = '#f8fafc'
    DARK_TEXT = '#1e293b'       # Slate 800
    LIGHT_TEXT = '#f8fafc'
    TEXT_COLOR = '#1e293b'
    BORDER_COLOR = '#e2e8f0'    # Slate 200

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
                    font=('Segoe UI Variable', 10),
                    rowheight=40,
                    borderwidth=0)
        
        style.configure('Modern.Treeview.Heading',
                    background=cls.PRIMARY_COLOR,
                    foreground='white',
                    font=('Segoe UI Variable', 10, 'bold'),
                    padding=(10, 5))
        
        style.map('Modern.Treeview',
                background=[('selected', cls.SECONDARY_COLOR)],
                foreground=[('selected', 'white')])
        
        # Estilo para Notebook
        style.configure('TNotebook', background=cls.LIGHT_BG, borderwidth=0)
        style.configure('TNotebook.Tab', 
                        padding=(20, 8), 
                        font=('Segoe UI Variable', 10),
                        background='#e2e8f0', 
                        foreground=cls.DARK_TEXT)
        style.map('TNotebook.Tab',
                  background=[('selected', 'white')],
                  foreground=[('selected', cls.SECONDARY_COLOR)],
                  expand=[('selected', [1, 1, 1, 0])])
