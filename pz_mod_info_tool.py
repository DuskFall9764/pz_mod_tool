#!/usr/bin/env python3
"""
Dusk's Project Zomboid Mod Browser

The main purpose of the creation for this app was to assist server owners that have to deal with finding each mod name and workshopID indavidually — THE STONE AGES ARE OVER!

A simple desktop application for scanning downloaded Project Zomboid Steam Workshop mods.
Provides functionality to:
- Scan mod folder
- Display mod information in a sortable table with search/filter
- Copy mod details to clipboard (individual or bulk)
- Export filtered results to CSV

Author: DuskFall (discord: duskfall_)
Version: 2.0.0
Requirements: Python 3.7+
License: MIT
"""

import os
import sys
import csv
import webbrowser
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

# -------- Defaults --------
DEFAULT_MOD_PATH = os.path.expandvars(
    r"%ProgramFiles(x86)%\Steam\steamapps\workshop\content\108600"
) if sys.platform.startswith("win") else ""

# -------- Modern dark palette --------
C = {
    "bg": "#0b1117",
    "card": "#0f1722",
    "card_hi": "#162133",
    "muted": "#182236",
    "stroke": "#223248",
    "text": "#e9eef6",
    "sub": "#a6b4c4",
    "accent": "#5bb7ff",
    "row_even": "#121b28",
    "row_odd": "#0c141e",
    "sel": "#1a3c5f",
    "hover": "#224b74",
}

RIGHT_CARD_W = 360  # fixed width for the details panel

# -------- Error Handling --------
def _fatal(msg: str) -> None:
    """
    Handle fatal application errors with comprehensive logging and user notification.
    
    Attempts to:
    1. Write error details to a log file for debugging
    2. Display error message to user via GUI dialog
    3. Print to console as fallback
    4. Wait for user acknowledgment before exit
    
    Args:
        msg: Detailed error message including stack trace
    """
    # Try to save error log for debugging
    try:
        with open("pz_mod_tool_error.log", "w", encoding="utf-8") as f:
            f.write(f"PZ Mod Info Tool - Fatal Error\n")
            f.write(f"{'='*50}\n\n")
            f.write(msg)
    except Exception:
        pass  # Don't let logging errors prevent error display
    
    # Try to show GUI error dialog
    try:
        messagebox.showerror("Fatal Error - PZ Mod Info Tool", 
            f"The application encountered a fatal error and must close.\n\n"
            f"Error details have been saved to 'pz_mod_tool_error.log'\n\n"
            f"Error: {msg.split('\n')[0] if msg else 'Unknown error'}")
    except Exception:
        pass  # GUI might not be available
    
    # Always print to console
    print(f"\n{'='*60}")
    print("PZ MOD INFO TOOL - FATAL ERROR")
    print(f"{'='*60}")
    print(msg)
    print(f"{'='*60}")
    
    # Wait for user acknowledgment
    try:
        input("\nPress Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass  # Handle cases where input isn't available

def _install_tk_callback_error_dialog(root: tk.Tk) -> None:
    """
    Install a global error handler for tkinter callback exceptions.
    
    Replaces the default tkinter error handling with our custom fatal error
    handler to ensure GUI errors are properly logged and displayed to users.
    
    Args:
        root: The main tkinter window instance
    """
    def _error_handler(exc_type, exc_value, exc_traceback) -> None:
        """Handle tkinter callback exceptions."""
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        _fatal(f"GUI Error: {error_msg}")
        
    root.report_callback_exception = _error_handler


class ModInfoApp:
    """
    Main application class for Project Zomboid Mod Info Tool.
    
    A modern GUI application that provides comprehensive mod management functionality
    including scanning, filtering, sorting, and exporting Project Zomboid Steam Workshop mods.
    
    Features:
    - Automatic scanning of Steam Workshop mod directories
    - Real-time search and filtering across all mod fields
    - Sortable columns with intelligent numeric sorting for Workshop IDs
    - Multiple clipboard copy options (all info, mod ID only, workshop ID only)
    - CSV export functionality with current filter applied
    - Right-click context menu with additional actions
    - Keyboard shortcuts (Ctrl+A for select all, Ctrl+C for copy)
    - Responsive UI with hover effects and modern styling
    - Robust error handling with detailed logging
    
    Attributes:
        root: Main tkinter window instance
        mod_folder: StringVar containing current mod folder path
        search_var: StringVar containing current search/filter text
        status_var: StringVar containing current status message
        mods: List of dictionaries containing parsed mod information
        tree: Treeview widget displaying the mod table
    """
    
    def __init__(self, root: tk.Tk) -> None:
        """
        Initialize the ModInfoApp with UI setup and event bindings.
        
        Args:
            root: The main tkinter window instance
        """
        self.root = root
        self.root.title("PZ Mod Info Tool")
        self.root.geometry("1200x720")
        self.root.configure(bg=C["bg"])

        # Application state
        self.mod_folder = tk.StringVar(
            value=DEFAULT_MOD_PATH if os.path.isdir(DEFAULT_MOD_PATH) else ""
        )
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")
        self.mods: List[Dict[str, str]] = []  # Parsed mod information
        self._sort_dir: Dict[str, bool] = {}  # Column sort directions
        self._last_hover: Optional[str] = None  # Last hovered tree item

        # Initialize UI components
        self._setup_style()
        self._build_ui()
        self._bind_keys()

        # Lock minimum size to prevent layout issues
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

    # ---------- Style ----------
    def _setup_style(self) -> None:
        """
        Configure the application's visual theme and styling.
        
        Sets up a modern dark theme with consistent color palette,
        typography, and widget styling for professional appearance.
        Applies custom styles for different UI components including
        frames, labels, buttons, entries, and the main data table.
        """
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            # Fallback to default theme if clam is unavailable
            pass

        tkfont.nametofont("TkDefaultFont").configure(size=10, family="Segoe UI")
        self._hfont = ("Segoe UI", 14, "bold")
        self._sfont = ("Segoe UI", 9)

        style.configure("TFrame", background=C["bg"])
        style.configure("Card.TFrame", background=C["card"], relief="flat")
        style.configure("CardHi.TFrame", background=C["card_hi"], relief="flat")
        style.configure("Stroke.TFrame", background=C["stroke"], height=1)

        style.configure("TLabel", background=C["bg"], foreground=C["text"])
        style.configure("Card.TLabel", background=C["card"], foreground=C["text"])
        style.configure("Sub.TLabel", background=C["card"], foreground=C["sub"])

        style.configure("TEntry", fieldbackground=C["muted"], foreground=C["text"], relief="flat")
        style.map("TEntry", fieldbackground=[("focus", C["card_hi"])])

        style.configure("Tool.TButton", padding=6, relief="flat")
        style.map("Tool.TButton",
                  background=[("!disabled", C["card_hi"]), ("active", C["sel"])],
                  foreground=[("!disabled", C["text"])])

        style.configure("Treeview",
                        background=C["card"],
                        fieldbackground=C["card"],
                        foreground=C["text"],
                        rowheight=28,
                        borderwidth=0,
                        highlightthickness=0)
        style.configure("Treeview.Heading",
                        background=C["card_hi"],
                        foreground=C["sub"],
                        relief="flat",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", C["sel"])],
                  foreground=[("selected", C["text"])])

    # ---------- UI ----------
    def _build_ui(self) -> None:
        """
        Build the complete user interface layout.
        
        Creates and organizes all UI components including:
        - Application header with title and controls
        - Search/filter input section
        - Main data table with sortable columns
        - Details panel showing selected mod information
        - Action buttons for copy/export operations
        - Status bar for user feedback
        
        The layout uses a modern card-based design with proper spacing
        and responsive behavior.
        """
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True, padx=16, pady=12)

        # Title (uses window bg; no dark strip)
        appbar = ttk.Frame(outer)
        appbar.pack(fill="x", padx=2, pady=(0, 12))
        ttk.Label(appbar, text="Dusk's PZ Mod Browser", font=self._hfont).pack(
            side="left", padx=4, pady=4
        )

        # Right controls
        bar_right = ttk.Frame(appbar, style="CardHi.TFrame")
        bar_right.pack(side="right")
        ttk.Label(bar_right, text="Workshop Folder:", style="Card.TLabel").pack(side="left", padx=(10,6), pady=6)
        self.path_entry = ttk.Entry(bar_right, textvariable=self.mod_folder, width=55)
        self.path_entry.pack(side="left", pady=6)
        ttk.Button(bar_right, text="Browse", style="Tool.TButton", command=self.browse_folder).pack(side="left", padx=6, pady=6)
        ttk.Button(bar_right, text="Scan", style="Tool.TButton", command=self.scan_mods).pack(side="left", padx=6, pady=6)
        ttk.Button(bar_right, text="Export CSV", style="Tool.TButton", command=self.export_csv).pack(side="left", padx=6, pady=6)

        # Search card
        search_card = ttk.Frame(outer, style="Card.TFrame")
        search_card.pack(fill="x", padx=2, pady=(0, 12))
        srow = ttk.Frame(search_card, style="Card.TFrame"); srow.pack(fill="x", padx=12, pady=10)
        ttk.Label(srow, text="Search", style="Card.TLabel").pack(side="left")
        s_entry = ttk.Entry(srow, textvariable=self.search_var, width=50)
        s_entry.pack(side="left", padx=(10,6))
        s_entry.bind("<KeyRelease>", self._on_search)
        ttk.Button(srow, text="Clear", style="Tool.TButton", command=self._clear_search).pack(side="left")

        # Main content
        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True)

        # Left table card
        left_card = ttk.Frame(main, style="Card.TFrame")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(left_card, text="Mods", style="Card.TLabel").pack(anchor="w", padx=12, pady=(10,0))

        table_wrap = ttk.Frame(left_card, style="Card.TFrame"); table_wrap.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("Name", "ModID", "WorkshopID")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", selectmode="extended")
        for c in cols:
            self.tree.heading(c, text=c, command=lambda col=c: self._sort_by(col))
        # fixed widths to prevent flicker
        self.tree.column("Name", width=560, anchor="w", stretch=False)
        self.tree.column("ModID", width=300, anchor="w", stretch=False)
        self.tree.column("WorkshopID", width=160, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_wrap.rowconfigure(0, weight=1); table_wrap.columnconfigure(0, weight=1)

        self.tree.tag_configure("even", background=C["row_even"])
        self.tree.tag_configure("odd", background=C["row_odd"])
        self.tree.tag_configure("hover", background=C["hover"])

        self.tree.bind("<<TreeviewSelect>>", self._update_details)
        self.tree.bind("<Motion>", self._hover_row)
        self.tree.bind("<Leave>", lambda e: self._clear_hover())

        # Right details card (fixed width, no propagation)
        right_card = ttk.Frame(main, style="Card.TFrame", width=RIGHT_CARD_W)
        right_card.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        right_card.grid_propagate(False)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(0, weight=1)

        ttk.Label(right_card, text="Details", style="Card.TLabel").pack(anchor="w", padx=12, pady=(10,0))
        dwrap = ttk.Frame(right_card, style="Card.TFrame"); dwrap.pack(fill="both", expand=True, padx=12, pady=8)

        self.d_name = tk.StringVar(value="Select a mod to see details")
        self.d_modid = tk.StringVar()
        self.d_wid = tk.StringVar()

        self.name_lbl = ttk.Label(dwrap, textvariable=self.d_name,
                                  style="Card.TLabel", font=("Segoe UI", 12, "bold"),
                                  wraplength=RIGHT_CARD_W-24, justify="left")
        self.name_lbl.pack(anchor="w", pady=(4,6))
        ttk.Frame(dwrap, style="Stroke.TFrame").pack(fill="x", pady=4)

        ttk.Label(dwrap, text="Mod ID", style="Sub.TLabel").pack(anchor="w", pady=(2,0))
        self.modid_lbl = ttk.Label(dwrap, textvariable=self.d_modid,
                                   style="Card.TLabel", font=self._sfont,
                                   wraplength=RIGHT_CARD_W-24, justify="left")
        self.modid_lbl.pack(anchor="w")
        ttk.Frame(dwrap, style="Stroke.TFrame").pack(fill="x", pady=4)

        ttk.Label(dwrap, text="Workshop ID", style="Sub.TLabel").pack(anchor="w", pady=(2,0))
        self.wid_lbl = ttk.Label(dwrap, textvariable=self.d_wid,
                                 style="Card.TLabel", font=("Segoe UI", 9, "bold"),
                                 wraplength=RIGHT_CARD_W-24, justify="left")
        self.wid_lbl.pack(anchor="w")
        try:
            self.wid_lbl.configure(foreground=C["accent"])
        except Exception:
            pass

        ttk.Frame(right_card, style="Stroke.TFrame").pack(fill="x", padx=12, pady=8)
        actions = ttk.Frame(right_card, style="Card.TFrame"); actions.pack(fill="x", padx=12, pady=(0,12))
        ttk.Button(actions, text="Copy All", style="Tool.TButton", command=self.copy_selected).pack(fill="x", pady=4)
        ttk.Button(actions, text="Copy ModID", style="Tool.TButton", command=self.copy_modid).pack(fill="x", pady=4)
        ttk.Button(actions, text="Copy WorkshopID", style="Tool.TButton", command=self.copy_workshopid).pack(fill="x", pady=4)
        ttk.Button(actions, text="Open Folder", style="Tool.TButton", command=self.open_folder).pack(fill="x", pady=4)
        ttk.Button(actions, text="Clear Selection", style="Tool.TButton", command=self._clear_selection).pack(fill="x", pady=4)

        status = ttk.Frame(outer, style="CardHi.TFrame")
        status.pack(fill="x", padx=2, pady=(12, 0))
        ttk.Label(status, textvariable=self.status_var, style="Sub.TLabel").pack(side="left", padx=12, pady=6)

    # ---------- Hover ----------
    def _hover_row(self, event):
        iid = self.tree.identify_row(event.y)
        if iid == self._last_hover:
            return
        if self._last_hover and self.tree.exists(self._last_hover):
            tags = [t for t in self.tree.item(self._last_hover, "tags") if t != "hover"]
            self.tree.item(self._last_hover, tags=tags)
        if iid:
            tags = list(self.tree.item(iid, "tags"))
            if "hover" not in tags:
                tags.append("hover")
            self.tree.item(iid, tags=tags)
        self._last_hover = iid

    def _clear_hover(self):
        if self._last_hover and self.tree.exists(self._last_hover):
            tags = [t for t in self.tree.item(self._last_hover, "tags") if t != "hover"]
            self.tree.item(self._last_hover, tags=tags)
        self._last_hover = None

    # ---------- Event Bindings ----------
    def _bind_keys(self) -> None:
        """
        Set up keyboard shortcuts and context menu for enhanced usability.
        
        Keyboard shortcuts:
        - Ctrl+A: Select all visible mods
        - Ctrl+C: Copy selected mods (complete info)
        - Double-click: Copy selected mod
        - Right-click: Show context menu
        
        Context menu includes:
        - Copy options (all info, mod ID only, workshop ID only)
        - Open current folder in system file explorer
        """
        # Keyboard shortcuts (handle both cases for caps lock)
        self.root.bind("<Control-a>", self._select_all)
        self.root.bind("<Control-A>", self._select_all)
        self.root.bind("<Control-c>", self._copy_hotkey)
        self.root.bind("<Control-C>", self._copy_hotkey)
        
        # Double-click to copy
        self.tree.bind("<Double-1>", lambda e: self.copy_selected())
        
        # Right-click context menu
        self._menu = tk.Menu(self.root, tearoff=0)
        self._menu.add_command(label="Copy All Info", command=self.copy_selected)
        self._menu.add_command(label="Copy ModID Only", command=self.copy_modid)
        self._menu.add_command(label="Copy WorkshopID Only", command=self.copy_workshopid)
        self._menu.add_separator()
        self._menu.add_command(label="Open Folder in Explorer", command=self.open_folder)
        self.tree.bind("<Button-3>", self._popup_menu)

    # ---------- Actions ----------
    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.mod_folder.get() or None)
        if folder:
            self.mod_folder.set(folder)

    def open_folder(self):
        path = self.mod_folder.get().strip()
        if not os.path.isdir(path):
            messagebox.showerror("Error", "Folder does not exist."); return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                webbrowser.open(f"file://{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder:\n{e}")

    def scan_mods(self) -> None:
        """
        Scan the specified directory for Project Zomboid mod information.
        
        Iterates through all subdirectories in the selected folder, attempts to
        locate and parse mod.info files, and populates the mod list with discovered
        information. Updates the UI in real-time with progress and results.
        
        Handles various error conditions gracefully including:
        - Missing or invalid folder paths
        - Permission errors when accessing directories
        - Malformed or missing mod.info files
        - Large directories with progress feedback
        """
        folder_path = self.mod_folder.get().strip()
        
        # Validate input
        if not folder_path:
            messagebox.showerror("Error", "Please select a folder to scan.")
            return
            
        if not os.path.isdir(folder_path):
            messagebox.showerror("Error", f"Folder does not exist: {folder_path}")
            return

        # Clear previous results and update UI
        self.mods.clear()
        self.tree.delete(*self.tree.get_children())
        self.status_var.set("Scanning…")
        self.root.update_idletasks()

        scanned_count = 0
        found_count = 0
        
        try:
            # Use os.scandir for better performance than os.listdir
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        scanned_count += 1
                        
                        # Update progress for large directories
                        if scanned_count % 25 == 0:
                            self.status_var.set(f"Scanning… ({scanned_count} folders checked)")
                            self.root.update_idletasks()
                        
                        mod_info = self._read_mod_info(entry.path, entry.name)
                        if mod_info:
                            self.mods.append(mod_info)
                            found_count += 1
                            
        except PermissionError:
            messagebox.showerror("Error", f"Permission denied accessing: {folder_path}")
        except OSError as e:
            messagebox.showerror("Error", f"System error reading folder: {e}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Unexpected error during scan: {e}")
        finally:
            self._apply_filter()
            self.status_var.set(f"Found {found_count} mods (scanned {scanned_count} folders)")

    # ---- Parser
    def _read_mod_info(self, mod_path: str, workshopid: str) -> Optional[Dict[str, str]]:
        """
        Parse mod information from a mod.info file in the given directory.
        
        Searches for mod.info file in the root directory and subdirectories,
        then extracts the mod name and ID using robust parsing that handles
        various file formats and encoding issues.
        
        Args:
            mod_path: Path to the mod directory to search
            workshopid: Workshop ID (typically the directory name)
            
        Returns:
            Dictionary with 'name', 'modid', and 'workshopid' keys, or None if parsing fails
            
        Note:
            Handles various edge cases including:
            - UTF-8 BOM characters
            - Quoted values with single or double quotes
            - Comments and malformed lines
            - Multi-value ID fields (takes first value)
            - Different encoding formats
        """
        def find_modinfo(root: str) -> Optional[str]:
            """Recursively search for mod.info file."""
            # Check root directory first for performance
            direct_path = os.path.join(root, "mod.info")
            if os.path.isfile(direct_path):
                return direct_path
                
            # Search subdirectories if not found in root
            try:
                for subroot, _dirs, files in os.walk(root):
                    if "mod.info" in files:
                        return os.path.join(subroot, "mod.info")
            except (OSError, PermissionError):
                # Skip directories we can't access
                pass
                
            return None
            
        mod_info_path = find_modinfo(mod_path)
        if not mod_info_path:
            return None

        name = modid = None
        
        try:
            # Handle various encodings and BOM characters
            with open(mod_info_path, "r", encoding="utf-8-sig", errors="replace") as f:
                for line_num, raw_line in enumerate(f, 1):
                    # Prevent reading extremely long files (likely corrupted)
                    if line_num > 500:
                        break
                        
                    line = raw_line.strip()
                    
                    # Skip empty lines, comments, and malformed lines
                    if (not line or "=" not in line or 
                        line.startswith("#") or line.startswith("//")):
                        continue
                        
                    try:
                        key, value = line.split("=", 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"').strip("'")
                        
                        if key == "name" and not name and value:
                            name = value
                        elif key == "id" and not modid and value:
                            # Handle multi-value IDs (semicolon separated)
                            modid = value.split(";")[0].strip()
                            
                        # Early exit if we have both required fields
                        if name and modid:
                            break
                            
                    except ValueError:
                        # Skip malformed lines
                        continue
                        
            # Return parsed information if we have required fields
            if name and modid:
                return {
                    "name": name,
                    "modid": modid,
                    "workshopid": str(workshopid)
                }
                
        except (OSError, IOError):
            # File access error - silently skip this mod
            pass
        except Exception as e:
            # Log unexpected errors but don't crash the scan
            print(f"Warning: Error parsing {mod_info_path}: {e}")
            
        return None

    # ---- Table operations
    def _apply_filter(self) -> None:
        """
        Apply current search filter to the mod list and update the table display.
        
        Filters the mod list based on the current search query, performing
        case-insensitive matching across mod name, mod ID, and workshop ID fields.
        Updates the table with alternating row colors and refreshes the status bar
        with current counts.
        """
        query = self.search_var.get().lower().strip()
        
        # Clear existing table entries
        self.tree.delete(*self.tree.get_children())
        
        # Filter mods based on search query
        filtered_rows = []
        for mod in self.mods:
            if (not query or 
                query in mod["name"].lower() or 
                query in mod["modid"].lower() or 
                query in mod["workshopid"].lower()):
                filtered_rows.append((mod["name"], mod["modid"], mod["workshopid"]))
        
        # Populate table with filtered results and alternating colors
        for index, values in enumerate(filtered_rows):
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.insert("", "end", values=values, tags=(tag,))
            
        # Update status and details panel
        self.status_var.set(f"{len(filtered_rows)} shown / {len(self.mods)} total")
        self._update_details()

    def _on_search(self, _=None):
        self._apply_filter()

    def _clear_search(self):
        self.search_var.set("")
        self._apply_filter()

    def _update_details(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            self.d_name.set("Select a mod to see details"); self.d_modid.set(""); self.d_wid.set(""); return
        name, modid, wid = self.tree.item(sel[0], "values")
        self.d_name.set(name); self.d_modid.set(modid); self.d_wid.set(wid)

    def _popup_menu(self, e) -> None:
        """
        Display right-click context menu at mouse position.
        
        Args:
            e: Tkinter mouse event containing cursor coordinates
        """
        try:
            self._menu.tk_popup(e.x_root, e.y_root)
        finally:
            self._menu.grab_release()

    def _select_all(self, _=None) -> str:
        """
        Select all visible mods in the table.
        
        Used by Ctrl+A keyboard shortcut to select all currently displayed mods.
        
        Args:
            _: Tkinter event object (unused, for compatibility)
            
        Returns:
            "break" to prevent default event handling
        """
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _copy_hotkey(self, _=None) -> str:
        """
        Handle Ctrl+C keyboard shortcut to copy selected mods.
        
        Args:
            _: Tkinter event object (unused, for compatibility)
            
        Returns:
            "break" to prevent default event handling
        """
        self.copy_selected()
        return "break"

    def _clear_selection(self) -> None:
        """
        Clear all selected items in the table and update the UI.
        
        Removes selection from all table items, updates the details panel,
        and provides user feedback via the status bar.
        """
        for item_id in self.tree.selection():
            self.tree.selection_remove(item_id)
        self._update_details()
        self.status_var.set("Selection cleared.")

    # -------- Table Sorting --------
    def _sort_by(self, col: str) -> None:
        """
        Sort table by specified column with intelligent type handling.
        
        Handles different data types appropriately:
        - WorkshopID: Numeric sorting with fallback to string
        - Name/ModID: Case-insensitive alphabetic sorting
        
        Maintains alternating row colors after sorting and toggles
        sort direction for consecutive clicks on the same column.
        
        Args:
            col: Column name to sort by ("Name", "ModID", or "WorkshopID")
        """
        items = list(self.tree.get_children())
        if not items:
            return
            
        # Map column names to indices
        column_indices = {"Name": 0, "ModID": 1, "WorkshopID": 2}
        column_index = column_indices[col]
        
        # Get current sort direction (toggle on repeat clicks)
        reverse_sort = self._sort_dir.get(col, False)

        def sort_key(item_id: str) -> Union[int, str]:
            """
            Generate appropriate sort key based on column type.
            
            Args:
                item_id: Tree item identifier
                
            Returns:
                Sort key (int for WorkshopID, lowercase string for others)
            """
            value = self.tree.item(item_id, "values")[column_index]
            
            # Special handling for WorkshopID (numeric sort)
            if column_index == 2:  # WorkshopID column
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return (value or "").lower()  # Fallback to string sort
            
            # String sorting for Name and ModID columns
            return (value or "").lower()

        # Sort items using appropriate key function
        items.sort(key=sort_key, reverse=reverse_sort)
        
        # Reorder items in tree and refresh alternating colors
        for position, item_id in enumerate(items):
            self.tree.move(item_id, "", position)
            tag = "even" if position % 2 == 0 else "odd"
            self.tree.item(item_id, tags=(tag,))
            
        # Toggle sort direction for next click
        self._sort_dir[col] = not reverse_sort

    # -------- Clipboard Operations --------
    def _clipboard_set(self, text: str) -> None:
        """
        Safely set clipboard contents with error handling.
        
        Clears existing clipboard content and sets new text.
        Handles potential clipboard access issues gracefully.
        
        Args:
            text: Text content to copy to clipboard
        """
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            # Clipboard access might fail in some environments
            pass

    def copy_selected(self) -> None:
        """
        Copy complete information for all selected mods to clipboard.
        
        Formats each selected mod as "Name=...; ID=...; WorkshopID=..."
        with one mod per line. Shows user feedback via status bar and
        displays informational message if no mods are selected.
        """
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Copy", "No mods selected.")
            return
            
        lines = []
        for item_id in selection:
            name, modid, workshop_id = self.tree.item(item_id, "values")
            lines.append(f"Name={name}; ID={modid}; WorkshopID={workshop_id}")
            
        self._clipboard_set("\n".join(lines))
        self.status_var.set(f"Copied {len(selection)} mod(s) - complete info.")

    def copy_modid(self) -> None:
        """
        Copy only the Mod IDs for all selected mods to clipboard.
        
        Extracts just the mod ID field from selected rows, with one ID per line.
        Useful for creating mod lists for server configurations or mod managers.
        """
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Copy", "No mods selected.")
            return
            
        mod_ids = [self.tree.item(item_id, "values")[1] for item_id in selection]
        self._clipboard_set("\n".join(mod_ids))
        self.status_var.set(f"Copied {len(mod_ids)} Mod ID(s).")

    def copy_workshopid(self) -> None:
        """
        Copy only the Workshop IDs for all selected mods to clipboard.
        
        Extracts just the workshop ID field from selected rows, with one ID per line.
        Useful for Steam Workshop URLs or bulk mod operations.
        """
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Copy", "No mods selected.")
            return
            
        workshop_ids = [self.tree.item(item_id, "values")[2] for item_id in selection]
        self._clipboard_set("\n".join(workshop_ids))
        self.status_var.set(f"Copied {len(workshop_ids)} Workshop ID(s).")

    def export_csv(self) -> None:
        """
        Export currently filtered mod data to a CSV file.
        
        Opens a file save dialog and exports all mods that match the current
        search filter to a CSV file with headers. Handles encoding properly
        for international characters in mod names.
        
        The exported CSV includes columns: Name, ModID, WorkshopID
        """
        if not self.mods:
            messagebox.showinfo("Export", "No mods to export. Please scan a folder first.")
            return
            
        # Get save file path from user
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="pz_mods.csv",
            title="Export Mod Data"
        )
        
        if not file_path:
            return  # User cancelled
            
        # Apply current filter to determine which mods to export
        query = self.search_var.get().lower().strip()
        filtered_mods = [
            mod for mod in self.mods 
            if (not query or 
                query in mod["name"].lower() or 
                query in mod["modid"].lower() or 
                query in mod["workshopid"].lower())
        ]
        
        try:
            # Write CSV with proper encoding for international characters
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header row
                writer.writerow(["Name", "ModID", "WorkshopID"])
                
                # Write mod data
                for mod in filtered_mods:
                    writer.writerow([mod["name"], mod["modid"], mod["workshopid"]])
                    
            self.status_var.set(f"Successfully exported {len(filtered_mods)} mods to CSV.")
            
        except PermissionError:
            messagebox.showerror("Export Error", 
                f"Permission denied writing to: {file_path}\n\n"
                "The file may be open in another program.")
        except OSError as e:
            messagebox.showerror("Export Error", f"System error writing file: {e}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Unexpected error during export: {e}")


def main() -> None:
    """
    Main application entry point.
    
    Initializes the tkinter root window, sets up global error handling,
    creates the main application instance, and starts the GUI event loop.
    
    Handles any uncaught exceptions gracefully by logging them and
    displaying user-friendly error messages.
    """
    try:
        # Create and configure main window
        root = tk.Tk()
        
        # Install global error handler for tkinter callbacks
        _install_tk_callback_error_dialog(root)
        
        # Create main application
        app = ModInfoApp(root)
        
        # Start GUI event loop
        root.mainloop()
        
    except ImportError as e:
        _fatal(f"Missing required Python modules: {e}\n\n"
               "Please ensure Python and tkinter are properly installed.")
    except Exception as e:
        error_msg = "".join(traceback.format_exc())
        _fatal(f"Application failed to start: {e}\n\n{error_msg}")

if __name__ == "__main__":
    main()