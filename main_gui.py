# Handburger
# SoupTextures - MHGU TEX Tool to end all Kuriimu tools

# main_gui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, UnidentifiedImageError
import os
import platform
from typing import Optional

import constants as C
import tex_handler
import image_utils

import sys
import argparse # For more robust CLI argument parsing
# winreg will be imported conditionally later for Windows-specific functions

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
        if "clam" in self.style.theme_names():
            self.style.theme_use('clam')
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

    def set_status(self, message: str, color: str = C.STATUS_INFO_FG):
        # Update the status bar message and color.
        self.status_var.set(message)
        self.status_label.config(foreground=color)

    def add_info(self, message: str):
        # Add a message to the info text box.
        self.info_text.config(state=tk.NORMAL)
        self.info_text.insert(tk.END, message + "\n")
        self.info_text.see(tk.END)
        self.info_text.config(state=tk.DISABLED)

    def update_ui_for_loaded_state(self):
        # Enable/disable UI elements based on whether an image is loaded.
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
        # Clears the canvas and displays the current image, handling zooming.
        self.image_canvas.delete("all")
        actual_image_to_display = self.current_display_image 

        if actual_image_to_display:
            try:
                self.root.update_idletasks() # Ensure canvas dimensions are up-to-date
                canvas_width = self.image_canvas.winfo_width()
                canvas_height = self.image_canvas.winfo_height()
                if canvas_width <= 1 or canvas_height <= 1:
                    canvas_width, canvas_height = 400,300 # Default fallback dimensions
                
                img_for_tk = actual_image_to_display.copy()
                zoomed_w = int(img_for_tk.width * self.zoom_level)
                zoomed_h = int(img_for_tk.height * self.zoom_level)

                if zoomed_w > 0 and zoomed_h > 0:
                    if (zoomed_w, zoomed_h) != img_for_tk.size:
                        # Use NEAREST for zooming in (pixel art style), LANCZOS for zooming out (smoothing)
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

    def _reset_alpha_toggle_state(self, called_by_load: bool = False):
        # Resets the state of the alpha toggle button and its internal flag.
        if called_by_load:
            self.image_state_before_set_opaque = None
        self.is_currently_opaque_by_toggle = False
        if hasattr(self, 'toggle_alpha_button'):
            self.toggle_alpha_button.config(text="Set Alpha Opaque")

    def _update_display_and_sources(self, new_pil_image: Optional[Image.Image], called_by_alpha_toggle: bool = False):
        # Updates the internal image references and refreshes the display.
        if not called_by_alpha_toggle:
            self._reset_alpha_toggle_state(called_by_load=True)
            
        self.current_display_image = new_pil_image
        # If a TEX file was loaded, update its internal image.
        if self.current_tex_file and self.current_tex_file.image is not None:
            self.current_tex_file.image = new_pil_image
        # If an external image was loaded, update its reference for export.
        elif self.loaded_image_for_export:
            self.loaded_image_for_export = new_pil_image
        
        self.display_image(new_pil_image)

    def zoom_in(self):
        # Increases the zoom level and updates the displayed image.
        if not self.current_display_image:
            return
        self.zoom_level = round(min(self.zoom_level + self.zoom_step, 5.0), 2) # Max zoom 500%
        self._update_display_and_sources(self.current_display_image.copy(), called_by_alpha_toggle=True)
        self.set_status(f"Zoom: {int(self.zoom_level*100)}%", C.STATUS_INFO_FG)

    def zoom_out(self):
        # Decreases the zoom level and updates the displayed image.
        if not self.current_display_image:
            return
        self.zoom_level = round(max(self.zoom_level - self.zoom_step, 0.1), 2) # Min zoom 10%
        self._update_display_and_sources(self.current_display_image.copy(), called_by_alpha_toggle=True)
        self.set_status(f"Zoom: {int(self.zoom_level*100)}%", C.STATUS_INFO_FG)

    def _init_ui(self):
        # Initializes the main user interface layout and widgets.
        main_frame = ttk.Frame(self.root, padding="3")
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        main_frame.columnconfigure(0, weight=1, minsize=180)
        main_frame.columnconfigure(1, weight=5)
        main_frame.rowconfigure(0, weight=1)
        
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        
        display_frame = ttk.Frame(main_frame)
        display_frame.grid(row=0, column=1, sticky="nsew")

        # File Import/Export Buttons
        ttk.Button(controls_frame, text="Import TEX", command=self.import_tex).pack(fill=tk.X, pady=2, padx=1)
        ttk.Button(controls_frame, text="Import PNG/DDS/JPG", command=self.import_image).pack(fill=tk.X, pady=2, padx=1) # Renamed
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
        
        # Image Modification Buttons
        self.toggle_alpha_button = ttk.Button(controls_frame, text="Set Alpha Opaque", command=self.toggle_set_alpha_opaque, state=tk.DISABLED)
        self.toggle_alpha_button.pack(fill=tk.X, pady=2, padx=1)
        
        self.ensure_rgba_button = ttk.Button(controls_frame, text="Ensure RGBA Format", command=self.ensure_rgba_format, state=tk.DISABLED)
        self.ensure_rgba_button.pack(fill=tk.X, pady=2, padx=1)
        
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)

        # Zoom Controls
        zoom_frame = ttk.Frame(controls_frame)
        zoom_frame.pack(fill=tk.X, pady=2, padx=1)
        self.zoom_in_button = ttk.Button(zoom_frame, text="Zoom In (+)", command=self.zoom_in, state=tk.DISABLED)
        self.zoom_in_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,1))
        self.zoom_out_button = ttk.Button(zoom_frame, text="Zoom Out (-)", command=self.zoom_out, state=tk.DISABLED)
        self.zoom_out_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(1,0))
        
        ttk.Separator(controls_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3, padx=1)

        # Image Display Canvas
        display_frame.rowconfigure(0, weight=1)
        display_frame.rowconfigure(1, weight=0)
        display_frame.columnconfigure(0, weight=1)
        
        self.image_canvas = tk.Canvas(display_frame, bg=C.WIDGET_BG, highlightthickness=0)
        self.image_canvas.grid(row=0, column=0, sticky="nsew", pady=(0,3))
        
        # Info Text Box (with scrollbar)
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
        
        # Status Bar
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


    def import_tex(self, filepath: Optional[str] = None):
        # Handles importing a .tex file, parsing its header and image data.
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
            with open(filepath, "rb") as f:
                data = f.read()
            loaded_tex = tex_handler.load_tex_from_data(data)
            
            if loaded_tex:
                self.current_tex_file = loaded_tex
                self.current_tex_file.filepath = filepath
                self.loaded_image_for_export = None # Clear any previously loaded non-TEX image
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
                if self.current_display_image:
                    self.add_info("  Image preview generated.")
                else:
                    self.add_info("  Image data could not be decoded/previewed.")
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

    def import_image(self): # Renamed function
        # Handles importing PNG, DDS, or JPG/JPEG image files for editing/export.
        filepath = filedialog.askopenfilename(
            title="Import Image File",
            filetypes=(
                ("Image files", "*.png *.dds *.jpg *.jpeg"),
                ("PNG files", "*.png"),
                ("DDS files", "*.dds"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            )
        )
        if not filepath:
            return
        self.set_status(f"Loading image: {os.path.basename(filepath)}...", C.STATUS_INFO_FG)
        self.add_info(f"Attempting to load image: {filepath}")
        try:
            pil_image = image_utils.load_image_from_path(filepath)
            if pil_image:
                self.loaded_image_for_export = pil_image.convert("RGBA") # Ensure RGBA for consistency
                self.loaded_image_filepath = filepath
                
                if self.current_tex_file:
                    self.add_info("  Imported image. Previous TEX header info kept (if any). TEX image data replaced.")
                else:
                     self.add_info("  Imported image. New MHGU header will be used for TEX export.")
                
                self._update_display_and_sources(self.loaded_image_for_export.copy(), called_by_alpha_toggle=False)
                self.set_status(f"Image {os.path.basename(filepath)} loaded.", C.STATUS_SUCCESS_FG)
                self.add_info(f"  Loaded image: {pil_image.width}x{pil_image.height}")
            else:
                self.set_status(f"Failed to load/convert: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
                self.add_info("  Image load/conversion failed.")
        except UnidentifiedImageError:
            self.set_status(f"Cannot identify image file: {os.path.basename(filepath)}", C.STATUS_ERROR_FG)
            self.add_info("  Error: Cannot identify image file. It might be corrupted or an unsupported format.")
        except Exception as e:
            self.set_status(f"Error loading image: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  Exception: {e}")

    def toggle_set_alpha_opaque(self):
        # Toggles the alpha channel of the current image to opaque or restores its previous state.
        if not self.current_display_image:
            self.set_status("No image loaded to modify.", C.STATUS_INFO_FG)
            return

        new_image_state: Optional[Image.Image] = None
        action_message = ""

        if not self.is_currently_opaque_by_toggle:
            # Store current image state before making it opaque.
            if self.image_state_before_set_opaque is None:
                 self.image_state_before_set_opaque = self.current_display_image.copy()

            modified_image = self.current_display_image.copy()
            if modified_image.mode != "RGBA":
                modified_image = modified_image.convert("RGBA")
            
            # Create a fully opaque alpha channel and apply it.
            opaque_alpha = Image.new('L', modified_image.size, 255)
            modified_image.putalpha(opaque_alpha)
            
            new_image_state = modified_image
            self.is_currently_opaque_by_toggle = True
            self.toggle_alpha_button.config(text="Undo Set Alpha Opaque")
            action_message = "Image alpha channel set to opaque."
        else:
            # Restore image to the state it was in before setting alpha opaque.
            if self.image_state_before_set_opaque:
                new_image_state = self.image_state_before_set_opaque.copy()
                action_message = "Restored image to state before 'Set Alpha Opaque'."
            else:
                # Fallback if no prior state was saved (shouldn't happen with proper flow).
                new_image_state = self.current_display_image.copy()
                if new_image_state.mode != "RGBA":
                    new_image_state = new_image_state.convert("RGBA")
                action_message = "No prior state to restore; ensured RGBA."
            
            self.is_currently_opaque_by_toggle = False
            self.toggle_alpha_button.config(text="Set Alpha Opaque")

        if new_image_state:
            self._update_display_and_sources(new_image_state, called_by_alpha_toggle=True)
            self.set_status(action_message, C.STATUS_SUCCESS_FG)

    def ensure_rgba_format(self):
        # Converts the current image to RGBA format if it isn't already.
        if not self.current_display_image:
            self.set_status("No image loaded.", C.STATUS_INFO_FG)
            return
        
        if self.current_display_image.mode != "RGBA":
            modified_image = self.current_display_image.convert("RGBA")
            self._update_display_and_sources(modified_image.copy(), called_by_alpha_toggle=False)
            self.set_status("Image format ensured to be RGBA.", C.STATUS_SUCCESS_FG)
            self.add_info("Image converted to RGBA (alpha preserved or added).")
        else:
            self.set_status("Image is already RGBA.", C.STATUS_INFO_FG)
            self.add_info("Image is already RGBA format.")
            
    def export_to_png(self):
        # Exports the currently displayed image to a PNG file.
        if not self.current_display_image:
            messagebox.showwarning("Export PNG", "No image loaded.")
            return

        # Determine a default filename.
        default_name = "exported_image.png"
        if self.current_tex_file and self.current_tex_file.filepath:
            default_name = f"{os.path.splitext(os.path.basename(self.current_tex_file.filepath))[0]}.png"
        elif self.loaded_image_filepath:
            default_name = f"{os.path.splitext(os.path.basename(self.loaded_image_filepath))[0]}_edited.png"
        
        save_filepath = filedialog.asksaveasfilename(title="Export Image as PNG", defaultextension=".png", initialfile=default_name, filetypes=(("PNG files", "*.png"),))
        if not save_filepath:
            return
        try:
            self.current_display_image.save(save_filepath, "PNG")
            self.set_status(f"Image exported to PNG: {os.path.basename(save_filepath)}", C.STATUS_SUCCESS_FG)
            self.add_info(f"  Saved PNG: {save_filepath}")
        except Exception as e:
            self.set_status(f"Error exporting PNG: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  PNG Export Exception: {e}")

    def _get_default_tex_header_info(self) -> tex_handler.TexFile:
        # Creates a TexFile object with default MHGU header information for new exports.
        # This ensures consistency with game expectations for newly created TEX files.
        default_tex_info = tex_handler.TexFile()
        default_tex_info.version = C.MHGU_VERSION
        default_tex_info.magic = C.MAGIC_TEX_LITTLE # Match desired header sequence (TEX\0)
        default_tex_info.is_big_endian = False # Required for Little Endian magic
        default_tex_info.k_unk1 = 8 # Specific value from desired header sequence
        default_tex_info.k_unused1 = 0
        default_tex_info.alpha_flags = 2 # Specific value from desired header sequence
        default_tex_info.k_unk2 = 0
        default_tex_info.k_unk3 = 0
        return default_tex_info

    def _pad_image_for_export(self, image: Image.Image, format_id: int) -> Optional[Image.Image]:
        # Pads the image dimensions to meet Aclios swizzler requirements for the target format.
        # Returns the padded image or None if parameters are invalid.
        try:
            aclios_block_wh, aclios_bytes_per_block = tex_handler.get_aclios_format_params(format_id)
            aclios_swizzle_mode = 4 # Confirmed as the correct mode for MHGU TEX

            tile_width_pixels = (64 // aclios_bytes_per_block) * aclios_block_wh[0]
            tile_height_pixels = 8 * aclios_block_wh[1] * (2 ** aclios_swizzle_mode)

            original_width = image.width
            original_height = image.height

            # Calculate the required padded dimensions using ceiling division.
            padded_width = ((original_width + tile_width_pixels - 1) // tile_width_pixels) * tile_width_pixels
            padded_height = ((original_height + tile_height_pixels - 1) // tile_height_pixels) * tile_height_pixels

            if original_width != padded_width or original_height != padded_height:
                self.add_info(f"  Padding image from {original_width}x{original_height} to {padded_width}x{padded_height} for export.")
                # Create a new image with padded dimensions, filled with transparent black.
                padded_image = Image.new("RGBA", (padded_width, padded_height), (0, 0, 0, 0))
                # Paste the original image onto the top-left corner of the padded image.
                padded_image.paste(image, (0, 0))
                return padded_image
            return image # No padding needed
            
        except ValueError as ve:
            self.set_status(f"Error: Format {format_id} not supported for Aclios padding: {ve}", C.STATUS_ERROR_FG)
            self.add_info("  Export aborted due to unsupported Aclios format parameters.")
            return None
        except Exception as e:
            self.set_status(f"Error during padding calculation: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  Padding Exception: {e}")
            return None

    def export_to_tex(self):
        # Exports the current image data as a MHGU .tex file.
        current_image_for_export = self.current_display_image

        if not current_image_for_export:
            messagebox.showerror("Export Error", "No image data to export.")
            return

        base_tex_for_header_info = self.current_tex_file if self.current_tex_file else self._get_default_tex_header_info()
        
        # Ensure the version is explicitly MHGU_VERSION for consistency with Kuriimu2.
        base_tex_for_header_info.version = C.MHGU_VERSION 

        export_format_str = self.export_format_var.get()
        new_tex_format_id = tex_handler.get_mtf_format_id_from_string_kukkii_switch(export_format_str)
        
        if new_tex_format_id is None:
            self.set_status(f"Error: Unsupported export format '{export_format_str}' for MHGU.", C.STATUS_ERROR_FG)
            self.add_info(f"  Export aborted due to unsupported format: {export_format_str}")
            return

        image_to_save = self._pad_image_for_export(current_image_for_export, new_tex_format_id)
        if image_to_save is None: # Padding failed
            return

        # Update header info with potentially padded dimensions.
        base_tex_for_header_info.width = image_to_save.width
        base_tex_for_header_info.height = image_to_save.height

        # Determine default save filename.
        default_name = "exported_mhgu.tex" # Changed default to something more generic
        if self.loaded_image_filepath:
            default_name = f"{os.path.splitext(os.path.basename(self.loaded_image_filepath))[0]}.tex"
        elif base_tex_for_header_info.filepath:
             default_name = f"{os.path.splitext(os.path.basename(base_tex_for_header_info.filepath))[0]}_exp.tex"
        
        save_filepath = filedialog.asksaveasfilename(title="Save MHGU TEX File As", defaultextension=".tex", initialfile=default_name, filetypes=(("TEX files", "*.tex"),))
        if not save_filepath:
            return # User cancelled save dialog
        
        self.set_status(f"Exporting to {export_format_str}...", C.STATUS_INFO_FG)
        self.add_info(f"  Target format: {export_format_str}")
        
        try:
            # Pass the (potentially padded) image to the tex_handler.
            tex_byte_data = tex_handler.save_tex_to_data(base_tex_for_header_info, image_to_save, export_format_str)
            
            if tex_byte_data:
                with open(save_filepath, "wb") as f:
                    f.write(tex_byte_data)
                self.set_status(f"Exported to {os.path.basename(save_filepath)}.", C.STATUS_SUCCESS_FG)
                self.add_info(f"  Saved {len(tex_byte_data)} bytes.")
            else:
                # tex_handler.save_tex_to_data would have printed its own errors.
                self.set_status("Export failed (tex_handler returned None).", C.STATUS_ERROR_FG)
                self.add_info("  Export failed (tex_handler returned None). Check console for details.")
        except Exception as e:
            self.set_status(f"Error during export: {e}", C.STATUS_ERROR_FG)
            self.add_info(f"  Export Exception: {e}")

    def check_tex_validity(self):
        # Placeholder method for checking TEX file validity (requires tex_handler.check_tex_type)
        filepath = filedialog.askopenfilename(title="Select TEX File to Check", filetypes=(("TEX files", "*.tex"),))
        if not filepath:
            return
        self.add_info(f"Checking validity: {os.path.basename(filepath)}")
        try:
            with open(filepath, "rb") as f:
                data = f.read(32) # Read enough for header check
            
            # Placeholder implementation:
            if data[:4] == C.MAGIC_TEX_LITTLE.to_bytes(4, 'little') or \
               data[:4] == C.MAGIC_TEX_BIG.to_bytes(4, 'big'):
                result = "Valid TEX Magic Found"
            else:
                result = "Unknown/invalid TEX."

            if result == "Valid TEX Magic Found":
                self.add_info(f"  Validation: {result}")
                messagebox.showinfo("TEX Validity", f"File: {os.path.basename(filepath)}\nType: {result}\n(Basic magic check)")
            else:
                self.add_info(f"  Validation: {result}")
                messagebox.showwarning("TEX Validity", f"File: {os.path.basename(filepath)}\n{result}")
        except Exception as e:
            self.add_info(f"  Error checking: {e}")
            messagebox.showerror("Validation Error", f"Could not check: {e}")

# === HEADLESS CONVERSION FUNCTION ===
def headless_convert_tex_to_png(input_tex_path: str, output_png_path: Optional[str] = None):
    # Converts a .tex file to a .png file in headless mode (CLI).
    if not os.path.exists(input_tex_path):
        print(f"ERROR: Input TEX file not found: {input_tex_path}")
        return 1

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
        # import traceback # For detailed debugging: traceback.print_exc()
        return 1

# === REGISTRY AND CLI HANDLING (Windows-specific) ===
PROG_ID = "SoupTextures.MHGUTexFile.1"
FILE_EXT = ".tex"
APP_DESCRIPTION = "MHGU Texture File (SoupTextures)"

if platform.system() == "Windows":
    import winreg

    CONTEXT_MENU_COMMAND_NAME = "SoupTexConvertToPNG"
    CONTEXT_MENU_DISPLAY_TEXT = "Convert to .PNG (SoupTextures)"

    def _get_open_with_command() -> str:
        # Determines the correct command string to open the app for file association.
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as a PyInstaller bundled executable.
            app_path = sys.executable
            return f'"{app_path}" "%1"'
        else:
            # Running as a Python script.
            script_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            # Prefer pythonw.exe to prevent console window from appearing when opening files via GUI.
            python_exe_to_use = pythonw_exe if os.path.exists(pythonw_exe) else python_exe
            return f'"{python_exe_to_use}" "{script_path}" "%1"'

    def setup_windows_file_association():
        # Sets up Windows file association for .tex files to open with this application.
        try:
            command = _get_open_with_command()
            # Register .tex extension with our ProgID.
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, FILE_EXT) as key_ext:
                winreg.SetValueEx(key_ext, None, 0, winreg.REG_SZ, PROG_ID)
            
            # Create/update ProgID for our application.
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, PROG_ID) as key_prog_id:
                winreg.SetValueEx(key_prog_id, None, 0, winreg.REG_SZ, APP_DESCRIPTION)
                
                # Set default icon for the file type.
                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    icon_path = f'"{sys.executable}",0'
                else:
                    python_exe_for_icon = sys.executable
                    pythonw_exe_for_icon = os.path.join(os.path.dirname(python_exe_for_icon), "pythonw.exe")
                    icon_path = f'"{pythonw_exe_for_icon if os.path.exists(pythonw_exe_for_icon) else python_exe_for_icon}",0'
                with winreg.CreateKey(key_prog_id, "DefaultIcon") as key_icon:
                    winreg.SetValueEx(key_icon, None, 0, winreg.REG_SZ, icon_path)
                
                # Set the command to execute when opening the file.
                with winreg.CreateKey(key_prog_id, r"shell\open\command") as key_shell_open_cmd:
                    winreg.SetValueEx(key_shell_open_cmd, None, 0, winreg.REG_SZ, command)
            
            messagebox.showinfo("File Association Setup", 
                                f"Successfully registered {FILE_EXT} files to open with this application.\n"
                                "Changes may require restarting Windows Explorer or a system reboot to take full effect.")
            print(f"Successfully set up file association for {FILE_EXT}.")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to set up file associations.")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Registration Error", f"An error occurred: {e}")
            print(f"Error setting up file association: {e}")

    def remove_windows_file_association():
        # Removes Windows file association for this application.
        try:
            # Attempt to read current handler for .tex to see if it's ours.
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, FILE_EXT, 0, winreg.KEY_READ) as key_ext_read:
                    current_prog_id, _ = winreg.QueryValueEx(key_ext_read, None)
                if current_prog_id == PROG_ID:
                    print(f"Note: {PROG_ID} was the default handler for {FILE_EXT}.")
                    # More advanced removal might unset the default for FILE_EXT,
                    # but for simplicity, we only remove our specific ProgID.
            except FileNotFoundError:
                pass # .tex key doesn't exist or has no default.
            except Exception as e_read:
                print(f"Could not read default for {FILE_EXT}: {e_read}")

            # Delete ProgID and its subkeys from HKEY_CLASSES_ROOT.
            sub_keys_to_delete = [r"shell\open\command", r"shell\open", r"shell", "DefaultIcon"]
            for sub_key in sub_keys_to_delete:
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, rf"{PROG_ID}\{sub_key}")
                except FileNotFoundError:
                    pass # Key already gone or never existed.
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, PROG_ID)
            except FileNotFoundError:
                pass # ProgID key already gone.

            messagebox.showinfo("File Association Removal",
                                f"Attempted to unregister {PROG_ID}.\n"
                                "Changes may require restarting Windows Explorer or a system reboot.")
            print(f"Attempted to remove file association for {PROG_ID}.")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to remove file associations.")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Unregistration Error", f"An error occurred: {e}")
            print(f"Error removing file association: {e}")

    def setup_context_menu_item():
        # Adds a "Convert to .PNG" item to the .tex file context menu.
        if not (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')):
            messagebox.showwarning("Context Menu Setup Warning",
                                   "Context menu registration is intended to be run by the compiled .exe application "
                                   "to ensure correct paths.\nRunning from a Python script will register "
                                   "the script itself, which is likely not the desired deployed behavior.")

        try:
            # Check if the base ProgID is registered first.
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

            # Create the shell verb (the menu item itself).
            with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, base_key_path) as key_cmd_verb:
                winreg.SetValueEx(key_cmd_verb, None, 0, winreg.REG_SZ, CONTEXT_MENU_DISPLAY_TEXT)
                # Set an icon for the context menu item.
                winreg.SetValueEx(key_cmd_verb, "Icon", 0, winreg.REG_SZ, f'"{app_executable_path}",0')

            # Set the command to execute when the menu item is clicked.
            with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, rf"{base_key_path}\command") as key_cmd_action:
                winreg.SetValueEx(key_cmd_action, None, 0, winreg.REG_SZ, command_str)

            messagebox.showinfo("Context Menu Setup",
                                f"Successfully added '{CONTEXT_MENU_DISPLAY_TEXT}' to .tex file context menu "
                                f"(associated with ProgID '{PROG_ID}').\n"
                                "Changes may require restarting Windows Explorer.")
            print(f"Successfully set up context menu item: '{CONTEXT_MENU_DISPLAY_TEXT}'")
            print(f"  Command: {command_str}")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to modify the registry for context menus.")
            print("Permission denied. Please run as an administrator.")
        except Exception as e:
            messagebox.showerror("Context Menu Registration Error", f"An error occurred: {e}")
            print(f"Error setting up context menu item: {e}")

    def remove_context_menu_item():
        # Removes the "Convert to .PNG" item from the .tex file context menu.
        try:
            command_key_path = rf"{PROG_ID}\shell\{CONTEXT_MENU_COMMAND_NAME}\command"
            verb_key_path = rf"{PROG_ID}\shell\{CONTEXT_MENU_COMMAND_NAME}"

            # Attempt to delete the command and verb keys.
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, command_key_path)
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, verb_key_path)
            except FileNotFoundError:
                pass

            messagebox.showinfo("Context Menu Removal",
                                f"Attempted to remove '{CONTEXT_MENU_DISPLAY_TEXT}' from .tex file context menu.\n"
                                "Changes may require restarting Windows Explorer.")
            print(f"Attempted to remove context menu item: '{CONTEXT_MENU_DISPLAY_TEXT}'")
        except PermissionError:
            messagebox.showerror("Permission Error", "Administrator privileges are required to modify the registry.")
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
            temp_root.withdraw() # Hide the main window
            if args.register_assoc:
                setup_windows_file_association()
            if args.unregister_assoc:
                remove_windows_file_association()
            if args.register_context_menu:
                setup_context_menu_item()
            if args.unregister_context_menu:
                remove_context_menu_item()
            temp_root.destroy()
            cli_action_taken = True
            sys.exit(0)

    if args.convert_to_png:
        if not image_utils.check_texconv():
             print(f"WARNING: texconv.exe (expected at '{os.path.abspath(image_utils.TEXCONV_PATH)}') "
                   "not found. DXT/BCn features may fail during headless conversion.")
        exit_code = headless_convert_tex_to_png(args.convert_to_png, args.output_png)
        cli_action_taken = True
        sys.exit(exit_code)

    # If no CLI action was taken, proceed to GUI launch.
    if not cli_action_taken:
        # Check texconv and warn user if not found at GUI startup.
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
            if gui_file_to_open.lower().endswith(C.FILE_EXT): # Use constant for extension
                app_root.after(100, lambda fp=gui_file_to_open: app.import_tex(filepath=fp))
            else:
                app.set_status(f"Cannot open: {os.path.basename(gui_file_to_open)} (not a {C.FILE_EXT} file)", C.STATUS_ERROR_FG)
                app.add_info(f"Attempted to open non-{C.FILE_EXT} file via command line: {gui_file_to_open}")
        
        app_root.mainloop()