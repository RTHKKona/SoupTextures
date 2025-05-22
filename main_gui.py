# SoupTextures - MHGU TEX Tool to end all Kuriimu tools
# Updated 2025-05-22
# v1.1

# main_gui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, UnidentifiedImageError # Ensure UnidentifiedImageError is imported
import os
import platform
# import copy # Not needed for this specific toggle undo
from typing import Optional

import constants as C
import tex_handler
import image_utils

# === Add these imports at the top ===
import sys
import argparse # For more robust CLI argument parsing
# winreg will be imported conditionally later for Windows-specific functions
# === End of new imports at top ===

class TexToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SoupTextures - MHGU v{C.MHGU_VERSION} TEX Tool (Aclios Swizzle)")
        self.root.configure(bg=C.BG_COLOR)
        self.root.geometry("1300x950")
        self.current_tex_file: Optional[tex_handler.TexFile] = None
        self.current_display_image: Optional[Image.Image] = None
        self.current_image_tk: Optional[ImageTk.PhotoImage] = None
        self.loaded_image_filepath: Optional[str] = None
        self.zoom_level = 1.0
        self.zoom_step = 0.2

        # For the "Set Opaque" / "Restore State Before Opaque" toggle
        self.image_state_before_set_opaque: Optional[Image.Image] = None # Stores image copy
        self.is_currently_opaque_by_toggle = False # True if "Set Alpha Opaque" was the last toggle action

        self.loaded_image_for_export: Optional[Image.Image] = None


        self._init_styles()
        self._init_ui()
        
        self.set_status("Ready.", C.STATUS_INFO_FG)
        self.add_info(f"Welcome to SoupTextures - MHGU v{C.MHGU_VERSION} TEX Tool!\nUsing Aclios swizzle logic.")
        self.root.after(100, lambda: self.display_image(self.current_display_image))

    def _init_styles(self):
        # Updated style configurations with Segoe UI font and smaller padding
        self.style = ttk.Style()
        if "clam" in self.style.theme_names(): self.style.theme_use('clam')
        self.style.configure("TFrame", background=C.BG_COLOR)
        self.style.configure("TLabel", background=C.BG_COLOR, foreground=C.TEXT_COLOR, font=("Segoe UI", 9))
        self.style.configure(
            "Header.TLabel", 
            font=("Segoe UI", 10, "bold"), 
            foreground=C.HEADER_TEXT, 
            background=C.HEADER_BG, 
            padding=(3, 1)
            )
        self.style.configure(
            "TButton", 
            background=C.BUTTON_BG, 
            foreground=C.BUTTON_FG, 
            bordercolor=C.BUTTON_BORDER_COLOR, 
            lightcolor=C.BUTTON_BG, 
            darkcolor=C.BUTTON_BG, 
            font=("Segoe UI", 9),
            padding=(3, 1),
            relief=tk.RAISED
        )
        self.style.map("TButton", 
            background=[('active', C.BUTTON_ACTIVE_BG), ('pressed', C.BUTTON_ACTIVE_BG), ('disabled', C.DISABLED_BUTTON_BG)], 
            foreground=[('disabled', C.DISABLED_BUTTON_FG)], 
            relief=[('pressed', tk.SUNKEN), ('!pressed', tk.RAISED)]
        )
        self.style.configure(
            "TCombobox", 
            fieldbackground=C.WIDGET_BG, 
            background=C.BUTTON_BG, 
            foreground=C.TEXT_COLOR,
            arrowcolor=C.TEXT_COLOR, 
            selectbackground=C.HIGHLIGHT_BG, 
            selectforeground=C.HIGHLIGHT_TEXT, 
            font=("Segoe UI", 9)
            )
        self.root.option_add("*TCombobox*Listbox*Background", C.WIDGET_BG)
        self.root.option_add("*TCombobox*Listbox*Foreground", C.INPUT_TEXT_COLOR)
        self.root.option_add("*TCombobox*Listbox*selectBackground", C.HIGHLIGHT_BG)
        self.root.option_add("*TCombobox*Listbox*selectForeground", C.HIGHLIGHT_TEXT)
        self.root.option_add("*TCombobox*Listbox*Font", ("Segoe UI", 9))


    def _init_ui(self):
        main_frame = ttk.Frame(self.root, padding="3")
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        main_frame.columnconfigure(0, weight=1, minsize=180)
        main_frame.columnconfigure(1, weight=5)
        main_frame.rowconfigure(0, weight=1)
        
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        
        display_frame = ttk.Frame(main_frame)
        display_frame.grid(row=0, column=1, sticky="nsew")

        ttk.Button(controls_frame, text="Import TEX", command=self.import_tex).pack(fill=tk.X, pady=2, padx=1)
        ttk.Button(controls_frame, text="Import PNG/DDS", command=self.import_png_dds).pack(fill=tk.X, pady=2, padx=1)
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)

        self.export_png_button = ttk.Button(controls_frame, text="Export to PNG", command=self.export_to_png, state=tk.DISABLED)
        self.export_png_button.pack(fill=tk.X, pady=2, padx=1)

        ttk.Label(controls_frame, text="Export TEX Format:").pack(fill=tk.X, pady=(3,0), padx=1)
        kukkii_export_formats = ["DXT1", "DXT5", "ATI1", "ATI2", "BGRA8888"]
        self.export_format_var = tk.StringVar(value="DXT5")
        self.export_format_combo = ttk.Combobox(controls_frame, textvariable=self.export_format_var, values=kukkii_export_formats, state="readonly")
        self.export_format_combo.pack(fill=tk.X, pady=2, padx=1)
        self.export_tex_button = ttk.Button(controls_frame, text="Export to TEX", command=self.export_to_tex, state=tk.DISABLED)
        self.export_tex_button.pack(fill=tk.X, pady=2, padx=1)
        
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)
        
        self.toggle_alpha_button = ttk.Button(controls_frame, text="Set Alpha Opaque", command=self.toggle_set_alpha_opaque, state=tk.DISABLED)
        self.toggle_alpha_button.pack(fill=tk.X, pady=2, padx=1)
        
        self.ensure_rgba_button = ttk.Button(controls_frame, text="Ensure RGBA Format", command=self.ensure_rgba_format, state=tk.DISABLED)
        self.ensure_rgba_button.pack(fill=tk.X, pady=2, padx=1)
        
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)

        zoom_frame = ttk.Frame(controls_frame)
        zoom_frame.pack(fill=tk.X, pady=2, padx=1)
        self.zoom_in_button = ttk.Button(zoom_frame, text="Zoom In (+)", command=self.zoom_in, state=tk.DISABLED)
        self.zoom_in_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,1))
        self.zoom_out_button = ttk.Button(zoom_frame, text="Zoom Out (-)", command=self.zoom_out, state=tk.DISABLED)
        self.zoom_out_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(1,0))
        
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)

        display_frame.rowconfigure(0, weight=1)
        display_frame.rowconfigure(1, weight=0)
        display_frame.columnconfigure(0, weight=1)
        
        self.image_canvas = tk.Canvas(display_frame, bg=C.WIDGET_BG, highlightthickness=0)
        self.image_canvas.grid(row=0, column=0, sticky="nsew", pady=(0,3))
        
        self.info_text_frame = ttk.Frame(display_frame)
        self.info_text_frame.grid(row=1, column=0, sticky="ew")
        self.info_text_frame.columnconfigure(0, weight=1)
        
        info_font = ("Segoe UI", 9) if platform.system() == "Windows" else ("Helvetica", 9)
        
        self.info_text = tk.Text(
            self.info_text_frame, 
            height=7,
            wrap=tk.WORD, 
            bg=C.INPUT_BG, 
            fg=C.TEXT_COLOR, 
            insertbackground=C.TEXT_COLOR, 
            relief=tk.FLAT, 
            font=info_font,
            borderwidth=0, 
            highlightthickness=0
        )
        self.info_text.grid(row=0, column=0, sticky="ew")
        
        info_scrollbar = ttk.Scrollbar(self.info_text_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        info_scrollbar.grid(row=0, column=1, sticky="ns")
        self.info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            padding=(4, 2),
            relief=tk.FLAT, 
            style="Header.TLabel", 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)


    def _reset_alpha_toggle_state(self, called_by_load=False):
        if called_by_load:
            self.image_state_before_set_opaque = None
        self.is_currently_opaque_by_toggle = False
        if hasattr(self, 'toggle_alpha_button'): 
            self.toggle_alpha_button.config(text="Set Alpha Opaque")

    def _update_display_and_sources(self, new_pil_image: Optional[Image.Image], called_by_alpha_toggle: bool = False):
        if not called_by_alpha_toggle: 
            self._reset_alpha_toggle_state(called_by_load=True)
            
        self.current_display_image = new_pil_image
        if self.current_tex_file and self.current_tex_file.image is not None:
            self.current_tex_file.image = new_pil_image
        elif self.loaded_image_for_export: 
            self.loaded_image_for_export = new_pil_image
        
        self.display_image(new_pil_image)

    def set_status(self, message, color=C.STATUS_INFO_FG): 
        self.status_var.set(message)
        self.status_label.config(foreground=color)

    def add_info(self, message): 
        self.info_text.config(state=tk.NORMAL)
        self.info_text.insert(tk.END, message + "\n")
        self.info_text.see(tk.END)
        self.info_text.config(state=tk.DISABLED)

    def update_ui_for_loaded_state(self):
        has_image = self.current_display_image is not None
        self.export_png_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.export_tex_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.toggle_alpha_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.ensure_rgba_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.zoom_in_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.zoom_out_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        
        if not has_image: 
            self._reset_alpha_toggle_state(called_by_load=True)


    def display_image(self, pil_image: Optional[Image.Image]):
        self.image_canvas.delete("all")
        actual_image_to_display = self.current_display_image 

        if actual_image_to_display:
            try:
                self.root.update_idletasks() 
                canvas_width = self.image_canvas.winfo_width()
                canvas_height = self.image_canvas.winfo_height()
                if canvas_width <= 1 or canvas_height <= 1: 
                    canvas_width, canvas_height = 400,300 # Default fallback
                
                img_for_tk = actual_image_to_display.copy()
                zoomed_w = int(img_for_tk.width * self.zoom_level)
                zoomed_h = int(img_for_tk.height * self.zoom_level)

                if zoomed_w > 0 and zoomed_h > 0:
                    if (zoomed_w, zoomed_h) != img_for_tk.size: 
                        img_for_tk = img_for_tk.resize((zoomed_w, zoomed_h), Image.Resampling.NEAREST if self.zoom_level >= 1.0 else Image.Resampling.LANCZOS)
                    self.current_image_tk = ImageTk.PhotoImage(img_for_tk)
                    self.image_canvas.create_image(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, image=self.current_image_tk)
                else: 
                    self.current_image_tk = None
                    self.image_canvas.create_text(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, text="Zoomed too small.", fill=C.TEXT_COLOR)
            except Exception as e:
                self.current_image_tk = None
                self.image_canvas.create_text(10,10, anchor=tk.NW, text=f"Preview error: {e}", fill=C.STATUS_ERROR_FG, width=max(100,self.image_canvas.winfo_width()-20))
        else:
            self.current_image_tk = None
            self.image_canvas.create_text(max(50,self.image_canvas.winfo_width()//2), max(50,self.image_canvas.winfo_height()//2), anchor=tk.CENTER, text="No image loaded.", fill=C.TEXT_COLOR)
        
        self.update_ui_for_loaded_state()

    def import_tex(self, filepath: Optional[str] = None):
        if filepath is None:
            filepath = filedialog.askopenfilename(title="Import MHGU TEX File", filetypes=(("TEX files", "*.tex"), ("All files", "*.*")))
        
        if not filepath: 
            return
        
        if not os.path.exists(filepath):
            self.set_status(f"Error: File not found - {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
            self.add_info(f"  File not found: {filepath}")
            self.current_tex_file = None
            self._update_display_and_sources(None) 
            return

        self.set_status(f"Loading TEX: {os.path.basename(filepath)}...", C.STATUS_INFO_FG)
        self.add_info(f"Attempting to load TEX: {filepath}")
        try:
            with open(filepath, "rb") as f: data = f.read()
            loaded_tex = tex_handler.load_tex_from_data(data)
            
            if loaded_tex:
                self.current_tex_file = loaded_tex
                self.current_tex_file.filepath = filepath
                self.loaded_image_for_export = None
                self.loaded_image_filepath = None
                
                self.set_status(f"Loaded {os.path.basename(filepath)}.", C.STATUS_SUCCESS_FG)
                self.add_info(
                    f"  Magic: {hex(self.current_tex_file.magic)} "
                    f"({'BigE' if self.current_tex_file.is_big_endian else 'LittleE'}), "
                    f"Version: {self.current_tex_file.version}, "
                    f"Format: {self.current_tex_file.get_format_str()}, "
                    f"Dims: {self.current_tex_file.width}x{self.current_tex_file.height}, "
                    f"Mipmaps: {self.current_tex_file.mip_map_count}"
                )

                self._update_display_and_sources(self.current_tex_file.image.copy() if self.current_tex_file.image else None, called_by_alpha_toggle=False)
                if self.current_display_image: self.add_info("  Image preview generated.")
                else: self.add_info("  Image data could not be decoded/previewed.")
            else:
                self.set_status(f"Failed to load TEX: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
                self.add_info(f"  Load failed (tex_handler returned None).")
                self.current_tex_file = None
                self._update_display_and_sources(None)
        except Exception as e: 
            self.set_status(f"Outer error loading TEX: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  Exception in import_tex: {e}")
            self.current_tex_file = None
            self._update_display_and_sources(None)

    def import_png_dds(self):
        filepath = filedialog.askopenfilename(title="Import PNG or DDS File", filetypes=(("Image files", "*.png *.dds"),("All files", "*.*")))
        if not filepath: return
        self.set_status(f"Loading image: {os.path.basename(filepath)}...", C.STATUS_INFO_FG)
        self.add_info(f"Attempting to load image: {filepath}")
        try:
            pil_image = image_utils.load_image_from_path(filepath)
            if pil_image:
                self.loaded_image_for_export = pil_image.convert("RGBA")
                self.loaded_image_filepath = filepath
                
                if self.current_tex_file:
                    self.add_info(f"  Imported image. Previous TEX header info kept (if any). TEX image data replaced.")
                else:
                     self.add_info(f"  Imported image. New MHGU header will be used for TEX export.")
                
                self._update_display_and_sources(self.loaded_image_for_export.copy(), called_by_alpha_toggle=False)
                self.set_status(f"Image {os.path.basename(filepath)} loaded.", C.STATUS_SUCCESS_FG)
                self.add_info(f"  Loaded image: {pil_image.width}x{pil_image.height}")
            else:
                self.set_status(f"Failed to load/convert: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
                self.add_info(f"  Image load/conversion failed.")
        except UnidentifiedImageError:
            self.set_status(f"Cannot identify image file: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
            self.add_info(f"  Error: Cannot identify image file. It might be corrupted or an unsupported format.")
        except Exception as e:
            self.set_status(f"Error loading image: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  Exception: {e}")


    def toggle_set_alpha_opaque(self):
        if not self.current_display_image:
            self.set_status("No image loaded to modify.", C.STATUS_INFO_FG)
            return

        new_image_state: Optional[Image.Image] = None
        action_message = ""

        if not self.is_currently_opaque_by_toggle:
            if self.image_state_before_set_opaque is None:
                 self.image_state_before_set_opaque = self.current_display_image.copy()

            modified_image = self.current_display_image.copy()
            if modified_image.mode != "RGBA":
                modified_image = modified_image.convert("RGBA")
            
            opaque_alpha = Image.new('L', modified_image.size, 255) 
            modified_image.putalpha(opaque_alpha)
            
            new_image_state = modified_image
            self.is_currently_opaque_by_toggle = True
            self.toggle_alpha_button.config(text="Undo Set Alpha Opaque")
            action_message = "Image alpha channel set to opaque."
        else:
            if self.image_state_before_set_opaque:
                new_image_state = self.image_state_before_set_opaque.copy() 
                action_message = "Restored image to state before 'Set Alpha Opaque'."
            else: 
                new_image_state = self.current_display_image.copy() # Fallback
                if new_image_state.mode != "RGBA": new_image_state = new_image_state.convert("RGBA")
                action_message = "No prior state to restore; ensured RGBA."
            
            self.is_currently_opaque_by_toggle = False
            self.toggle_alpha_button.config(text="Set Alpha Opaque")

        if new_image_state:
            self._update_display_and_sources(new_image_state, called_by_alpha_toggle=True)
            self.set_status(action_message, C.STATUS_SUCCESS_FG)

    def ensure_rgba_format(self): 
        if not self.current_display_image:
            self.set_status("No image loaded.", C.STATUS_INFO_FG); return
        
        if self.current_display_image.mode != "RGBA":
            modified_image = self.current_display_image.convert("RGBA")
            self._update_display_and_sources(modified_image.copy(), called_by_alpha_toggle=False) 
            self.set_status("Image format ensured to be RGBA.", C.STATUS_SUCCESS_FG)
            self.add_info("Image converted to RGBA (alpha preserved or added).")
        else:
            self.set_status("Image is already RGBA.", C.STATUS_INFO_FG)
            self.add_info("Image is already RGBA format.")
            
    def export_to_png(self):
        if not self.current_display_image: 
            messagebox.showwarning("Export PNG", "No image loaded.")
            return
        default_name = "exported_image.png"
        if self.current_tex_file and self.current_tex_file.filepath: 
            default_name = f"{os.path.splitext(os.path.basename(self.current_tex_file.filepath))[0]}.png"
        elif self.loaded_image_filepath: 
            default_name = f"{os.path.splitext(os.path.basename(self.loaded_image_filepath))[0]}_edited.png"
        
        save_filepath = filedialog.asksaveasfilename(title="Export Image as PNG", defaultextension=".png", initialfile=default_name, filetypes=(("PNG files", "*.png"),))
        if not save_filepath: return
        try:
            self.current_display_image.save(save_filepath, "PNG")
            self.set_status(f"Image exported to PNG: {os.path.basename(save_filepath)}", C.STATUS_SUCCESS_FG)
            self.add_info(f"  Saved PNG: {save_filepath}")
        except Exception as e:
            self.set_status(f"Error exporting PNG: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  PNG Export Exception: {e}")

    def export_to_tex(self):
        current_image_for_export = self.current_display_image

        if not current_image_for_export: 
            messagebox.showerror("Export Error", "No image data to export.")
            return

        base_tex_for_header_info = self.current_tex_file if self.current_tex_file else tex_handler.TexFile()
        
        if not self.current_tex_file: 
            base_tex_for_header_info.version = C.MHGU_VERSION
            base_tex_for_header_info.magic = C.MAGIC_TEX_BIG 
            base_tex_for_header_info.is_big_endian = True
            base_tex_for_header_info.k_unk1 = 0 
            base_tex_for_header_info.k_unused1 = 0
            base_tex_for_header_info.alpha_flags = 1 
            base_tex_for_header_info.k_unk2 = 0
            base_tex_for_header_info.k_unk3 = 0
        
        base_tex_for_header_info.width = current_image_for_export.width
        base_tex_for_header_info.height = current_image_for_export.height

        default_name = "exported_mhgu.tex"
        if self.loaded_image_filepath:
            default_name = f"{os.path.splitext(os.path.basename(self.loaded_image_filepath))[0]}.tex"
        elif base_tex_for_header_info.filepath:
             default_name = f"{os.path.splitext(os.path.basename(base_tex_for_header_info.filepath))[0]}_exp.tex"
        
        save_filepath = filedialog.asksaveasfilename(title="Save MHGU TEX File As", defaultextension=".tex", initialfile=default_name, filetypes=(("TEX files", "*.tex"),))
        if not save_filepath: return
        
        export_format_str = self.export_format_var.get()
        self.set_status(f"Exporting to {export_format_str}...", C.STATUS_INFO_FG)
        self.add_info(f"  Target format: {export_format_str}")
        try:
            tex_byte_data = tex_handler.save_tex_to_data(base_tex_for_header_info, current_image_for_export, export_format_str)
            if tex_byte_data:
                with open(save_filepath, "wb") as f: f.write(tex_byte_data)
                self.set_status(f"Exported to {os.path.basename(save_filepath)}.", C.STATUS_SUCCESS_FG)
                self.add_info(f"  Saved {len(tex_byte_data)} bytes.")
            else: 
                self.set_status("Export failed (tex_handler returned None).", C.STATUS_ERROR_FG)
                self.add_info("  Export failed (tex_handler returned None). Check console for details.")
        except Exception as e: 
            self.set_status(f"Error during export: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  Export Exception: {e}")

    def zoom_in(self):
        if not self.current_display_image: return
        self.zoom_level = round(min(self.zoom_level + self.zoom_step, 5.0), 2) 
        self._update_display_and_sources(self.current_display_image.copy(), called_by_alpha_toggle=True)
        self.set_status(f"Zoom: {int(self.zoom_level*100)}%", C.STATUS_INFO_FG)

    def zoom_out(self):
        if not self.current_display_image: return
        self.zoom_level = round(max(self.zoom_level - self.zoom_step, 0.1), 2) 
        self._update_display_and_sources(self.current_display_image.copy(), called_by_alpha_toggle=True)
        self.set_status(f"Zoom: {int(self.zoom_level*100)}%", C.STATUS_INFO_FG)

    def check_tex_validity(self): # This method needs tex_handler.check_tex_type to be implemented
        filepath = filedialog.askopenfilename(title="Select TEX File to Check", filetypes=(("TEX files", "*.tex"),))
        if not filepath: return
        self.add_info(f"Checking validity: {os.path.basename(filepath)}")
        try:
            with open(filepath, "rb") as f: data = f.read(32) # Read enough for header check
            # Assuming check_tex_type exists and returns a string or None
            # result = tex_handler.check_tex_type(data) # This function is not in the provided tex_handler.py
            # Placeholder implementation:
            if data[:4] == C.MAGIC_TEX_LITTLE.to_bytes(4, 'little') or \
               data[:4] == C.MAGIC_TEX_BIG.to_bytes(4, 'big'):
                result = "Valid TEX Magic Found"
            else:
                result = None

            if result: 
                self.add_info(f"  Validation: {result}")
                messagebox.showinfo("TEX Validity", f"File: {os.path.basename(filepath)}\nType: {result}\n(Basic magic check)")
            else: 
                self.add_info(f"  Validation: Unknown/invalid TEX.")
                messagebox.showwarning("TEX Validity", f"File: {os.path.basename(filepath)}\nInvalid/unknown MTF TEX.")
        except Exception as e: 
            self.add_info(f"  Error checking: {e}")
            messagebox.showerror("Validation Error", f"Could not check: {e}")


# === HEADLESS CONVERSION FUNCTION ===
def headless_convert_tex_to_png(input_tex_path: str, output_png_path: Optional[str] = None):
    if not os.path.exists(input_tex_path):
        print(f"ERROR: Input TEX file not found: {input_tex_path}")
        return 1

    # Dependency check for texconv (crucial for DXT formats)
    # if not image_utils.check_texconv():
    #     print(f"ERROR: texconv.exe not found at '{os.path.abspath(image_utils.TEXCONV_PATH)}'. "
    #           "Cannot decode DXT/BCn formats which might be required.")
        # If you want to be strict and always require it for headless:
        # return 1

    print(f"Attempting to convert '{os.path.basename(input_tex_path)}' to PNG...")

    try:
        with open(input_tex_path, "rb") as f:
            data = f.read()
        
        loaded_tex = tex_handler.load_tex_from_data(data)

        if not loaded_tex:
            print(f"ERROR: Failed to load TEX file: {input_tex_path} (tex_handler returned None).")
            return 1
        
        if not loaded_tex.image:
            err_msg = f"ERROR: TEX file loaded, but no image data could be decoded: {input_tex_path}"
            err_msg += f"\n  TEX Info: Version={loaded_tex.version}, Format={loaded_tex.get_format_str()}, Dims={loaded_tex.width}x{loaded_tex.height}"
            if loaded_tex.is_dxt_format() and not image_utils.check_texconv():
                 err_msg += "\n  NOTE: This is a DXT/BCn format and texconv.exe is missing or not found. Decoding will fail."
            print(err_msg)
            return 1

        if output_png_path is None:
            base, _ = os.path.splitext(input_tex_path)
            output_png_path = base + ".png"
        
        output_dir = os.path.dirname(output_png_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")
            except OSError as e:
                print(f"ERROR: Could not create output directory '{output_dir}': {e}")
                return 1
        
        loaded_tex.image.save(output_png_path, "PNG")
        print(f"SUCCESS: Successfully converted '{os.path.basename(input_tex_path)}' to '{os.path.basename(output_png_path)}'")
        print(f"  Full output path: {output_png_path}")
        return 0

    except Exception as e:
        print(f"ERROR: An unexpected error occurred during conversion of '{input_tex_path}': {e}")
        # import traceback # For detailed debugging
        # traceback.print_exc()
        return 1

# === REGISTRY AND CLI HANDLING ===
PROG_ID = "SoupTextures.MHGUTexFile.1"
FILE_EXT = ".tex"
APP_DESCRIPTION = "MHGU Texture File (SoupTextures)"

if platform.system() == "Windows":
    import winreg

    CONTEXT_MENU_COMMAND_NAME = "SoupTexConvertToPNG"
    CONTEXT_MENU_DISPLAY_TEXT = "Convert to .PNG (SoupTextures)"

    def _get_open_with_command():
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            app_path = sys.executable
            return f'"{app_path}" "%1"'
        else:
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            python_exe_to_use = pythonw_exe if os.path.exists(pythonw_exe) else python_exe
            return f'"{python_exe_to_use}" "{script_path}" "%1"'

    def setup_windows_file_association():
        try:
            command = _get_open_with_command()
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, FILE_EXT) as key_ext:
                winreg.SetValueEx(key_ext, None, 0, winreg.REG_SZ, PROG_ID)
            
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, PROG_ID) as key_prog_id:
                winreg.SetValueEx(key_prog_id, None, 0, winreg.REG_SZ, APP_DESCRIPTION)
                
                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    icon_path = f'"{sys.executable}",0'
                else:
                    python_exe_for_icon = sys.executable
                    pythonw_exe_for_icon = os.path.join(os.path.dirname(python_exe_for_icon), "pythonw.exe")
                    icon_path = f'"{pythonw_exe_for_icon if os.path.exists(pythonw_exe_for_icon) else python_exe_for_icon}",0'

                with winreg.CreateKey(key_prog_id, "DefaultIcon") as key_icon:
                    winreg.SetValueEx(key_icon, None, 0, winreg.REG_SZ, icon_path)
                
                with winreg.CreateKey(key_prog_id, r"shell\open\command") as key_shell_open_cmd:
                    winreg.SetValueEx(key_shell_open_cmd, None, 0, winreg.REG_SZ, command)
            
            messagebox.showinfo("File Association Setup", 
                                f"Successfully registered {FILE_EXT} files to open with this application.\n"
                                "Changes may require restarting Windows Explorer or a system reboot to take full effect.")
            print(f"Successfully set up file association for {FILE_EXT}.")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to set up file associations...")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Registration Error", f"An error occurred: {e}")
            print(f"Error setting up file association: {e}")

    def remove_windows_file_association():
        try:
            keys_to_delete = [PROG_ID] # More complex removal might be needed for FILE_EXT default
            # For simplicity, just removing the ProgID. To fully clean FILE_EXT, one might
            # need to know what the previous handler was or set it to a known system default.
            # This will remove our app's specific ProgID.

            # Check if PROG_ID is default for FILE_EXT, if so, clear it (optional, can be risky)
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, FILE_EXT, 0, winreg.KEY_READ) as key_ext_read:
                    current_prog_id, _ = winreg.QueryValueEx(key_ext_read, None) # Reads (Default)
                if current_prog_id == PROG_ID:
                    # If our app is the default, you might want to clear this.
                    # This is delicate. For now, we'll just remove our ProgID itself.
                    # winreg.SetValueEx(key_ext_write, None, 0, winreg.REG_SZ, "") # Example: set to empty
                    print(f"Note: {PROG_ID} was the default handler for {FILE_EXT}.")
            except FileNotFoundError:
                pass # .tex key doesn't exist or has no default.
            except Exception as e_read:
                print(f"Could not read default for {FILE_EXT}: {e_read}")


            # Delete ProgID and its subkeys
            sub_keys_of_prog_id = [r"shell\open\command", r"shell\open", r"shell", "DefaultIcon"]
            for sub_key in sub_keys_of_prog_id:
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, rf"{PROG_ID}\{sub_key}")
                except FileNotFoundError:
                    pass # Key already gone or never existed
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, PROG_ID)
            except FileNotFoundError:
                pass

            messagebox.showinfo("File Association Removal",
                                f"Attempted to unregister {PROG_ID}.\n"
                                "Changes may require restarting Windows Explorer or a system reboot.")
            print(f"Attempted to remove file association for {PROG_ID}.")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to remove file associations...")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Unregistration Error", f"An error occurred: {e}")
            print(f"Error removing file association: {e}")


    def setup_context_menu_item():
        if not (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')):
            messagebox.showwarning("Context Menu Setup Warning",
                                   "Context menu registration is intended to be run by the compiled .exe application "
                                   "to ensure correct paths.\nRunning from a Python script will register "
                                   "the script itself, which is likely not the desired deployed behavior.")

        try:
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, PROG_ID) as key_prog_id_check:
                    pass 
            except FileNotFoundError:
                messagebox.showerror("Prerequisite Missing",
                                     f"The Program ID '{PROG_ID}' is not registered for .tex files.\n"
                                     f"Please run your application with '--register-assoc' first to set up the basic file type association.")
                print(f"ERROR: ProgID '{PROG_ID}' not found. Run --register-assoc first.")
                return

            app_executable_path = sys.executable
            command_str = f'"{app_executable_path}" --convert-to-png "%1"'
            base_key_path = rf"{PROG_ID}\shell\{CONTEXT_MENU_COMMAND_NAME}"

            with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, base_key_path) as key_cmd_verb:
                winreg.SetValueEx(key_cmd_verb, None, 0, winreg.REG_SZ, CONTEXT_MENU_DISPLAY_TEXT)
                winreg.SetValueEx(key_cmd_verb, "Icon", 0, winreg.REG_SZ, f'"{app_executable_path}",0')

            with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, rf"{base_key_path}\command") as key_cmd_action:
                winreg.SetValueEx(key_cmd_action, None, 0, winreg.REG_SZ, command_str)

            messagebox.showinfo("Context Menu Setup",
                                f"Successfully added '{CONTEXT_MENU_DISPLAY_TEXT}' to .tex file context menu "
                                f"(associated with ProgID '{PROG_ID}').\n"
                                "Changes may require restarting Windows Explorer.")
            print(f"Successfully set up context menu item: '{CONTEXT_MENU_DISPLAY_TEXT}'")
            print(f"  Command: {command_str}")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to modify the registry for context menus...")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Context Menu Registration Error", f"An error occurred: {e}")
            print(f"Error setting up context menu item: {e}")

    def remove_context_menu_item():
        try:
            command_key_path = rf"{PROG_ID}\shell\{CONTEXT_MENU_COMMAND_NAME}\command"
            verb_key_path = rf"{PROG_ID}\shell\{CONTEXT_MENU_COMMAND_NAME}"

            try: winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, command_key_path)
            except FileNotFoundError: pass
            try: winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, verb_key_path)
            except FileNotFoundError: pass

            messagebox.showinfo("Context Menu Removal",
                                f"Attempted to remove '{CONTEXT_MENU_DISPLAY_TEXT}' from .tex file context menu.\n"
                                "Changes may require restarting Windows Explorer.")
            print(f"Attempted to remove context menu item: '{CONTEXT_MENU_DISPLAY_TEXT}'")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to modify the registry...")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Context Menu Unregistration Error", f"An error occurred: {e}")
            print(f"Error removing context menu item: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"SoupTextures - MHGU TEX Tool v{C.MHGU_VERSION}", add_help=True)
    
    reg_group = parser.add_argument_group('Registry Actions (require Administrator privileges)')
    reg_group.add_argument("--register-assoc", action="store_true", help="Register .tex file 'Open With' association to this app's GUI.")
    reg_group.add_argument("--unregister-assoc", action="store_true", help="Unregister .tex file 'Open With' association.")
    reg_group.add_argument("--register-context-menu", action="store_true", help="Register 'Convert to .PNG' context menu for .tex files.")
    reg_group.add_argument("--unregister-context-menu", action="store_true", help="Unregister 'Convert to .PNG' context menu.")
    
    convert_group = parser.add_argument_group('Headless Conversion')
    convert_group.add_argument("--convert-to-png", metavar="INPUT_TEX", help="Convert specified .tex file to .png headlessly.")
    convert_group.add_argument("--output-png", metavar="OUTPUT_PNG", help="Optional output path for .png conversion (default: input_file.png).")
    
    # For GUI: A single optional positional argument for the file to open.
    parser.add_argument("gui_file", nargs='?', default=None, help="Path to a .tex file to open in the GUI (optional).")

    args = parser.parse_args()
    cli_action_taken = False

    if platform.system() == "Windows":
        if args.register_assoc or args.unregister_assoc or \
           args.register_context_menu or args.unregister_context_menu:
            temp_root = tk.Tk()
            temp_root.withdraw()
            if args.register_assoc: setup_windows_file_association()
            if args.unregister_assoc: remove_windows_file_association()
            if args.register_context_menu: setup_context_menu_item()
            if args.unregister_context_menu: remove_context_menu_item()
            temp_root.destroy()
            cli_action_taken = True
            sys.exit(0)

    if args.convert_to_png:
        if not image_utils.check_texconv(): # Check texconv for headless conversion
             print(f"WARNING: texconv.exe (expected at '{os.path.abspath(image_utils.TEXCONV_PATH)}') "
                   "not found. DXT/BCn features may fail during headless conversion.")
        exit_code = headless_convert_tex_to_png(args.convert_to_png, args.output_png)
        cli_action_taken = True
        sys.exit(exit_code)

    # If no CLI action was taken, proceed to GUI launch
    if not cli_action_taken:
        # Texconv check for GUI startup message
        if not image_utils.check_texconv():
            _tk_root_for_startup_msg = tk.Tk()
            _tk_root_for_startup_msg.withdraw()
            messagebox.showwarning("Dependency Check",
                                   f"texconv.exe (expected at '{os.path.abspath(image_utils.TEXCONV_PATH)}') "
                                   "not found. DXT/BCn features will fail.", parent=None)
            _tk_root_for_startup_msg.destroy()

        app_root = tk.Tk()
        app = TexToolApp(app_root)

        gui_file_to_open = args.gui_file
        if gui_file_to_open and os.path.isfile(gui_file_to_open):
            if gui_file_to_open.lower().endswith(FILE_EXT):
                app_root.after(100, lambda fp=gui_file_to_open: app.import_tex(filepath=fp))
            else:
                app.set_status(f"Cannot open: {os.path.basename(gui_file_to_open)} (not a {FILE_EXT} file)", C.STATUS_ERROR_FG)
                app.add_info(f"Attempted to open non-{FILE_EXT} file via command line: {gui_file_to_open}")
        
        app_root.mainloop()