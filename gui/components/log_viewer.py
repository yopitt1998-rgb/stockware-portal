import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
from datetime import datetime

class TkLogHandler(logging.Handler):
    """Custom logging handler to redirect logs to a Tkinter text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-7s | %(message)s', '%H:%M:%S'))

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + "\n")
            # Auto-scroll
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
            
            # Keep only last 1000 lines
            if float(self.text_widget.index('end-1c')) > 1000:
                self.text_widget.delete('1.0', '10.0')
                
        self.text_widget.after(0, append)

class LogViewerWindow(tk.Toplevel):
    """Window to display real-time application logs."""
    def __init__(self, master):
        super().__init__(master)
        self.title("🔍 StockWare - Visor de Logs del Sistema")
        self.geometry("800x500")
        self.minsize(600, 400)
        
        # UI Setup
        main_frame = tk.Frame(self, bg='#f1f5f9', padx=10, pady=10)
        main_frame.pack(fill='both', expand=True)
        
        # Header
        header = tk.Frame(main_frame, bg='#f1f5f9')
        header.pack(fill='x', pady=(0, 10))
        
        tk.Label(header, text="REGISTRO DE ACTIVIDAD (LOGS)", 
                font=('Segoe UI', 12, 'bold'), bg='#f1f5f9', fg='#1e293b').pack(side='left')
        
        btn_clear = tk.Button(header, text="Limpiar", command=self.clear_logs,
                             bg='#e2e8f0', relief='flat', padx=10)
        btn_clear.pack(side='right')

        # Log Area
        self.log_area = scrolledtext.ScrolledText(main_frame, state='disabled', 
                                                 font=('Consolas', 9),
                                                 bg='#0f172a', fg='#f8fafc',
                                                 borderwidth=0)
        self.log_area.pack(fill='both', expand=True)
        
        # Add tags for colors
        self.log_area.tag_config('INFO', foreground='#38bdf8')
        self.log_area.tag_config('WARNING', foreground='#fbbf24')
        self.log_area.tag_config('ERROR', foreground='#f87171')
        self.log_area.tag_config('CRITICAL', foreground='#ef4444', font=('Consolas', 9, 'bold'))

        # Register handler
        self.handler = TkLogHandler(self.log_area)
        logging.getLogger().addHandler(self.handler)
        
        # Capture previous logs from file if possible? (Optional)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def clear_logs(self):
        self.log_area.configure(state='normal')
        self.log_area.delete('1.0', tk.END)
        self.log_area.configure(state='disabled')

    def on_close(self):
        logging.getLogger().removeHandler(self.handler)
        self.destroy()
