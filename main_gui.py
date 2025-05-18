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

        # This attribute seems to be used in _update_display_and_sources but not initialized.
        # Assuming it was intended or should be initialized, e.g., when an image is imported.
        # For now, initializing to None to prevent potential AttributeError if accessed before set.
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
            padding=(3, 1)  # Reduced padding
            )
        self.style.configure(
            "TButton", 
            background=C.BUTTON_BG, 
            foreground=C.BUTTON_FG, 
            bordercolor=C.BUTTON_BORDER_COLOR, 
            lightcolor=C.BUTTON_BG, 
            darkcolor=C.BUTTON_BG, 
            font=("Segoe UI", 9),  # Changed to Segoe UI
            padding=(3, 1),  # Reduced padding for slimmer buttons
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
            foreground=C.TEXT_COLOR,  # Changed from C.INPUT_TEXT_COLOR to C.TEXT_COLOR
            arrowcolor=C.TEXT_COLOR, 
            selectbackground=C.HIGHLIGHT_BG, 
            selectforeground=C.HIGHLIGHT_TEXT, 
            font=("Segoe UI", 9)  # Changed to Segoe UI
            )
        self.root.option_add("*TCombobox*Listbox*Background", C.WIDGET_BG)
        self.root.option_add("*TCombobox*Listbox*Foreground", C.INPUT_TEXT_COLOR)
        self.root.option_add("*TCombobox*Listbox*selectBackground", C.HIGHLIGHT_BG)
        self.root.option_add("*TCombobox*Listbox*selectForeground", C.HIGHLIGHT_TEXT)
        self.root.option_add("*TCombobox*Listbox*Font", ("Segoe UI", 9))  # Added font for dropdown list


    def _init_ui(self):
        # Main layout with adjusted proportions for left panel (controls)
        main_frame = ttk.Frame(self.root, padding="3")  # Reduced overall padding
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Configure columns with better proportions - making controls panel narrower
        main_frame.columnconfigure(0, weight=1, minsize=180)  # Reduced from 220 to 180
        main_frame.columnconfigure(1, weight=5)  # Increased weight for better proportion
        main_frame.rowconfigure(0, weight=1)
        
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3))  # Reduced padding
        
        display_frame = ttk.Frame(main_frame)
        display_frame.grid(row=0, column=1, sticky="nsew")

        # Buttons with reduced padding
        ttk.Button(controls_frame, text="Import TEX", command=self.import_tex).pack(fill=tk.X, pady=2, padx=1)  # Reduced pady from 3 to 2
        ttk.Button(controls_frame, text="Import PNG/DDS", command=self.import_png_dds).pack(fill=tk.X, pady=2, padx=1)
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)  # Slightly reduced separator padding

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
        #ttk.Button(controls_frame, text="Check TEX File Validity", command=self.check_tex_validity).pack(fill=tk.X, pady=(3,2), padx=1)

        display_frame.rowconfigure(0, weight=1)
        display_frame.rowconfigure(1, weight=0)
        display_frame.columnconfigure(0, weight=1)
        
        self.image_canvas = tk.Canvas(display_frame, bg=C.WIDGET_BG, highlightthickness=0)
        self.image_canvas.grid(row=0, column=0, sticky="nsew", pady=(0,3))  # Reduced padding
        
        self.info_text_frame = ttk.Frame(display_frame)
        self.info_text_frame.grid(row=1, column=0, sticky="ew")
        self.info_text_frame.columnconfigure(0, weight=1)
        
        # Use Segoe UI for info text on Windows, appropriate alternative on other platforms
        info_font = ("Segoe UI", 9) if platform.system() == "Windows" else ("Helvetica", 9)
        
        self.info_text = tk.Text(
            self.info_text_frame, 
            height=7,  # Slightly reduced height
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
        
        # Status bar with reduced padding
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            padding=(4, 2),  # Reduced padding
            relief=tk.FLAT, 
            style="Header.TLabel", 
            anchor=tk.W
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)


    def _reset_alpha_toggle_state(self, called_by_load=False):
        """Resets the alpha toggle state. If called by image load, also clears stored image."""
        if called_by_load:
            self.image_state_before_set_opaque = None
        self.is_currently_opaque_by_toggle = False
        if hasattr(self, 'toggle_alpha_button'): # Ensure button exists
            self.toggle_alpha_button.config(text="Set Alpha Opaque")

    def _update_display_and_sources(self, new_pil_image: Optional[Image.Image], called_by_alpha_toggle: bool = False):
        if not called_by_alpha_toggle: # Any other image change resets the toggle's saved state
            self._reset_alpha_toggle_state(called_by_load=True) # called_by_load will clear image_state_before_set_opaque
            
        self.current_display_image = new_pil_image
        if self.current_tex_file and self.current_tex_file.image is not None:
            self.current_tex_file.image = new_pil_image
        elif self.loaded_image_for_export: # Check this if no current_tex_file or its image is None
            self.loaded_image_for_export = new_pil_image
        
        self.display_image(new_pil_image) # This will call update_ui_for_loaded_state

    def set_status(self, message, color=C.STATUS_INFO_FG): self.status_var.set(message); self.status_label.config(foreground=color)
    def add_info(self, message): self.info_text.config(state=tk.NORMAL); self.info_text.insert(tk.END, message + "\n"); self.info_text.see(tk.END); self.info_text.config(state=tk.DISABLED)

    def update_ui_for_loaded_state(self):
        has_image = self.current_display_image is not None
        self.export_png_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.export_tex_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.toggle_alpha_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.ensure_rgba_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.zoom_in_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        self.zoom_out_button.config(state=tk.NORMAL if has_image else tk.DISABLED)
        
        if not has_image: # Also reset toggle state if image becomes None
            self._reset_alpha_toggle_state(called_by_load=True)


    def display_image(self, pil_image: Optional[Image.Image]):
        # self.current_display_image should already be set by the caller (_update_display_and_sources)
        self.image_canvas.delete("all")
        actual_image_to_display = self.current_display_image # Use the class member

        if actual_image_to_display:
            try:
                self.root.update_idletasks() 
                canvas_width = self.image_canvas.winfo_width(); canvas_height = self.image_canvas.winfo_height()
                if canvas_width <= 1 or canvas_height <= 1: canvas_width, canvas_height = 400,300
                
                img_for_tk = actual_image_to_display.copy() # Work with a copy for Tk display
                zoomed_w = int(img_for_tk.width * self.zoom_level); zoomed_h = int(img_for_tk.height * self.zoom_level)

                if zoomed_w > 0 and zoomed_h > 0:
                    if (zoomed_w, zoomed_h) != img_for_tk.size: 
                        img_for_tk = img_for_tk.resize((zoomed_w, zoomed_h), Image.Resampling.NEAREST if self.zoom_level >= 1.0 else Image.Resampling.LANCZOS)
                    self.current_image_tk = ImageTk.PhotoImage(img_for_tk)
                    self.image_canvas.create_image(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, image=self.current_image_tk)
                else: 
                    self.current_image_tk = None; self.image_canvas.create_text(canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, text="Zoomed too small.", fill=C.TEXT_COLOR)
            except Exception as e:
                self.current_image_tk = None; self.image_canvas.create_text(10,10, anchor=tk.NW, text=f"Preview error: {e}", fill=C.STATUS_ERROR_FG, width=max(100,self.image_canvas.winfo_width()-20))
        else:
            self.current_image_tk = None; self.image_canvas.create_text(max(50,self.image_canvas.winfo_width()//2), max(50,self.image_canvas.winfo_height()//2), anchor=tk.CENTER, text="No image loaded.", fill=C.TEXT_COLOR)
        
        self.update_ui_for_loaded_state() # Update button states after display change

    def import_tex(self):
        filepath = filedialog.askopenfilename(title="Import MHGU TEX File", filetypes=(("TEX files", "*.tex"), ("All files", "*.*")))
        if not filepath: return
        self.set_status(f"Loading TEX: {os.path.basename(filepath)}...", C.STATUS_INFO_FG)
        self.add_info(f"Attempting to load TEX: {filepath}")
        try:
            with open(filepath, "rb") as f: data = f.read()
            loaded_tex = tex_handler.load_tex_from_data(data)
            
            if loaded_tex:
                self.current_tex_file = loaded_tex
                self.current_tex_file.filepath = filepath
                self.loaded_image_for_export = None; self.loaded_image_filepath = None
                
                self.set_status(f"Loaded {os.path.basename(filepath)}.", C.STATUS_SUCCESS_FG)
                self.add_info(f"  Magic: {hex(self.current_tex_file.magic)} ({'BigE' if self.current_tex_file.is_big_endian else 'LittleE'})" # ... other info ...
                )
                # ... (all other add_info calls for tex details) ...

                # _update_display_and_sources handles setting self.current_display_image and resetting alpha toggle
                self._update_display_and_sources(self.current_tex_file.image.copy() if self.current_tex_file.image else None, called_by_alpha_toggle=False) # Pass a copy
                if self.current_display_image: self.add_info("  Image preview generated.")
                else: self.add_info("  Image data could not be decoded/previewed.")
            else:
                self.set_status(f"Failed to load TEX: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
                self.add_info(f"  Load failed (tex_handler returned None).")
                self.current_tex_file = None; self._update_display_and_sources(None)
        except Exception as e: 
            self.set_status(f"Outer error loading TEX: {e}", C.STATUS_ERROR_FG); self.add_info(f"  Exception in import_tex: {e}")
            self.current_tex_file = None; self._update_display_and_sources(None)

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
                
                if self.current_tex_file: self.add_info(f"  Imported image. Previous TEX header info kept.")
                else: self.add_info(f"  Imported image. New MHGU header for TEX export.")
                
                self._update_display_and_sources(self.loaded_image_for_export.copy(), called_by_alpha_toggle=False) # Pass a copy
                self.set_status(f"Image {os.path.basename(filepath)} loaded.", C.STATUS_SUCCESS_FG)
                self.add_info(f"  Loaded image: {pil_image.width}x{pil_image.height}")
            else:
                self.set_status(f"Failed to load/convert: {os.path.basename(filepath)}", C.STATUS_ERROR_FG); self.add_info(f"  Image load/conversion failed.")
        except UnidentifiedImageError: # Specific handling for PIL's unidentified image error
            self.set_status(f"Cannot identify image file: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
            self.add_info(f"  Error: Cannot identify image file. It might be corrupted or an unsupported format.")
        except Exception as e:
            self.set_status(f"Error loading image: {e}", C.STATUS_ERROR_FG); self.add_info(f"  Exception: {e}")


    def toggle_set_alpha_opaque(self):
        if not self.current_display_image:
            self.set_status("No image loaded to modify.", C.STATUS_INFO_FG)
            return

        new_image_state: Optional[Image.Image] = None
        action_message = ""

        if not self.is_currently_opaque_by_toggle:
            # Action: Set Alpha Opaque
            # Store the current state *before* modification, only if not already stored by a previous "Set Opaque"
            if self.image_state_before_set_opaque is None:
                 self.image_state_before_set_opaque = self.current_display_image.copy()

            modified_image = self.current_display_image.copy()
            if modified_image.mode != "RGBA":
                modified_image = modified_image.convert("RGBA")
            
            opaque_alpha = Image.new('L', modified_image.size, 255) # Alpha channel of all 255s
            modified_image.putalpha(opaque_alpha)
            
            new_image_state = modified_image
            self.is_currently_opaque_by_toggle = True
            self.toggle_alpha_button.config(text="Undo Set Alpha Opaque")
            action_message = "Image alpha channel set to opaque."
        else:
            # Action: Undo Set Alpha Opaque (Restore to state before first "Set Opaque")
            if self.image_state_before_set_opaque:
                new_image_state = self.image_state_before_set_opaque.copy() # Restore the originally saved state
                # self.image_state_before_set_opaque = None # Keep it for further toggles until new image load
                action_message = "Restored image to state before 'Set Alpha Opaque'."
            else: # Should not happen if logic is correct, but as a fallback:
                new_image_state = self.current_display_image.convert("RGBA") # Ensure RGBA (likely already is)
                action_message = "No prior state to restore; ensured RGBA (opaque)."
            
            self.is_currently_opaque_by_toggle = False
            self.toggle_alpha_button.config(text="Set Alpha Opaque")

        if new_image_state:
            self._update_display_and_sources(new_image_state, called_by_alpha_toggle=True)
            self.set_status(action_message, C.STATUS_SUCCESS_FG)
            # self.add_info(action_message) # add_info is now part of _update_display_and_sources

    def ensure_rgba_format(self): 
        if not self.current_display_image:
            self.set_status("No image loaded.", C.STATUS_INFO_FG); return
        
        if self.current_display_image.mode != "RGBA":
            modified_image = self.current_display_image.convert("RGBA")
            self._update_display_and_sources(modified_image.copy(), called_by_alpha_toggle=False) # This will reset alpha toggle state
            self.set_status("Image format ensured to be RGBA.", C.STATUS_SUCCESS_FG)
            self.add_info("Image converted to RGBA (alpha preserved or added).")
        else:
            self.set_status("Image is already RGBA.", C.STATUS_INFO_FG)
            self.add_info("Image is already RGBA format.")
            
    def export_to_png(self):
        if not self.current_display_image: messagebox.showwarning("Export PNG", "No image loaded."); return
        default_name = "exported_image.png"
        if self.current_tex_file and self.current_tex_file.filepath: default_name = f"{os.path.splitext(os.path.basename(self.current_tex_file.filepath))[0]}.png"
        elif self.loaded_image_filepath: default_name = f"{os.path.splitext(os.path.basename(self.loaded_image_filepath))[0]}_edited.png"
        save_filepath = filedialog.asksaveasfilename(title="Export Image as PNG", defaultextension=".png", initialfile=default_name, filetypes=(("PNG files", "*.png"),))
        if not save_filepath: return
        try:
            self.current_display_image.save(save_filepath, "PNG"); self.set_status(f"Image exported to PNG", C.STATUS_SUCCESS_FG); self.add_info(f"  Saved PNG: {save_filepath}")
        except Exception as e:
            self.set_status(f"Error exporting PNG: {e}", C.STATUS_ERROR_FG); self.add_info(f"  PNG Export Exception: {e}")

    def export_to_tex(self):
        if not self.current_display_image: messagebox.showerror("Export Error", "No image data to export."); return
        base_tex_for_header_info = self.current_tex_file if self.current_tex_file else tex_handler.TexFile()
        if not self.current_tex_file: 
            base_tex_for_header_info.version = C.MHGU_VERSION
            base_tex_for_header_info.magic = C.MAGIC_TEX_BIG 
            base_tex_for_header_info.is_big_endian = True
        
        # Ensure the base_tex_for_header_info has correct current dimensions
        base_tex_for_header_info.width = self.current_display_image.width
        base_tex_for_header_info.height = self.current_display_image.height

        default_name = "exported_mhgu.tex"
        if self.loaded_image_filepath: default_name = f"{os.path.splitext(os.path.basename(self.loaded_image_filepath))[0]}.tex"
        elif base_tex_for_header_info.filepath: default_name = f"{os.path.splitext(os.path.basename(base_tex_for_header_info.filepath))[0]}_exp.tex"
        
        save_filepath = filedialog.asksaveasfilename(title="Save MHGU TEX File As", defaultextension=".tex", initialfile=default_name, filetypes=(("TEX files", "*.tex"),))
        if not save_filepath: return
        export_format_str = self.export_format_var.get()
        self.set_status(f"Exporting to {export_format_str}...", C.STATUS_INFO_FG); self.add_info(f"  Target format: {export_format_str}")
        try:
            tex_byte_data = tex_handler.save_tex_to_data(base_tex_for_header_info, self.current_display_image, export_format_str)
            if tex_byte_data:
                with open(save_filepath, "wb") as f: f.write(tex_byte_data)
                self.set_status(f"Exported to {os.path.basename(save_filepath)}.", C.STATUS_SUCCESS_FG); self.add_info(f"  Saved {len(tex_byte_data)} bytes.")
            else: self.set_status("Export failed.", C.STATUS_ERROR_FG); self.add_info("  Export failed.")
        except Exception as e: self.set_status(f"Error during export: {e}", C.STATUS_ERROR_FG); self.add_info(f"  Export Exception: {e}")

    def zoom_in(self):
        if not self.current_display_image: return
        self.zoom_level = round(min(self.zoom_level + self.zoom_step, 5.0), 2) # Max 500%
        # Pass current_display_image.copy() to ensure a new PhotoImage is generated if needed,
        # and called_by_alpha_toggle=True to prevent resetting alpha toggle logic if it's not an actual image content change.
        self._update_display_and_sources(self.current_display_image.copy(), called_by_alpha_toggle=True)
        self.set_status(f"Zoom: {int(self.zoom_level*100)}%", C.STATUS_INFO_FG)

    def zoom_out(self):
        if not self.current_display_image: return
        self.zoom_level = round(max(self.zoom_level - self.zoom_step, 0.1), 2) # Min 10%
        self._update_display_and_sources(self.current_display_image.copy(), called_by_alpha_toggle=True)
        self.set_status(f"Zoom: {int(self.zoom_level*100)}%", C.STATUS_INFO_FG)

    def check_tex_validity(self):
        filepath = filedialog.askopenfilename(title="Select TEX File to Check", filetypes=(("TEX files", "*.tex"),))
        if not filepath: return
        self.add_info(f"Checking validity: {os.path.basename(filepath)}")
        try:
            with open(filepath, "rb") as f: data = f.read(32) 
            result = tex_handler.check_tex_type(data)
            if result: self.add_info(f"  Validation: {result}"); messagebox.showinfo("TEX Validity", f"File: {os.path.basename(filepath)}\nType: {result}\n(Basic magic check)")
            else: self.add_info(f"  Validation: Unknown/invalid TEX."); messagebox.showwarning("TEX Validity", f"File: {os.path.basename(filepath)}\nInvalid/unknown MTF TEX.")
        except Exception as e: self.add_info(f"  Error checking: {e}"); messagebox.showerror("Validation Error", f"Could not check: {e}")


if __name__ == "__main__":
    # This check is illustrative. Ensure image_utils and TEXCONV_PATH are correctly set up in your environment.
    if not image_utils.check_texconv():
        messagebox.showwarning("Dependency Check", f"texconv.exe (expected at '{os.path.abspath(image_utils.TEXCONV_PATH)}') not found. DXT/BCn features will fail.")
    app_root = tk.Tk()
    app = TexToolApp(app_root)
    app_root.mainloop()