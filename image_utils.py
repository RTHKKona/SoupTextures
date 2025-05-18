# image_utils.py
import subprocess
import os
import sys # Added for PyInstaller compatibility
from PIL import Image, ImageFile, UnidentifiedImageError
import struct
from typing import Optional # Keep for type hints

ImageFile.LOAD_TRUNCATED_IMAGES = True # Keep, can be helpful

# --- Start of PyInstaller Path Helper ---
def _get_app_base_path() -> str:
    """
    Get the base path for the application.
    If bundled with PyInstaller, this is the _MEIPASS temporary directory.
    Otherwise, it's the current working directory (assuming the script is run from the project root
    and texconv.exe is expected there or added to PATH).
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running in a normal Python environment
        # Assume texconv.exe is in the current working dir or will be found via PATH
        # For consistency with PyInstaller's --add-binary placing it in the bundle's root,
        # os.path.abspath(".") is a good default for development if main script is in root.
        return os.path.abspath(".")

_APP_BASE_PATH = _get_app_base_path()
TEXCONV_PATH = os.path.join(_APP_BASE_PATH, "texconv.exe")
# --- End of PyInstaller Path Helper ---

def check_texconv() -> bool:
    """Checks if texconv.exe can be found at the determined path."""
    return os.path.exists(TEXCONV_PATH)

def _create_minimal_dds_header(width: int, height: int, data_len: int, fourcc_str: str) -> bytes:
    """Creates a DDS header for raw DXT/BC data."""
    header = bytearray(128)
    struct.pack_into("<I", header, 0, 0x20534444)  # "DDS " magic
    struct.pack_into("<I", header, 4, 124)         # dwSize
    # DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    struct.pack_into("<I", header, 8, flags)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, data_len) # dwPitchOrLinearSize (size of main image)
    struct.pack_into("<I", header, 28, 1)        # dwMipMapCount (only Mip0)
    # PixelFormat
    struct.pack_into("<I", header, 76, 32)       # pfSize
    struct.pack_into("<I", header, 80, 0x4)      # pfFlags = DDPF_FOURCC
    struct.pack_into("<4s", header, 84, fourcc_str.encode('ascii').ljust(4, b'\0')) # pfFourCC
    # Caps
    struct.pack_into("<I", header, 108, 0x1000)  # DDSCAPS_TEXTURE
    return bytes(header)

def decode_dxt_to_rgba(dxt_data: bytes, width: int, height: int, dxt_format_name: str) -> Optional[bytes]:
    """Decodes DXT/BC data to RGBA using texconv."""
    if not check_texconv():
        print(f"TEXCONV_DECODE_ERROR: texconv.exe not found at {TEXCONV_PATH}")
        return None
    if not dxt_data: return None

    fourcc_map = {
        "DXT1": "DXT1", "ATI1": "BC4U",
        "DXT5": "DXT5", "ATI2": "BC5U",
    }
    fourcc = fourcc_map.get(dxt_format_name.upper(), dxt_format_name.upper())

    full_dds_data = _create_minimal_dds_header(width, height, len(dxt_data), fourcc) + dxt_data
    
    # Use _APP_BASE_PATH for temporary files and texconv output directory
    temp_dds_path = os.path.join(_APP_BASE_PATH, "temp_decode_input.dds")
    # texconv will name the output file based on the input file name if -o specifies a directory
    expected_output_png = os.path.join(_APP_BASE_PATH, "temp_decode_input.png")

    try:
        if os.path.exists(expected_output_png): os.remove(expected_output_png)
        with open(temp_dds_path, "wb") as f: f.write(full_dds_data)

        cmd = [TEXCONV_PATH, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-o", _APP_BASE_PATH, "-nologo", "-y", temp_dds_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=_APP_BASE_PATH) # Added cwd for robustness
        
        if result.returncode != 0 or not os.path.exists(expected_output_png):
            print(f"TEXCONV_DECODE_ERROR: texconv failed for {dxt_format_name} (Ret: {result.returncode}).")
            # print(f"  Input: {temp_dds_path}, Output: {expected_output_png}")
            # print(f"  STDOUT: {result.stdout}\n  STDERR: {result.stderr}")
            return None

        with Image.open(expected_output_png) as img:
            return img.convert("RGBA").tobytes()
            
    except Exception as e:
        print(f"TEXCONV_DECODE_EXCEPTION: {e}")
        return None
    finally:
        if os.path.exists(temp_dds_path):
            try: os.remove(temp_dds_path)
            except OSError: pass # May fail if file is locked, though unlikely here
        if os.path.exists(expected_output_png):
            try: os.remove(expected_output_png)
            except OSError: pass

def encode_rgba_to_dxt(rgba_data: bytes, width: int, height: int, target_dxt_format_name: str) -> Optional[bytes]:
    """Encodes RGBA data to DXT/BC using texconv."""
    if not check_texconv():
        print(f"TEXCONV_ENCODE_ERROR: texconv.exe not found at {TEXCONV_PATH}")
        return None

    texconv_fmt_map = {
        "DXT1": "BC1_UNORM", "ATI1": "BC4_UNORM",
        "DXT5": "BC5_UNORM", "ATI2": "BC5_UNORM", # ATI2 is BC5
    }
    texconv_target_fmt = texconv_fmt_map.get(target_dxt_format_name.upper())
    if not texconv_target_fmt:
        print(f"TEXCONV_ENCODE_ERROR: Unsupported target DXT format for texconv: {target_dxt_format_name}")
        return None

    # Use _APP_BASE_PATH for temporary files and texconv output directory
    temp_png_path = os.path.join(_APP_BASE_PATH, "temp_encode_input.png")
    expected_output_dds = os.path.join(_APP_BASE_PATH, "temp_encode_input.dds")

    try:
        if os.path.exists(expected_output_dds): os.remove(expected_output_dds)
        img = Image.frombytes("RGBA", (width, height), rgba_data)
        img.save(temp_png_path, "PNG")

        cmd = [TEXCONV_PATH, "-ft", "dds", "-f", texconv_target_fmt, "-o", _APP_BASE_PATH, "-nologo", "-y", "-m", "1", temp_png_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=_APP_BASE_PATH) # Added cwd

        if result.returncode != 0 or not os.path.exists(expected_output_dds):
            print(f"TEXCONV_ENCODE_ERROR: texconv failed for {texconv_target_fmt} (Ret: {result.returncode}).")
            # print(f"  Input: {temp_png_path}, Output: {expected_output_dds}")
            # print(f"  STDOUT: {result.stdout}\n  STDERR: {result.stderr}")
            return None

        with open(expected_output_dds, "rb") as f: dds_data = f.read()
        
        if len(dds_data) > 128: return dds_data[128:] # Return raw DXT data (skip DDS header)
        print("TEXCONV_ENCODE_ERROR: DDS output from texconv too small.")
        return None
            
    except Exception as e:
        print(f"TEXCONV_ENCODE_EXCEPTION: {e}")
        return None
    finally:
        if os.path.exists(temp_png_path):
            try: os.remove(temp_png_path)
            except OSError: pass
        if os.path.exists(expected_output_dds):
            try: os.remove(expected_output_dds)
            except OSError: pass

def load_image_from_path(path: str) -> Optional[Image.Image]:
    """Loads PNG or decodes DDS (via texconv) to an RGBA Pillow Image."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".png":
            return Image.open(path).convert("RGBA")
        elif ext == ".dds":
            if not check_texconv():
                print(f"TEXCONV_LOAD_DDS_ERROR: texconv.exe not found at {TEXCONV_PATH}")
                return None
            
            # Output PNG will be created in _APP_BASE_PATH
            # texconv creates output named <input_filename_without_ext>.png
            base_name_no_ext = os.path.splitext(os.path.basename(path))[0]
            expected_output_png = os.path.join(_APP_BASE_PATH, f"{base_name_no_ext}.png")
            
            if os.path.exists(expected_output_png): os.remove(expected_output_png)

            cmd = [TEXCONV_PATH, "-ft", "png", "-f", "R8G8B8A8_UNORM", "-o", _APP_BASE_PATH, "-nologo", "-y", path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=_APP_BASE_PATH) # Added cwd
            
            if result.returncode != 0 or not os.path.exists(expected_output_png):
                print(f"TEXCONV_LOAD_DDS_ERROR: Failed to convert DDS '{os.path.basename(path)}' (Ret: {result.returncode}).")
                # print(f"  Input: {path}, Output: {expected_output_png}")
                # print(f"  STDOUT: {result.stdout}\n  STDERR: {result.stderr}")
                return None
            return Image.open(expected_output_png).convert("RGBA")
        else:
            print(f"IMAGE_UTILS_ERROR: Unsupported import format: {ext}")
            return None
    except UnidentifiedImageError:
        print(f"IMAGE_UTILS_ERROR: Cannot identify image file (corrupt or unsupported): {path}")
        return None
    except Exception as e:
        print(f"IMAGE_UTILS_EXCEPTION: Loading {path}: {e}")
        return None
    finally:
        # Cleanup for DDS conversion if expected_output_png was defined and exists
        if ext == ".dds" and 'expected_output_png' in locals() and os.path.exists(expected_output_png):
            try: os.remove(expected_output_png)
            except OSError: pass

def image_to_bgra(img_rgba: Image.Image) -> bytes:
    img = img_rgba.convert("RGBA") # Ensure RGBA
    r, g, b, a = img.split()
    return Image.merge("RGBA", (b, g, r, a)).tobytes()

def bgra_to_image(bgra_data: bytes, width: int, height: int) -> Optional[Image.Image]:
    if not bgra_data or width <= 0 or height <= 0 or len(bgra_data) != width * height * 4:
        print(f"BGRA_TO_IMAGE_ERROR: Invalid parameters for BGRA conversion. Len={len(bgra_data)}, W={width}, H={height}")
        return None
    try:
        rgba_data = bytearray(len(bgra_data))
        for i in range(0, len(bgra_data), 4):
            b, g, r, a = bgra_data[i:i+4]
            rgba_data[i:i+4] = r, g, b, a
        return Image.frombytes("RGBA", (width, height), bytes(rgba_data))
    except Exception as e:
        print(f"BGRA_TO_IMAGE_EXCEPTION: {e}")
        return None