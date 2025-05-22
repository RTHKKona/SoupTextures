# This is from the original code by @Acilio which was released under the MIT license, so I am allowed to use it.
# Check the original Github Repo for more details.

import numpy as np
import typing

supported_platforms = ("nsw")

class InvalidInputDatasize(Exception):
    pass

class MissingSwizzleMode(Exception):
    pass

class UnsupportedPlatform(Exception):
    pass

class InvalidImageDimension(Exception):
    pass

class InvalidOutputDatasize(Exception):
    # Exception raised when the output data size unexpectedly differs from input.
    pass

class BytesDeswizzle:
    def __init__(self,platform: str,data: bytearray | bytes,im_size: (int,int),block_size: (int,int),bytes_per_block: int,swizzle_mode: int = None):
        # Initializes the deswizzler with platform-specific parameters.
        self.data = data
        datasize = len(data)
        im_width, im_height = im_size
        block_width, block_height = block_size

        expected_data_size = (im_width * im_height) // (block_width * block_height) * bytes_per_block

        if expected_data_size != datasize:
            raise InvalidInputDatasize(f'Error: Invalid data size.\nExpected datasize (according to image and format specifications): {expected_data_size}\nActual datasize: {datasize}')

        if platform == 'nsw':
            if swizzle_mode is None:
                raise MissingSwizzleMode(f'Error: Swizzle mode required for Nintendo Switch deswizzle')
            # Nintendo Switch specific tile calculation.
            tile_datasize = 512 * (2 ** swizzle_mode)
            tile_width = 64 // bytes_per_block * block_width
            tile_height = 8 * block_height * (2 ** swizzle_mode)
            self.deswizzle_data_list = [(2,0),(2,1),(4,0),(2,1),(2**swizzle_mode,0)]
            self.read_size = 16
            self.read_per_tile_count = 32 * (2 ** swizzle_mode)

        else:
            raise UnsupportedPlatform(f'Error: unknown platform. Supported platforms: {supported_platforms}')

        if datasize % tile_datasize != 0:
            raise InvalidInputDatasize(f'Error: Invalid data size. The data size should be a multiple of {tile_datasize}, while the given datasize is {datasize}. Height and/or width padding may be required in the original image.')

        self.tile_count = datasize // tile_datasize

        if im_width % tile_width != 0:
            raise InvalidImageDimension(f'Error: with the current parameters, image width should be a multiple of {tile_width}, but the given width is {im_width}')

        if im_height % tile_height != 0:
            raise InvalidImageDimension(f'Error: with the current parameters, image height should be a multiple of {tile_height}, but the given height is {im_height}')

        self.tile_per_width = im_width // tile_width
        self.data_read_idx = 0

    def __get_tile_data(self) -> list:
        # Reads data chunks for a single tile and converts them to numpy arrays.
        array_list = []
        for _ in range(self.read_per_tile_count):
            array_list.append(np.array([[self.data[self.data_read_idx:self.data_read_idx + self.read_size]]],dtype = np.void))
            self.data_read_idx += self.read_size
        return array_list

    def __concat_arrays(self,array_list: list,section_number: int,axis: int) -> list:
        # Concatenates a list of numpy arrays along a specified axis.
        new_array_list = []
        idx = 0
        for _ in range(len(array_list) // section_number):
            new_array_list.append(np.concatenate(array_list[idx:idx+section_number],axis=axis))
            idx += section_number
        return new_array_list

    def __deswizzle_tile(self) -> np.array:
        # Deswizzles a single tile by applying a series of concatenations.
        array_list = self.__get_tile_data()
        for deswizzle_data in self.deswizzle_data_list:
            array_list = self.__concat_arrays(array_list,deswizzle_data[0],deswizzle_data[1])
        return array_list[0]

    def deswizzle(self) -> bytes:
        # Deswizzles the entire byte data.
        tile_list = []
        for _ in range(self.tile_count):
            tile_list.append(self.__deswizzle_tile())
        
        # Concatenate tiles horizontally and then vertically.
        tile_list_width_concat = self.__concat_arrays(tile_list,self.tile_per_width,1)
        deswizzled_data = self.__concat_arrays(tile_list_width_concat,len(tile_list_width_concat),0)[0].tobytes()
        
        if len(deswizzled_data) != len(self.data):
            raise InvalidOutputDatasize(f'An unknown error occurred while deswizzling bytes: output data length is (somehow) different than input data length. Input data: {len(self.data)}, Output data: {len(deswizzled_data)}')
        return deswizzled_data


class BytesSwizzle:
    def __init__(self,platform: str,data: bytearray | bytes,im_size: (int,int),block_size: (int,int),bytes_per_block: int,swizzle_mode: int = None):
        # Initializes the swizzler with platform-specific parameters.
        self.data = data
        datasize = len(data)
        im_width, im_height = im_size
        block_width, block_height = block_size

        expected_data_size = (im_width * im_height) // (block_width * block_height) * bytes_per_block

        if expected_data_size != datasize:
            raise InvalidInputDatasize(f'Error: Invalid data size.\nExpected datasize (according to image and format specifications): {expected_data_size}\nActual datasize: {datasize}')

        if platform == 'nsw':
            if swizzle_mode is None:
                raise MissingSwizzleMode(f'Error: Swizzle mode required for Nintendo Switch swizzle')
            # Nintendo Switch specific tile calculation.
            tile_datasize = 512 * (2 ** swizzle_mode)
            tile_width = 64 // bytes_per_block * block_width
            tile_height = 8 * block_height * (2 ** swizzle_mode)
            self.swizzle_data_list = [(2 ** swizzle_mode,0),(2,1),(4,0),(2,1),(2,0)]
            self.read_size = bytes_per_block
            self.column_count = (bytes_per_block * im_width) // (block_width * 16) # Specific for NSW byte layout

        elif platform == 'ps4':
            # PlayStation 4 specific tile calculation.
            tile_datasize = 64 * bytes_per_block
            tile_width = 8 * block_width
            tile_height = 8 * block_height
            self.swizzle_data_list = [(2,0),(2,1),(2,0),(2,1),(2,0),(2,1)]
            self.read_size = bytes_per_block
            self.column_count = im_width // block_width

        else:
            raise UnsupportedPlatform(f'Error: unknown platform. Supported platforms: {supported_platforms}')

        if datasize % tile_datasize != 0:
            raise InvalidInputDatasize(f'Error: Invalid data size. In order to be swizzled, the data size must be a multiple of {tile_datasize}, while the given datasize is {datasize}.')
        
        self.tile_count = datasize // tile_datasize # Redundant, already calculated as datasize // tile_datasize earlier.
        self.tile_per_width = im_width // tile_width
        self.tile_per_height = im_height // tile_height
        self.row_count = im_height // block_height

    def __bytes_to_array(self) -> np.array:
        # Converts linear byte data into a 2D numpy array of byte chunks.
        read_data_idx = 0
        # Initialize an empty list to collect rows.
        rows = []
        for _ in range(self.row_count):
            new_row = []
            for _ in range(self.column_count):
                new_row.append(self.data[read_data_idx:read_data_idx+self.read_size])
                read_data_idx += self.read_size
            rows.append(new_row)
        # Convert the list of lists into a single numpy array.
        return np.array(rows, dtype=np.void)


    def __split_arrays(self,array_list: list,section_number: int,axis: int) -> list:
        # Splits a list of numpy arrays along a specified axis.
        new_array_list = []
        for array in array_list:
            # np.split returns a list of arrays. Extend the result list with these.
            new_array_list.extend(np.split(array,section_number,axis))
        return new_array_list

    def __swizzle_tile(self,array_list: list) -> list:
        # Swizzles a single tile by applying a series of split operations.
        for swizzle_data in self.swizzle_data_list:
            section_number, axis = swizzle_data
            array_list = self.__split_arrays(array_list,section_number,axis)
        return array_list

    def swizzle(self) -> bytes:
        # Swizzles the entire byte data.
        # Start with the entire image data as a single numpy array.
        initial_array_list = [self.__bytes_to_array()]
        
        # Split the array first by height, then by width, into individual tiles.
        split_array_list = self.__split_arrays(initial_array_list,self.tile_per_height,0)
        final_array_list = self.__split_arrays(split_array_list,self.tile_per_width,1)
        
        # Collect all swizzled blocks into a list of bytes, then join them at the end.
        # This is significantly more performant than repeated bytearray += operations.
        swizzled_blocks_bytes = []
        for array in final_array_list:
            # Swizzle each individual tile.
            swizzled_array_list = self.__swizzle_tile([array])
            for block in swizzled_array_list:
                # Extract the raw bytes from the numpy void array element.
                swizzled_blocks_bytes.append(block[0][0].item())
        
        swizzled_data = b"".join(swizzled_blocks_bytes) # Join all blocks into a single bytes object.

        if len(swizzled_data) != len(self.data):
            raise InvalidOutputDatasize('An unknown error occurred while swizzling bytes: output data length is (somehow) different than input data length.')
        return swizzled_data