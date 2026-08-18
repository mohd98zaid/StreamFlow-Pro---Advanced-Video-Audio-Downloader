"""
Theme and styling management for the application.
Following UI/UX Pro Max guidelines for modern, sleek desktop interface.
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any
import logging


import customtkinter as ctk

class StyleManager:
    """Manage application themes and styles with CustomTkinter integration"""
    
    def __init__(self, theme: str = "dark"):
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except:
            pass
        self.theme = theme
        self.colors: Dict[str, str] = {}
        self.font_family = "Segoe UI"
        self.apply_theme(theme)
    
    def apply_theme(self, theme: str = None) -> None:
        """
        Apply a theme to CustomTkinter and TTK widgets.
        
        Args:
            theme: Theme name ('light' or 'dark')
        """
        if theme:
            self.theme = theme.lower()
        
        # Apply CustomTkinter appearance mode
        if self.theme == "dark":
            ctk.set_appearance_mode("Dark")
            self.colors = {
                'bg': '#0F172A',            # Dark Slate 900
                'fg': '#F8FAFC',            # Slate 50
                'muted_fg': '#94A3B8',      # Slate 400
                'surface': '#1E293B',       # Slate 800
                'card_bg': '#1E293B',
                'card_border': '#334155',   # Slate 700
                'header_bg': '#151D2A',     # Deeper Header
                'primary': '#3B82F6',       # Blue 500
                'primary_hover': '#2563EB', # Blue 600
                'accent': '#8B5CF6',        # Violet 500
                'select': '#1D4ED8',        # Blue 700
                'error': '#EF4444',         # Red 500
                'success': '#10B981',       # Emerald 500
                'warning': '#F59E0B',       # Amber 500
                'tree_bg': '#1E293B',
                'tree_fg': '#F8FAFC',
                'tree_head_bg': '#151D2A',
                'tree_head_fg': '#60A5FA',
                'tree_alt': '#182234',
                'log_bg': '#0B1120',
                'log_fg': '#E2E8F0',
            }
        else:
            ctk.set_appearance_mode("Light")
            self.colors = {
                'bg': '#F8FAFC',            # Slate 50
                'fg': '#0F172A',            # Slate 900
                'muted_fg': '#64748B',      # Slate 500
                'surface': '#FFFFFF',       # Pure White Card
                'card_bg': '#FFFFFF',
                'card_border': '#E2E8F0',   # Slate 200
                'header_bg': '#EFF6FF',     # Soft Light Blue Header
                'primary': '#2563EB',       # Blue 600
                'primary_hover': '#1D4ED8', # Blue 700
                'accent': '#7C3AED',        # Violet 600
                'select': '#3B82F6',        # Blue 500
                'error': '#DC2626',         # Red 600
                'success': '#059669',       # Emerald 600
                'warning': '#D97706',       # Amber 600
                'tree_bg': '#FFFFFF',
                'tree_fg': '#0F172A',
                'tree_head_bg': '#F1F5F9',
                'tree_head_fg': '#2563EB',
                'tree_alt': '#F8FAFC',
                'log_bg': '#0F172A',
                'log_fg': '#F8FAFC',
            }
        
        self._configure_styles()
        logging.info(f"Applied {self.theme} theme via CustomTkinter")
    
    def _configure_styles(self) -> None:
        """Configure all ttk styles with modern typography & components"""
        # Primary Action Button
        self.style.configure(
            'Modern.TButton',
            background=self.colors['primary'],
            foreground='white',
            borderwidth=0,
            focuscolor='none',
            font=(self.font_family, 10, 'bold'),
            padding=(14, 8)
        )
        self.style.map(
            'Modern.TButton',
            background=[('active', self.colors['primary_hover']), ('disabled', self.colors['muted_fg'])],
            foreground=[('disabled', '#CBD5E1')]
        )
        
        # Secondary Action Button
        self.style.configure(
            'Secondary.TButton',
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['card_border'],
            borderwidth=1,
            relief='solid',
            focuscolor='none',
            font=(self.font_family, 9, 'bold'),
            padding=(12, 6)
        )
        self.style.map(
            'Secondary.TButton',
            background=[('active', self.colors['bg'])],
            foreground=[('active', self.colors['primary'])]
        )
        
        # Success Button
        self.style.configure(
            'Success.TButton',
            background=self.colors['success'],
            foreground='white',
            borderwidth=0,
            font=(self.font_family, 9, 'bold'),
            padding=(12, 6)
        )
        self.style.map(
            'Success.TButton',
            background=[('active', '#047857')]
        )
        
        # Danger / Cancel Button
        self.style.configure(
            'Danger.TButton',
            background=self.colors['error'],
            foreground='white',
            borderwidth=0,
            font=(self.font_family, 9, 'bold'),
            padding=(12, 6)
        )
        self.style.map(
            'Danger.TButton',
            background=[('active', '#B91C1C')]
        )
        
        # Frame styles
        self.style.configure('TFrame', background=self.colors['bg'])
        self.style.configure('Surface.TFrame', background=self.colors['surface'])
        
        # Card Labelframe
        self.style.configure(
            'TLabelframe',
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['card_border'],
            borderwidth=1,
            relief='solid',
            padding=12
        )
        self.style.configure(
            'TLabelframe.Label',
            background=self.colors['surface'],
            foreground=self.colors['primary'],
            font=(self.font_family, 10, 'bold')
        )
        
        # Entry and Combobox styles
        self.style.configure(
            'TEntry',
            fieldbackground=self.colors['surface'],
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            bordercolor=self.colors['card_border'],
            font=(self.font_family, 10),
            padding=6
        )
        self.style.configure(
            'TCombobox',
            fieldbackground=self.colors['surface'],
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            selectbackground=self.colors['select'],
            selectforeground='white',
            font=(self.font_family, 10),
            padding=6
        )
        
        # Treeview styles (32px rows, sleek headers)
        self.style.configure(
            'Treeview',
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            fieldbackground=self.colors['surface'],
            font=(self.font_family, 9),
            rowheight=32
        )
        self.style.configure(
            'Treeview.Heading',
            background=self.colors['header_bg'],
            foreground=self.colors['primary'],
            font=(self.font_family, 9, 'bold'),
            relief='flat',
            padding=6
        )
        self.style.map(
            'Treeview',
            background=[('selected', self.colors['select'])],
            foreground=[('selected', 'white')]
        )
        
        # Label styles
        self.style.configure(
            'TLabel',
            background=self.colors['bg'],
            foreground=self.colors['fg'],
            font=(self.font_family, 10)
        )
        self.style.configure(
            'Surface.TLabel',
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            font=(self.font_family, 10)
        )
        self.style.configure(
            'Title.TLabel',
            background=self.colors['header_bg'],
            foreground=self.colors['primary'],
            font=(self.font_family, 16, 'bold')
        )
        self.style.configure(
            'Subtitle.TLabel',
            background=self.colors['bg'],
            foreground=self.colors['muted_fg'],
            font=(self.font_family, 9)
        )
        self.style.configure(
            'HeaderSub.TLabel',
            background=self.colors['header_bg'],
            foreground=self.colors['muted_fg'],
            font=(self.font_family, 9)
        )
        self.style.configure(
            'MetricValue.TLabel',
            background=self.colors['surface'],
            foreground=self.colors['primary'],
            font=(self.font_family, 14, 'bold')
        )
        self.style.configure(
            'MetricTitle.TLabel',
            background=self.colors['surface'],
            foreground=self.colors['muted_fg'],
            font=(self.font_family, 9, 'bold')
        )
        
        # Checkbutton and Radiobutton styles
        self.style.configure(
            'TCheckbutton',
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            font=(self.font_family, 9)
        )
        self.style.configure(
            'TRadiobutton',
            background=self.colors['surface'],
            foreground=self.colors['fg'],
            font=(self.font_family, 9)
        )
        
        # Progressbar style
        self.style.configure(
            'TProgressbar',
            background=self.colors['primary'],
            troughcolor=self.colors['card_border'],
            thickness=10
        )
        
        # Notebook (tabs) style
        self.style.configure(
            'TNotebook',
            background=self.colors['bg'],
            borderwidth=0
        )
        self.style.configure(
            'TNotebook.Tab',
            background=self.colors['surface'],
            foreground=self.colors['muted_fg'],
            font=(self.font_family, 10, 'bold'),
            padding=(16, 8),
            borderwidth=0
        )
        self.style.map(
            'TNotebook.Tab',
            background=[('selected', self.colors['primary'])],
            foreground=[('selected', 'white')]
        )
    
    def get_color(self, color_name: str) -> str:
        """Get a color from the current theme"""
        return self.colors.get(color_name, '#000000')
    
    def configure_root_window(self, root: tk.Tk) -> None:
        """Configure root window with theme colors"""
        root.configure(bg=self.colors['bg'])

