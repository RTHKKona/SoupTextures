# Uses the Aclios swizzler directly for deswizzling and swizzling.
# This is a modified version of the original Kukkii swizzler logic by IcySon55 - Kuriimu.

# tex_handler.py
import struct
from io import BytesIO
from typing import Optional, List, Tuple 

from PIL import Image

import constants as C
import swizzle_aclios # MODIFIED: Using Aclios swizzler directly
import image_utils

class NoeBitStream:
    def __init__(self, data: bytes, endian=C.NOE_LITTLEENDIAN):
        self.buffer = data
        self.offset = 0 
        self.bit_buffer = 0
        self.bit_count = 0 
        self.endian = endian 

    def set_endian(self, endian_mode):
        self.endian = endian_mode
    
    def tell(self):
        return self.offset - (self.bit_count // 8)

    def seek(self, new_offset):
        if new_offset < 0 or new_offset > len(self.buffer):
            raise ValueError(f"Seek offset {new_offset} out of bounds for buffer size {len(self.buffer)}")
        self.offset = new_offset
        self.bit_buffer = 0
        self.bit_count = 0

    def read_bytes(self, num_bytes: int) -> bytes:
        if self.bit_count > 0: 
            self.align_to_byte() 
            
        if self.offset + num_bytes > len(self.buffer):
            raise EOFError(f"Not enough data to read {num_bytes} bytes. Offset={self.offset}, Need={num_bytes}, Avail={len(self.buffer)-self.offset}")
        data_slice = self.buffer[self.offset : self.offset + num_bytes]
        self.offset += num_bytes
        return data_slice

    def _read_integral(self, fmt_char: str, size: int):
        if self.bit_count > 0:
            self.align_to_byte()
        
        prefix = ">" if self.endian == C.NOE_BIGENDIAN else "<"
        val = struct.unpack(prefix + fmt_char, self.read_bytes(size))[0]
        return val

    def read_uint(self) -> int: return self._read_integral('I', 4)
    def read_ushort(self) -> int: return self._read_integral('H', 2)
    def read_byte(self) -> int: return self._read_integral('B', 1)
    def read_int(self) -> int: return self._read_integral('i', 4)

    def read_bits(self, num_bits: int) -> int: 
        if not (0 < num_bits <= 32):
            raise ValueError("num_bits must be between 1 and 32 for read_bits")

        value = 0
        bits_read_so_far = 0
        while bits_read_so_far < num_bits:
            if self.bit_count == 0: 
                if self.offset >= len(self.buffer):
                    raise EOFError(f"Not enough bytes in stream for read_bits ({num_bits} requested, {bits_read_so_far} read, EOF at byte {self.offset})")
                byte_val = self.buffer[self.offset]
                self.offset += 1
                self.bit_buffer = byte_val
                self.bit_count = 8
            
            bits_to_take_this_round = min(num_bits - bits_read_so_far, self.bit_count)
            taken_bits = self.bit_buffer & ((1 << bits_to_take_this_round) - 1)
            value |= (taken_bits << bits_read_so_far)
            
            self.bit_buffer >>= bits_to_take_this_round
            self.bit_count -= bits_to_take_this_round
            bits_read_so_far += bits_to_take_this_round
        return value

    def align_to_byte(self):
        self.bit_buffer = 0
        self.bit_count = 0

class TexFile:
    def __init__(self):
        self.magic: int = 0
        self.version: int = 0
        self.alpha_flags: int = 0
        self.mip_map_count: int = 0
        self.width: int = 0
        self.height: int = 0
        self.format: int = 0 
        self.image_data_length: int = 0 
        self.total_data_length_all_mips: int = 0
        self.mip_offsets: List[int] = []
        
        self.pixel_data_swizzled_mip0: Optional[bytes] = None
        self.pixel_data_linear_mip0: Optional[bytes] = None
        self.image: Optional[Image.Image] = None 

        self.is_big_endian: bool = False
        self.filepath: Optional[str] = None
        
        self.k_unk1: int = 0 
        self.k_unused1: int = 0 
        self.k_unk2: int = 0 
        self.k_unk3: int = 0 
        self.k_switch_unknown_data_block: Optional[bytes] = None

    def get_format_str(self) -> str: 
        if self.version == C.MHGU_VERSION:
            if self.format == 0x07: return "BGRA8888" 
            if self.format == 0x13: return "DXT1"
            if self.format == 0x17: return "DXT5"
            if self.format == 0x19: return "ATI1" 
            if self.format == 0x1F: return "ATI2" 
            return f"SwitchV160_Fmt{self.format}"
        return f"UnknownV{self.version}_Fmt{self.format}"

    def is_dxt_format(self) -> bool: # MODIFIED: Uses the helper now
        return is_dxt_format_from_id(self.format, self.version)

def get_aclios_format_params(mtf_format_id: int) -> Tuple[Tuple[int,int], int]:
    if mtf_format_id == 0x13: return (4,4), 8    # DXT1
    elif mtf_format_id == 0x17: return (4,4), 16 # DXT5
    elif mtf_format_id == 0x19: return (4,4), 8  # ATI1 (BC4)
    elif mtf_format_id == 0x1F: return (4,4), 16 # ATI2 (BC5)
    elif mtf_format_id == 0x07: return (1,1), 4  # BGRA8888
    raise ValueError(f"Unsupported MTF format ID {mtf_format_id} for Aclios swizzler params")

def load_tex_from_data(data: bytes) -> Optional[TexFile]:
    tex = TexFile()
    bs = NoeBitStream(data)

    try:
        tex.magic = bs.read_uint()
    except EOFError:
        # print("TEX_HANDLER_ERROR: Not enough data for magic number.")
        return None

    if tex.magic == C.MAGIC_TEX_LITTLE: tex.is_big_endian = False
    elif tex.magic == C.MAGIC_TEX_BIG: tex.is_big_endian = True
    else:
        # print(f"TEX_HANDLER_ERROR: Unknown TEX magic: {hex(tex.magic)}")
        return None
    bs.set_endian(C.NOE_BIGENDIAN if tex.is_big_endian else C.NOE_LITTLEENDIAN)

    try:
        raw_block1 = bs.read_uint()
        tex.version = raw_block1 & 0xFFF
        tex.k_unk1 = (raw_block1 >> 12) & 0xFFF
        tex.k_unused1 = (raw_block1 >> 24) & 0xF
        tex.alpha_flags = (raw_block1 >> 28) & 0xF
        
        raw_block2 = bs.read_uint()
        raw_mip_count_from_header = raw_block2 & 0x3F
        tex.width = (raw_block2 >> 6) & 0x1FFF
        raw_height_from_header = (raw_block2 >> 19) & 0x1FFF
        tex.height = max(raw_height_from_header, 8)
        
        raw_block3 = bs.read_uint()
        tex.k_unk2 = raw_block3 & 0xFF
        tex.format = (raw_block3 >> 8) & 0xFF
        tex.k_unk3 = (raw_block3 >> 16) & 0xFFFF
        
        if tex.version != C.MHGU_VERSION:
            # print(f"TEX_HANDLER_ERROR: Unsupported version {tex.version}. Only MHGU (V160) supported.")
            return None
        if tex.width == 0 or tex.height == 0:
            # print("TEX_HANDLER_ERROR: Texture dimensions are zero.")
            return None

        tex_overall_size_field = bs.read_uint()
        tex.mip_map_count = raw_mip_count_from_header
        tex.total_data_length_all_mips = tex_overall_size_field
            
        if tex.mip_map_count > 0:
            for _ in range(tex.mip_map_count):
                tex.mip_offsets.append(bs.read_uint())
        
        start_of_pixel_data_section = bs.tell()
        offset_of_mip0_relative_to_pixel_section_start = 0
        length_of_mip0_data_to_read = 0

        if tex.mip_map_count > 0 and tex.mip_offsets:
            offset_of_mip0_relative_to_pixel_section_start = tex.mip_offsets[0]
            if tex.mip_map_count == 1:
                length_of_mip0_data_to_read = tex.total_data_length_all_mips - tex.mip_offsets[0]
            else: 
                length_of_mip0_data_to_read = tex.mip_offsets[1] - tex.mip_offsets[0]
        elif tex.mip_map_count > 0: 
            length_of_mip0_data_to_read = tex.total_data_length_all_mips
        # else: length_of_mip0_data_to_read = 0 # Already 0

        tex.image_data_length = length_of_mip0_data_to_read

        if tex.image_data_length < 0:
            # print(f"TEX_HANDLER_ERROR: Calculated Mip0 length is negative ({tex.image_data_length}).")
            return None
        
        actual_seek_target_for_mip0 = start_of_pixel_data_section + offset_of_mip0_relative_to_pixel_section_start
        
        if actual_seek_target_for_mip0 < 0 or actual_seek_target_for_mip0 + tex.image_data_length > len(data):
            # print(f"TEX_HANDLER_ERROR: Mip0 data range (Offset:{actual_seek_target_for_mip0}, Len:{tex.image_data_length}) OOB for file size {len(data)}.")
            return None

        bs.seek(actual_seek_target_for_mip0) 
        if tex.image_data_length > 0 :
            tex.pixel_data_swizzled_mip0 = bs.read_bytes(tex.image_data_length)
        else:
            tex.pixel_data_swizzled_mip0 = b""
            if tex.width > 0 and tex.height > 0:
                 print("TEX_HANDLER_WARNING: Mip0 length is 0 for non-empty texture dimensions.")

    except EOFError as e:
        # print(f"TEX_HANDLER_ERROR: EOF during header/data read. {e}")
        return None
    except ValueError as e:
        # print(f"TEX_HANDLER_ERROR: Invalid value during header/data read. {e}")
        return None
    except Exception as e:
        # print(f"TEX_HANDLER_ERROR: Unexpected error during header/data read. {e}")
        # import traceback; traceback.print_exc() # Keep for unexpected during dev
        return None

    if tex.pixel_data_swizzled_mip0:
        if tex.version == C.MHGU_VERSION: 
            try:
                aclios_block_wh, aclios_bytes_per_block = get_aclios_format_params(tex.format)
                aclios_swizzle_mode = 4 # Using 1 as per your last test
                
                print(f"TEX_HANDLER_DEBUG: Using Aclios deswizzle. ImSize=({tex.width},{tex.height}), BlockSize={aclios_block_wh}, BpB={aclios_bytes_per_block}, SwizzleMode={aclios_swizzle_mode}")
                print(f"  Input swizzled data length: {len(tex.pixel_data_swizzled_mip0)}")
                
                tile_width_pixels = (64 // aclios_bytes_per_block) * aclios_block_wh[0]
                tile_height_pixels = 8 * aclios_block_wh[1] * (2 ** aclios_swizzle_mode)

                if tex.width % tile_width_pixels != 0 or tex.height % tile_height_pixels != 0:
                    print(f"TEX_HANDLER_WARNING: Aclios padding mismatch! Texture WxH ({tex.width}x{tex.height}) "
                          f"is not multiple of Aclios tile WxH ({tile_width_pixels}x{tile_height_pixels}).")
                
                deswizzler = swizzle_aclios.BytesDeswizzle(
                    platform='nsw', data=tex.pixel_data_swizzled_mip0,
                    im_size=(tex.width, tex.height), block_size=aclios_block_wh,
                    bytes_per_block=aclios_bytes_per_block, swizzle_mode=aclios_swizzle_mode
                )
                unswizzled_data = deswizzler.deswizzle()
                tex.pixel_data_linear_mip0 = unswizzled_data
            except (swizzle_aclios.InvalidInputDatasize, swizzle_aclios.MissingSwizzleMode, swizzle_aclios.InvalidImageDimension) as aclios_e:
                print(f"TEX_HANDLER_ERROR: Aclios known error: {aclios_e}")
                tex.pixel_data_linear_mip0 = tex.pixel_data_swizzled_mip0 
            except Exception as e_unswizzle:
                print(f"TEX_HANDLER_ERROR: Aclios Unswizzling failed unexpectedly: {e_unswizzle}")
                # import traceback; traceback.print_exc()
                tex.pixel_data_linear_mip0 = tex.pixel_data_swizzled_mip0 
        else: 
            tex.pixel_data_linear_mip0 = tex.pixel_data_swizzled_mip0

        if tex.pixel_data_linear_mip0:
            if tex.is_dxt_format(): # Uses the instance method now
                dxt_fmt_str = tex.get_format_str()
                rgba_data = image_utils.decode_dxt_to_rgba(tex.pixel_data_linear_mip0, tex.width, tex.height, dxt_fmt_str)
                if rgba_data:
                    try: tex.image = Image.frombytes("RGBA", (tex.width, tex.height), rgba_data)
                    except Exception as e_pil: print(f"TEX_HANDLER_ERROR: Pillow Image.frombytes failed: {e_pil}")
            elif tex.get_format_str() == "BGRA8888": 
                tex.image = image_utils.bgra_to_image(tex.pixel_data_linear_mip0, tex.width, tex.height)
    return tex

def get_mtf_format_id_from_string_kukkii_switch(format_str: str) -> Optional[int]:
    s = format_str.upper()
    if s in ["DXT1", "BC1"]: return 0x13
    if s in ["DXT5", "BC3", "BC5"]: return 0x17 
    if s in ["ATI1", "BC4"]: return 0x19
    if s in ["ATI2"]: return 0x1F # BC5 is ATI2
    if s == "BGRA8888": return 0x07
    return None # BC7 not in Kukkii's SwitchFormats provided

def is_dxt_format_from_id(mtf_format_id: int, version: int = C.MHGU_VERSION) -> bool: # Standalone helper
    if version == C.MHGU_VERSION:
        return mtf_format_id in [0x13, 0x17, 0x19, 0x1F] # DXT1, DXT5, ATI1, ATI2
    return False

def save_tex_to_data(base_tex_info: TexFile, output_image: Image.Image, export_format_str: str) -> Optional[bytes]:
    if not output_image: return None
    # Use the original version from base_tex_info if it's set by the main_gui logic.
    # The main_gui will explicitly set base_tex_info.version = C.MHGU_VERSION
    # for all exports, so this check primarily serves as a warning if somehow a different
    # version was passed down.
    if base_tex_info.version != C.MHGU_VERSION: 
        print(f"TEX_HANDLER_WARNING: Exporting with version {base_tex_info.version} instead of MHGU_VERSION {C.MHGU_VERSION}. Results may vary.")
        
    new_tex_format_id = get_mtf_format_id_from_string_kukkii_switch(export_format_str) # MODIFIED Call
    if new_tex_format_id is None:
        print(f"TEX_HANDLER_ERROR: Unsupported export format '{export_format_str}' for MHGU.")
        return None

    linear_pixel_data_for_swizzling: Optional[bytes] = None
    # MODIFIED Call to use helper
    if is_dxt_format_from_id(new_tex_format_id, C.MHGU_VERSION): 
        rgba_bytes = output_image.convert("RGBA").tobytes("raw", "RGBA")
        dxt_encode_name = export_format_str 
        # Aclios uses general DXT names, texconv maps them.
        # if export_format_str == "ATI1": dxt_encode_name = "ATI1" 
        # elif export_format_str == "ATI2": dxt_encode_name = "ATI2"
        dxt_data = image_utils.encode_rgba_to_dxt(rgba_bytes, output_image.width, output_image.height, dxt_encode_name)
        if not dxt_data: return None
        linear_pixel_data_for_swizzling = dxt_data
    elif export_format_str.upper() == "BGRA8888":
        linear_pixel_data_for_swizzling = image_utils.image_to_bgra(output_image.convert("RGBA"))
    else:
        print(f"TEX_HANDLER_ERROR: Unhandled export prep for: {export_format_str}")
        return None
    
    if not linear_pixel_data_for_swizzling: return None

    try:
        aclios_block_wh, aclios_bytes_per_block = get_aclios_format_params(new_tex_format_id)
        aclios_swizzle_mode = 4 # Corrected: Match mode used for deswizzle

        tile_width_pixels = (64 // aclios_bytes_per_block) * aclios_block_wh[0]
        tile_height_pixels = 8 * aclios_block_wh[1] * (2 ** aclios_swizzle_mode)

        if output_image.width % tile_width_pixels != 0 or output_image.height % tile_height_pixels != 0:
             print(f"TEX_HANDLER_ERROR: Export dimensions ({output_image.width}x{output_image.height}) "
                   f"do not meet Aclios tile multiple requirements ({tile_width_pixels}x{tile_height_pixels}) "
                   f"for format {new_tex_format_id}, mode {aclios_swizzle_mode}. Aborting save.")
             return None

        swizzler = swizzle_aclios.BytesSwizzle(
            platform='nsw', data=linear_pixel_data_for_swizzling,
            im_size=(output_image.width, output_image.height),
            block_size=aclios_block_wh, bytes_per_block=aclios_bytes_per_block,
            swizzle_mode=aclios_swizzle_mode
        )
        swizzled_mip0_data = swizzler.swizzle()
        # print(f"TEX_HANDLER_DEBUG: Aclios Swizzled Mip0 data length for save: {len(swizzled_mip0_data)}")

    except (swizzle_aclios.InvalidInputDatasize, swizzle_aclios.InvalidImageDimension) as aclios_e:
        print(f"TEX_HANDLER_ERROR: Aclios (Swizzle for Save) known error: {aclios_e}")
        return None
    except Exception as e_swizzle:
        print(f"TEX_HANDLER_ERROR: Aclios Swizzling for export failed: {e_swizzle}")
        # import traceback; traceback.print_exc()
        return None

    out_bs_buffer = BytesIO()
    # Use base_tex_info.is_big_endian if TEX was loaded, default to BigE for new Switch TEX
    is_output_big_endian = base_tex_info.is_big_endian if base_tex_info.magic else True
    endian_prefix = ">" if is_output_big_endian else "<" 
    output_magic = base_tex_info.magic if base_tex_info.magic else C.MAGIC_TEX_BIG

    out_bs_buffer.write(struct.pack(endian_prefix + "I", output_magic))

    # Corrected: Use base_tex_info.version directly (which is set by main_gui to C.MHGU_VERSION)
    val1 = ( (base_tex_info.version & 0xFFF) | 
             ((base_tex_info.k_unk1 & 0xFFF) << 12) |
             ((base_tex_info.k_unused1 & 0xF) << 24) |
             ((base_tex_info.alpha_flags & 0xF) << 28) )
    out_bs_buffer.write(struct.pack(endian_prefix + "I", val1))
    
    export_mip_count = 1 # Saving only Mip0
    val2 = ( (export_mip_count & 0x3F) |
             ((output_image.width & 0x1FFF) << 6) |
             ((max(output_image.height, 8) & 0x1FFF) << 19) )
    out_bs_buffer.write(struct.pack(endian_prefix + "I", val2))

    val3 = ( (base_tex_info.k_unk2 & 0xFF) |
             ((new_tex_format_id & 0xFF) << 8) |
             ((base_tex_info.k_unk3 & 0xFFFF) << 16) )
    out_bs_buffer.write(struct.pack(endian_prefix + "I", val3))

    out_bs_buffer.write(struct.pack(endian_prefix + "I", len(swizzled_mip0_data))) 
    out_bs_buffer.write(struct.pack(endian_prefix + "I", 0)) 
    out_bs_buffer.write(swizzled_mip0_data)
    return out_bs_buffer.getvalue()