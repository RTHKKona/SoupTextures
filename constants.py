# Some of this is taken from Noesis script for Monster Hunter Generations Ultimate (MHGU)
# constants.py

# Color Scheme
BG_COLOR = '#2b2b2b'
TEXT_COLOR = '#ffebcd'
WIDGET_BG = '#3c3f41'
INPUT_BG = '#313335' # Slightly different for input fields like Text
INPUT_TEXT_COLOR = '#f0f0f0'
BUTTON_BG = '#4c4c4c'
BUTTON_FG = TEXT_COLOR
BUTTON_ACTIVE_BG = '#5c5c5c'
BUTTON_BORDER_COLOR = '#1e1e1e' # For highlightthickness
DISABLED_BUTTON_BG = '#404040'
DISABLED_BUTTON_FG = '#888888'

HEADER_BG = '#4a4a4a'
HEADER_TEXT = TEXT_COLOR

HIGHLIGHT_BG = '#52596b' # For selected items or active areas
HIGHLIGHT_TEXT = '#00f7ff'

STATUS_ERROR_FG = '#ff6b6b'
STATUS_WARN_FG = '#ffb366'
STATUS_SUCCESS_FG = '#86e3a0'
STATUS_INFO_FG = TEXT_COLOR
STATUS_DEBUG_FG = '#999999'

# TEX Magic Numbers
MAGIC_TEX_LITTLE = 5784916  # TEX\0
MAGIC_TEX_BIG = 1413830656  # \0XET
MAGIC_TEX_MOBILE = 542655828 # TEX (space)

# Noesis Constants (for reference, may need to adapt)
NOE_BIGENDIAN = 1
NOE_LITTLEENDIAN = 0

# DXT/BC FourCCs (from Noesis script)
FOURCC_DXT1 = 0x31545844 # "DXT1"
FOURCC_DXT3 = 0x33545844 # "DXT3"
FOURCC_DXT5 = 0x35545844 # "DXT5"
FOURCC_ATI1 = 0x31495441 # "ATI1" / BC4
FOURCC_ATI2 = 0x32495441 # "ATI2" / BC5
FOURCC_BC7  = 0x374342   # "BC7 " (reverse for int) -> 0x20374342

# MHGU (Switch) Specifics
MHGU_VERSION = 160
# Common MHGU Formats (from Noesis script for Version 160)
# Format 7: RGBA8888 (b8g8r8a8 in Noesis, check byte order) -> Actually BGRA for Switch typically
# Format 19: DXT1/BC1
# Format 23: DXT5/BC5
# Format 25: ATI1/BC4
# Format 31: ATI2/BC5