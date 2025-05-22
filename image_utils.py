# image_utils.py
import subprocess
import os
import sys
import struct
import tempfile # For safer temporary file handling
from typing import Optional

from PIL import Image, ImageFile, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = True # Allow Pillow to load truncated images, can be helpful for some broken files.

def _get_app_base_path() -> str:
    # Get the base path for the application.
    # If bundled with PyInstaller, this is the _MEIPASS temporary directory.
    # Otherwise, it's the current working directory.
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle.
        return sys._MEIPASS
    else:
        # Running in a normal Python environment.
        # Assume texconv.exe is in the current working dir or will be found via PATH.
        return os.path.abspath(".")

_APP_BASE_PATH = _get_app_base_path()
TEXCONV_PATH = os.path.join(_APP_BASE_PATH, "texconv.exe")

def check_texconv() -> bool:
    # Checks if texconv.exe can be found at the determined path.
    return os.path.exists(TEXCONV_PATH)

def _create_minimal_dds_header(width: int, height: int, data_len: int, fourcc_str: str) -> bytes:
    # Creates a minimal DDS header for raw DXT/BC data, as required by texconv.
    header = bytearray(128)
    struct.pack_into("<I", header, 0, 0x20534444)  # "DDS " magic
    struct.pack_into("<I", header, 4, 124)         # dwSize of header
    # DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    struct.pack_into("<I", header, 8, flags)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, data_len) # dwPitchOrLinearSize (size of main image data)
    struct.pack_into("<I", header, 28, 1)        # dwMipMapCount (only Mip0)
    # PixelFormat sub-structure
    struct.pack_into("<I", header, 76, 32)       # pfSize
    struct.pack_into("<I", header, 80, 0x4)      # pfFlags = DDPF_FOURCC (means FourCC is valid)
    struct.pack_into("<4s", header, 84, fourcc_str.encode('ascii').ljust(4, b'\0')) # pfFourCC (e.g., "DXT1", "BC4U")
    # Caps sub-structure
    struct.pack_into("<I", header, 108, 0x1000)  # DDSCAPS_TEXTURE (indicates a texture, not a volume/cubemap)
    return bytes(header)

def decode_dxt_to_rgba(dxt_data: bytes, width: int, height: int, dxt_format_name: str) -> Optional[bytes]:
    # Decodes DXT/BC data to RGBA bytes using texconv.
    if not check_texconv():
        print(f"TEXCONV_DECODE_ERROR: texconv.exe not found at {TEXCONV_PATH}")
        return None
    if not dxt_data:
        return None

    # Map common DXT/BC format names to texconv's expected FourCCs.
    fourcc_map = {
        "DXT1": "DXT1", "ATI1": "BC4U",
        "DXT5": "DXT5", "ATI2": "BC5U", # DXT5 is indeed DXT5 for decompression, not BC3 here
    }
    fourcc = fourcc_map.get(dxt_format_name.upper(), dxt_format_name.upper())

    full_dds_data = _create_minimal_dds_header(width, height, len(dxt_data), fourcc) + dxt_data
    
    # Use tempfile to create temporary input DDS and output PNG files.
    # This ensures unique filenames and handles cleanup automatically.
    with tempfile.NamedTemporaryFile(suffix=".dds", delete=False, dir=_APP_BASE_PATH) as temp_dds_file:
        temp_dds_path = temp_dds_file.name
        temp_dds_file.write(full_dds_data)
    
    # texconv will name the output file based on the input file name if -o specifies a directory.
    # So, we expect the output PNG to have the same base name as the temp_dds_file.
    expected_output_png_path = os.path.splitext(temp_dds_path)[0] + ".png"

    try:
        cmd = [
            TEXCONV_PATH,
            "-ft", "png",                 # Output file type: PNG
            "-f", "R8G8B8A8_UNORM",       # Output format: RGBA 8-bit unorm
            "-o", _APP_BASE_PATH,         # Output directory
            "-nologo",                    # Suppress texconv logo
            "-y",                         # Overwrite existing files without prompt
            temp_dds_path                 # Input DDS file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=_APP_BASE_PATH)
        
        if result.returncode != 0 or not os.path.exists(expected_output_png_path):
            print(f"TEXCONV_DECODE_ERROR: texconv failed for {dxt_format_name} (Ret: {result.returncode}).")
            print(f"  STDOUT: {result.stdout}\n  STDERR: {result.stderr}")
            return None

        with Image.open(expected_output_png_path) as img:
            return img.convert("RGBA").tobytes()
            
    except Exception as e:
        print(f"TEXCONV_DECODE_EXCEPTION: {e}")
        return None
    finally:
        # Ensure temporary files are cleaned up.
        if os.path.exists(temp_dds_path):
            os.remove(temp_dds_path)
        if os.path.exists(expected_output_png_path):
            os.remove(expected_output_png_path)

def encode_rgba_to_dxt(rgba_data: bytes, width: int, height: int, target_dxt_format_name: str) -> Optional[bytes]:
    # Encodes RGBA data to DXT/BC compressed format using texconv.
    if not check_texconv():
        print(f"TEXCONV_ENCODE_ERROR: texconv.exe not found at {TEXCONV_PATH}")
        return None

    # Map target DXT/BC format names to texconv's internal formats for encoding.
    texconv_fmt_map = {
        "DXT1": "BC1_UNORM",
        "ATI1": "BC4_UNORM",
        "DXT5": "BC3_UNORM", # Corrected mapping: DXT5 is BC3
        "ATI2": "BC5_UNORM", # ATI2 is BC5
    }
    texconv_target_fmt = texconv_fmt_map.get(target_dxt_format_name.upper())
    if not texconv_target_fmt:
        print(f"TEXCONV_ENCODE_ERROR: Unsupported target DXT format for texconv: {target_dxt_format_name}")
        return None

    # Create temporary input PNG file and expect DDS output.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=_APP_BASE_PATH) as temp_png_file:
        temp_png_path = temp_png_file.name
        img = Image.frombytes("RGBA", (width, height), rgba_data)
        img.save(temp_png_path, "PNG")
    
    expected_output_dds_path = os.path.splitext(temp_png_path)[0] + ".dds"

    try:
        cmd = [
            TEXCONV_PATH,
            "-ft", "dds",                 # Output file type: DDS
            "-f", texconv_target_fmt,     # Output format: target DXT/BC format
            "-o", _APP_BASE_PATH,         # Output directory
            "-nologo",                    # Suppress texconv logo
            "-y",                         # Overwrite existing files
            "-m", "1",                    # Generate only Mip0 (no mipmaps)
            temp_png_path                 # Input PNG file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=_APP_BASE_PATH)

        if result.returncode != 0 or not os.path.exists(expected_output_dds_path):
            print(f"TEXCONV_ENCODE_ERROR: texconv failed for {texconv_target_fmt} (Ret: {result.returncode}).")
            print(f"  STDOUT: {result.stdout}\n  STDERR: {result.stderr}")
            return None

        with open(expected_output_dds_path, "rb") as f:
            dds_data = f.read()
        
        # DDS files always have a 128-byte header; return only the raw DXT data.
        if len(dds_data) > 128:
            return dds_data[128:]
        print("TEXCONV_ENCODE_ERROR: DDS output from texconv too small (missing pixel data).")
        return None
            
    except Exception as e:
        print(f"TEXCONV_ENCODE_EXCEPTION: {e}")
        return None
    finally:
        # Ensure temporary files are cleaned up.
        if os.path.exists(temp_png_path):
            os.remove(temp_png_path)
        if os.path.exists(expected_output_dds_path):
            os.remove(expected_output_dds_path)

def load_image_from_path(path: str) -> Optional[Image.Image]:
    # Loads PNG, JPG/JPEG, or decodes DDS (via texconv) to an RGBA Pillow Image.
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".png" or ext in [".jpg", ".jpeg"]:
            return Image.open(path).convert("RGBA")
        elif ext == ".dds":
            if not check_texconv():
                print(f"TEXCONV_LOAD_DDS_ERROR: texconv.exe not found at {TEXCONV_PATH}")
                return None
            
            # Create temporary output PNG path for texconv.
            base_name_no_ext = os.path.splitext(os.path.basename(path))[0]
            # Use tempfile for robust unique naming and cleanup, but keep base name for clarity.
            with tempfile.NamedTemporaryFile(prefix=base_name_no_ext + "_", suffix=".png", delete=False, dir=_APP_BASE_PATH) as temp_png_output_file:
                expected_output_png_path = temp_png_output_file.name

            try:
                cmd = [
                    TEXCONV_PATH,
                    "-ft", "png",                 # Output file type: PNG
                    "-f", "R8G8B8A8_UNORM",       # Output format: RGBA 8-bit unorm
                    "-o", _APP_BASE_PATH,         # Output directory
                    "-nologo",                    # Suppress texconv logo
                    "-y",                         # Overwrite existing files
                    path                          # Input DDS file
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=_APP_BASE_PATH)
                
                if result.returncode != 0 or not os.path.exists(expected_output_png_path):
                    print(f"TEXCONV_LOAD_DDS_ERROR: Failed to convert DDS '{os.path.basename(path)}' (Ret: {result.returncode}).")
                    print(f"  STDOUT: {result.stdout}\n  STDERR: {result.stderr}")
                    return None
                return Image.open(expected_output_png_path).convert("RGBA")
            finally:
                # Ensure temporary PNG is cleaned up.
                if os.path.exists(expected_output_png_path):
                    os.remove(expected_output_png_path)
        else:
            print(f"IMAGE_UTILS_ERROR: Unsupported import format: {ext}")
            return None
    except UnidentifiedImageError:
        print(f"IMAGE_UTILS_ERROR: Cannot identify image file (corrupt or unsupported): {path}")
        return None
    except Exception as e:
        print(f"IMAGE_UTILS_EXCEPTION: Loading {path}: {e}")
        return None

def image_to_bgra(img_rgba: Image.Image) -> bytes:
    # Converts an RGBA Pillow Image to BGRA byte data.
    img = img_rgba.convert("RGBA") # Ensure RGBA mode.
    r, g, b, a = img.split()
    return Image.merge("RGBA", (b, g, r, a)).tobytes()

def bgra_to_image(bgra_data: bytes, width: int, height: int) -> Optional[Image.Image]:
    # Converts BGRA byte data to an RGBA Pillow Image.
    if not bgra_data or width <= 0 or height <= 0 or len(bgra_data) != width * height * 4:
        print(f"BGRA_TO_IMAGE_ERROR: Invalid parameters for BGRA conversion. Len={len(bgra_data)}, W={width}, H={height}")
        return None
    try:
        # Efficiently convert BGRA to RGBA by swapping R and B channels.
        rgba_data = bytearray(len(bgra_data))
        for i in range(0, len(bgra_data), 4):
            b, g, r, a = bgra_data[i:i+4]
            rgba_data[i:i+4] = r, g, b, a # Swap B and R
        return Image.frombytes("RGBA", (width, height), bytes(rgba_data))
    except Exception as e:
        print(f"BGRA_TO_IMAGE_EXCEPTION: {e}")
        return None