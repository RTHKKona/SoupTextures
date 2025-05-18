# swizzle.py
import math
from typing import Tuple, List, Dict, Optional # Keep these for type hinting

# --- Constants and Tables directly from Kukkii's Switch.cs ---
KUKKII_COORDS_BLOCK_SWITCH: Dict[int, List[Tuple[int, int]]] = {
    4: [(1, 0), (2, 0), (0, 1), (0, 2), (4, 0), (0, 4), (8, 0), (0, 8), (0, 16), (16, 0)],
    8: [(1, 0), (2, 0), (0, 1), (0, 2), (0, 4), (4, 0), (0, 8), (0, 16), (8, 0)]
}

KUKKII_COORDS_REGULAR_SWITCH: Dict[int, List[Tuple[int, int]]] = {
    # Kukkii's Switch.cs only explicitly defined [32].
    # If other BPPs are needed for regular formats, their tables would be required from Kukkii.
    # For now, only including what's explicitly in the provided Switch.cs.
    32: [(1, 0), (2, 0), (0, 1), (4, 0), (0, 2), (0, 4), (8, 0), (0, 8), (0, 16)]
}

KUKKII_BLOCK_MAX_SIZE_ELEMENTS = 512
KUKKII_REGULAR_MAX_SIZE_ELEMENTS = 128
# Y-Extension starts at 32 for both block and regular in Kukkii's Switch.cs GetBitField
KUKKII_Y_EXTENSION_START_ELEMENTS = 32

# --- Helper functions (from previous versions, verified with Kukkii context) ---
def get_block_dims(mtf_tex_format: int) -> Tuple[int, int]:
    # Based on Kukkii's SwitchSwizzle.isBlockBased and common knowledge
    # Format 7 (RGBA8888) is regular. Format 23 (DXT5) is block.
    if mtf_tex_format == 7 : return 1,1 # Kukkii Switch.cs RGBA8888 is regular
    if mtf_tex_format == 23: return 4,4 # Kukkii Switch.cs DXT5 is block-based
    # Add other MHGU format mappings based on Kukkii's SwitchSwizzle.isBlockBased if needed
    if mtf_tex_format == 19: return 4,4 # DXT1
    if mtf_tex_format == 25: return 4,4 # ATI1 (BC4)
    if mtf_tex_format == 31: return 4,4 # ATI2 (BC5)
    if mtf_tex_format == 55: return 4,4 # BC7
    if mtf_tex_format == 9 : return 1,1 # RGBA8888 (MHS2 style, but regular)

    raise ValueError(f"Unknown MTF format for block_dims: {mtf_tex_format} in Kukkii context")

def get_bytes_per_element(mtf_tex_format: int) -> int:
    # This remains fairly standard
    if mtf_tex_format == 7: return 4   # RGBA8888
    if mtf_tex_format == 9: return 4   # RGBA8888
    if mtf_tex_format == 19: return 8  # DXT1
    if mtf_tex_format == 23: return 16 # DXT5
    if mtf_tex_format == 25: return 8  # BC4
    if mtf_tex_format == 31: return 16 # BC5
    if mtf_tex_format == 55: return 16 # BC7
    raise ValueError(f"Unknown MTF format for bytes_per_element: {mtf_tex_format}")

def get_bpp_key_for_kukkii_coords(mtf_tex_format: int, is_block_compression: bool) -> int:
    """
    Determines the BPP key for Kukkii's coordsBlock/coordsRegular.
    From Kukkii's DXT.cs: BitDepth is 4 for DXT1, 8 for DXT5.
    From Kukkii's MTTEX.kukki.cs SwitchFormats: RGBA8888 format uses new RGBA(8,8,8,8) which implies 32bpp.
    """
    if is_block_compression:
        # Kukkii's SwitchSwizzle.GetBitField uses `bpp` which comes from `Settings.Format.BitDepth`
        # Kukkii's DXT.cs sets BitDepth = 4 for DXT1, 8 for DXT3/DXT5.
        if mtf_tex_format == 19: return 4  # DXT1
        if mtf_tex_format == 23: return 8  # DXT5
        if mtf_tex_format == 25: return 4  # ATI1 (BC4)
        if mtf_tex_format == 31: return 8  # ATI2 (BC5)
        if mtf_tex_format == 55: return 8  # BC7
        raise ValueError(f"Unhandled Kukkii block compressed MTF format for BPP key: {mtf_tex_format}")
    else: # Regular
        if mtf_tex_format == 7: return 32 # RGBA8888
        if mtf_tex_format == 9: return 32 # RGBA8888
        raise ValueError(f"Unhandled Kukkii regular MTF format for BPP key: {mtf_tex_format}")

# --- Kukkii's MasterSwizzle Port (from Master.cs) ---
class KukkiiMasterSwizzle: # Renamed to avoid any ambiguity
    def __init__(self, image_stride_elements: int, init_point: Tuple[int, int],
                 bit_field_coords: List[Tuple[int, int]]):
        self.init_x = init_point[0]
        self.init_y = init_point[1]
        self.bit_field = bit_field_coords # Kukkii C#: _bitFieldCoords

        if not bit_field_coords:
            self.macro_tile_width = 1
            self.macro_tile_height = 1
        else:
            m_tile_w_or = 0
            # Check if any X component is non-zero before starting aggregate
            if any(item[0] != 0 for item in bit_field_coords):
                 # Find first non-zero to initialize, then OR others. Or just start with 0.
                 # Kukkii C#: bitFieldCoords.Select(p => p.Item1).Aggregate((x, y) => x | y)
                 # This implies if all are 0, result is 0. If list is [{0,1},{0,2}], X aggregate is 0.
                for bx, _ in bit_field_coords: m_tile_w_or |= bx
            self.macro_tile_width = m_tile_w_or + 1

            m_tile_h_or = 0
            if any(item[1] != 0 for item in bit_field_coords):
                for _, by in bit_field_coords: m_tile_h_or |= by
            self.macro_tile_height = m_tile_h_or + 1
            
        if self.macro_tile_width <= 0: self.macro_tile_width = 1
        if self.macro_tile_height <= 0: self.macro_tile_height = 1
        
        # C#: _widthInTiles = (imageStride + MacroTileWidth - 1) / MacroTileWidth;
        if self.macro_tile_width == 0: self.width_in_tiles = 0 
        else: self.width_in_tiles = (image_stride_elements + self.macro_tile_width - 1) // self.macro_tile_width
        
        if self.width_in_tiles == 0 and image_stride_elements > 0 : self.width_in_tiles = 1

    def get(self, point_count: int) -> Tuple[int, int]:
        if self.macro_tile_width == 0 or self.macro_tile_height == 0:
            return self.init_x, self.init_y
        
        points_in_macro_tile = self.macro_tile_width * self.macro_tile_height
        if points_in_macro_tile == 0: return self.init_x, self.init_y

        macro_tile_count = point_count // points_in_macro_tile
        
        if self.width_in_tiles == 0: 
            macro_x = 0
            macro_y = macro_tile_count
        else:
            macro_x = macro_tile_count % self.width_in_tiles
            macro_y = macro_tile_count // self.width_in_tiles

        # Kukkii's Aggregate logic:
        # current_x = self.init_x
        # current_y = self.init_y
        # current_x ^= (macro_x * self.macro_tile_width)
        # current_y ^= (macro_y * self.macro_tile_height)
        # For selected bitfield vectors: current_x ^= bf_x, current_y ^= bf_y

        # Start with init_point, then XOR the base macro tile offset, then XOR selected bitfield vectors
        aggregated_x = self.init_x ^ (macro_x * self.macro_tile_width)
        aggregated_y = self.init_y ^ (macro_y * self.macro_tile_height)

        for j, (bf_x, bf_y) in enumerate(self.bit_field):
            if (point_count >> j) & 1: # Check j-th bit of global pointCount
                aggregated_x ^= bf_x
                aggregated_y ^= bf_y
        
        return aggregated_x, aggregated_y

# --- Kukkii's SwitchSwizzle Port (from Switch.cs) ---
class KukkiiSwitchSwizzle: # Renamed from NxSwizzlePy_Kukkii
    def _to_power_of_two(self, value: int) -> int:
        # Kukkii: 2 << (int)Math.Log(width - 1, 2)
        # This is problematic for value=1 (Log(0)).
        # Python's bit_length method is safer for "next power of 2".
        if value <= 0: return 1 
        if value == 1: return 1
        return 1 << (value - 1).bit_length()

    def _pad_dimensions_dxt_like(self, width_pixels: int, height_pixels: int) -> Tuple[int, int]:
        # Kukkii's SwitchSwizzle.PadDimensions for DXT-like formats
        return ((width_pixels + 3) & ~3, (height_pixels + 3) & ~3)

    def _is_block_based_kukkii(self, mtf_tex_format: int) -> bool:
        # Replicates Kukkii's SwitchSwizzle.isBlockBased(Format format)
        # Need to map mtf_tex_format to Kukkii's SwitchSwizzle.Format enum values for this check
        # For simplicity, using the known MHGU formats:
        if mtf_tex_format in [19, 23, 25, 31, 55]: # DXT1, DXT5, ATI1, ATI2, BC7
            return True
        if mtf_tex_format in [7, 9]: # RGBA8888
            return False
        raise ValueError(f"Kukkii _is_block_based check: unknown mtf_tex_format {mtf_tex_format}")

    def __init__(self, orig_pixel_width: int, orig_pixel_height: int, mtf_tex_format: int,
                 to_power_of_2_initial: bool = True): # Kukkii's default for toPowerOf2

        self.is_block_compression = self._is_block_based_kukkii(mtf_tex_format)
        self.element_block_dim_w, self.element_block_dim_h = get_block_dims(mtf_tex_format)


        # Kukkii's SwitchSwizzle constructor padding logic:
        # 1. Initial optional power-of-2 padding (on original pixel dimensions)
        current_w_pixels = self._to_power_of_two(orig_pixel_width) if to_power_of_2_initial else orig_pixel_width
        current_h_pixels = self._to_power_of_two(orig_pixel_height) if to_power_of_2_initial else orig_pixel_height

        # 2. Then, DXT-like block padding (PadDimensions in Kukkii's SwitchSwizzle)
        if self.is_block_compression: # ASTC not relevant for MHGU
            current_w_pixels, current_h_pixels = self._pad_dimensions_dxt_like(current_w_pixels, current_h_pixels)
        
        # These are the final PADDED pixel dimensions of the swizzle surface (Kukkii's Width/Height properties)
        self.swizzle_surface_pixel_width = current_w_pixels
        self.swizzle_surface_pixel_height = current_h_pixels

        # Convert to PADDED element dimensions for internal use and MasterSwizzle stride
        if self.is_block_compression:
            self.swizzle_surface_element_width = (self.swizzle_surface_pixel_width + self.element_block_dim_w - 1) // self.element_block_dim_w
            self.swizzle_surface_element_height = (self.swizzle_surface_pixel_height + self.element_block_dim_h - 1) // self.element_block_dim_h
        else:
            self.swizzle_surface_element_width = self.swizzle_surface_pixel_width
            self.swizzle_surface_element_height = self.swizzle_surface_pixel_height
        
        # Get BPP key for Kukkii's COORDS tables
        bpp_coords_key = get_bpp_key_for_kukkii_coords(mtf_tex_format, self.is_block_compression)
        
        base_bit_field_list: Optional[List[Tuple[int,int]]]
        max_size_elements_for_ext: int
        y_extension_start: int

        if self.is_block_compression:
            base_bit_field_list = KUKKII_COORDS_BLOCK_SWITCH.get(bpp_coords_key)
            max_size_elements_for_ext = KUKKII_BLOCK_MAX_SIZE_ELEMENTS
            y_extension_start = KUKKII_Y_EXTENSION_START_ELEMENTS # 32 for blocks
        else:
            base_bit_field_list = KUKKII_COORDS_REGULAR_SWITCH.get(bpp_coords_key)
            max_size_elements_for_ext = KUKKII_REGULAR_MAX_SIZE_ELEMENTS
            y_extension_start = KUKKII_Y_EXTENSION_START_ELEMENTS # Kukkii uses 32 for regular

        if base_bit_field_list is None:
            # Kukkii's GetBitField: if bitField is null, returns null.
            # Kukkii's SwitchSwizzle constructor: if bitField is null, uses Linear swizzle.
            # We should error or implement Linear for this case. For now, error.
            raise ValueError(f"No Kukkii COORDS definition for BPP key {bpp_coords_key} (block: {self.is_block_compression})")

        # Bit Field Extension Logic from Kukkii's SwitchSwizzle.GetBitField
        bit_field_extension = []
        current_y_ext = y_extension_start
        # Loop uses swizzle_surface_element_height (Kukkii's Height in GetBitField, which is padded)
        limit_for_ext = min(self.swizzle_surface_element_height, max_size_elements_for_ext)
        while current_y_ext < limit_for_ext :
            bit_field_extension.append((0, current_y_ext))
            current_y_ext *= 2
        
        full_bit_field = base_bit_field_list + bit_field_extension

        # Kukkii's SwitchSwizzle passes its own PADDED element Width to MasterSwizzle as imageStride
        self.master_swizzler = KukkiiMasterSwizzle(
            image_stride_elements=self.swizzle_surface_element_width, # This is Kukkii's `Width` property
            init_point=(0,0),
            bit_field_coords=full_bit_field
        )

        # Store UNPADDED element dimensions for looping over original data in (un)swizzle_data
        if self.is_block_compression:
            self.unpadded_element_width = (orig_pixel_width + self.element_block_dim_w - 1) // self.element_block_dim_w
            self.unpadded_element_height = (orig_pixel_height + self.element_block_dim_h - 1) // self.element_block_dim_h
        else:
            self.unpadded_element_width = orig_pixel_width
            self.unpadded_element_height = orig_pixel_height

    def transform_coords(self, unpadded_linear_element_x: int, unpadded_linear_element_y: int) -> Tuple[int, int]:
        # Kukkii's SwitchSwizzle.Get(Point point): pointCount = point.Y * Width + point.X;
        # `Width` is the padded element width of the SwitchSwizzle instance (self.swizzle_surface_element_width).
        # `point.X` and `point.Y` are conceptual coordinates on this padded grid.
        # Our loop in (un)swizzle_data iterates 0..unpadded_element_width/height.
        # These unpadded_linear_element_x/y are treated as the `point.X` and `point.Y`.
        point_count = unpadded_linear_element_y * self.swizzle_surface_element_width + unpadded_linear_element_x
        return self.master_swizzler.get(point_count)

# --- (un)swizzle_data functions, now using KukkiiSwitchSwizzle ---
def unswizzle_data(swizzled_bytes: bytes,
                   orig_pixel_width: int, orig_pixel_height: int,
                   mtf_tex_format: int) -> bytes:
    if orig_pixel_width == 0 or orig_pixel_height == 0: return b""
    
    bytes_per_element = get_bytes_per_element(mtf_tex_format)
    kukkii_swizzler = KukkiiSwitchSwizzle(orig_pixel_width, orig_pixel_height, mtf_tex_format)

    # Linear data buffer uses UNPADDED element dimensions (from KukkiiSwitchSwizzle)
    width_in_elements_unpadded = kukkii_swizzler.unpadded_element_width
    height_in_elements_unpadded = kukkii_swizzler.unpadded_element_height
    
    linear_size = width_in_elements_unpadded * height_in_elements_unpadded * bytes_per_element
    if linear_size == 0 : return b""
    linear_data = bytearray(linear_size)
    
    # The swizzled data is indexed using the PADDED surface element width (KukkiiSwitchSwizzle.swizzle_surface_element_width)
    swizzled_buffer_stride_elements = kukkii_swizzler.swizzle_surface_element_width

    for y_lin_elem in range(height_in_elements_unpadded): # Iterate over unpadded dimensions
        for x_lin_elem in range(width_in_elements_unpadded):
            sw_x_elem, sw_y_elem = kukkii_swizzler.transform_coords(x_lin_elem, y_lin_elem)
            
            offset_lin = (y_lin_elem * width_in_elements_unpadded + x_lin_elem) * bytes_per_element
            offset_sw = (sw_y_elem * swizzled_buffer_stride_elements + sw_x_elem) * bytes_per_element

            if offset_sw + bytes_per_element > len(swizzled_bytes):
                # Fill with a pattern for error visibility if this happens often
                # for i_err in range(bytes_per_element):
                #    linear_data[offset_lin + i_err] = (0xEE if (offset_lin + i_err) % 2 == 0 else 0x11) & 0xFF
                continue # Skip if out of bounds

            try:
                linear_data[offset_lin : offset_lin + bytes_per_element] = \
                    swizzled_bytes[offset_sw : offset_sw + bytes_per_element]
            except IndexError: # Should be caught by above check, but for safety
                # print(f"IndexError during unswizzle copy: lin_off={offset_lin}, sw_off={offset_sw}, bpe={bytes_per_element}")
                continue 
    return bytes(linear_data)

def swizzle_data(linear_bytes: bytes,
                 orig_pixel_width: int, orig_pixel_height: int,
                 mtf_tex_format: int) -> bytes:
    if orig_pixel_width == 0 or orig_pixel_height == 0: return b""

    bytes_per_element = get_bytes_per_element(mtf_tex_format)
    kukkii_swizzler = KukkiiSwitchSwizzle(orig_pixel_width, orig_pixel_height, mtf_tex_format)

    width_in_elements_unpadded = kukkii_swizzler.unpadded_element_width
    height_in_elements_unpadded = kukkii_swizzler.unpadded_element_height

    # Swizzled data buffer (destination) must be sized for the PADDED surface
    swizzled_buffer_stride_elements = kukkii_swizzler.swizzle_surface_element_width
    # Total height of the swizzled surface is swizzle_surface_element_height
    swizzled_buffer_height_elements = kukkii_swizzler.swizzle_surface_element_height
    
    swizzled_size = swizzled_buffer_stride_elements * \
                    swizzled_buffer_height_elements * \
                    bytes_per_element

    if swizzled_size == 0: return b"" if not linear_bytes else linear_bytes # Safety for empty
    
    swizzled_data = bytearray(swizzled_size) 

    for y_lin_elem in range(height_in_elements_unpadded):
        for x_lin_elem in range(width_in_elements_unpadded):
            sw_x_elem, sw_y_elem = kukkii_swizzler.transform_coords(x_lin_elem, y_lin_elem)
            
            offset_lin = (y_lin_elem * width_in_elements_unpadded + x_lin_elem) * bytes_per_element
            offset_sw = (sw_y_elem * swizzled_buffer_stride_elements + sw_x_elem) * bytes_per_element
            
            if offset_lin + bytes_per_element > len(linear_bytes): continue
            if offset_sw + bytes_per_element > len(swizzled_data): continue
            
            swizzled_data[offset_sw : offset_sw + bytes_per_element] = \
                linear_bytes[offset_lin : offset_lin + bytes_per_element]
                
    return bytes(swizzled_data)