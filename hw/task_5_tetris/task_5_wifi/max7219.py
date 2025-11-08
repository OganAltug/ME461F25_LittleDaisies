# max7219.py
# A minimal MicroPython driver for MAX7219 8x8 LED matrices.
from machine import Pin, SPI
import framebuf

_NOOP = const(0)
_DIGIT0 = const(1)
_DIGIT1 = const(2)
_DIGIT2 = const(3)
_DIGIT3 = const(4)
_DIGIT4 = const(5)
_DIGIT5 = const(6)
_DIGIT6 = const(7)
_DIGIT7 = const(8)
_DECODEMODE = const(9)
_INTENSITY = const(10)
_SCANLIMIT = const(11)
_SHUTDOWN = const(12)
_DISPLAYTEST = const(15)

class Max7219(framebuf.FrameBuffer):
    def __init__(self, width, height, spi, cs, num_matrices=1):
        self.width = width
        self.height = height
        self.spi = spi
        self.cs = cs
        self.num_matrices = num_matrices
        
        # Calculate matrices layout
        self.matrices_w = width // 8
        self.matrices_h = height // 8
        if self.matrices_w * self.matrices_h != self.num_matrices:
            raise ValueError("Width/Height not compatible with number of matrices")

        self.buffer = bytearray(self.width * self.height // 8)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_HLSB)

        self.init()

    def _write(self, command, data):
        self.cs.off()
        for _ in range(self.num_matrices):
            self.spi.write(bytearray([command, data]))
        self.cs.on()

    def init(self):
        for command, data in (
            (_SHUTDOWN, 0),
            (_DISPLAYTEST, 0),
            (_SCANLIMIT, 7),
            (_DECODEMODE, 0),
            (_SHUTDOWN, 1),
        ):
            self._write(command, data)

    def brightness(self, value):
        if not 0 <= value <= 15:
            raise ValueError("Brightness must be 0-15")
        self._write(_INTENSITY, value)

    def show(self):
        # This logic assumes a specific wiring for a 16x32 grid
        # (e.g., 2 wide, 4 high)
        # This implementation is for a simple linear chain.
        # For a 16x32, you'd have 8 matrices.
        
        # Simple linear chain logic (adjust if your matrix layout is complex)
        for y in range(8): # For each row in an 8x8 matrix
            self.cs.off()
            for matrix_index in range(self.num_matrices - 1, -1, -1):
                # Calculate which part of the framebuffer this matrix represents
                # This assumes a 1D chain mapped to 2D
                matrix_x = (matrix_index % self.matrices_w) * 8
                matrix_y = (matrix_index // self.matrices_w) * 8
                
                byte = 0
                for x_offset in range(8):
                    px = self.pixel(matrix_x + x_offset, matrix_y + y)
                    if px:
                        byte |= 1 << (7 - x_offset)
                        
                self.spi.write(bytearray([_DIGIT0 + y, byte]))
            self.cs.on()

    # show() for standard linear horizontal matrix chain
    def show_linear(self):
        for y in range(8):
            self.cs.off()
            for matrix in range(self.num_matrices - 1, -1, -1):
                offset = matrix * 8
                byte = 0
                for x in range(8):
                    if self.pixel(x + offset, y):
                        byte |= 1 << (7 - x)
                self.spi.write(bytearray([_DIGIT0 + y, byte]))
            self.cs.on()
            
    # Use the linear one for simplicity. Your 16x32 is 8 matrices.
    # Re-map pixel to linear
    def show(self):
        # Re-map 16x32 buffer to 8 8x8 matrices
        # Assuming 2x4 layout (matrices 0-3 = col 1, 4-7 = col 2)
        # This is complex. Let's use the 1D (128x8) method
        # The provided driver is 1D. Let's assume 8 matrices in a line (128x8)
        # But the constructor was 16x32. We will use the 16x32 buffer.
        
        # This show() assumes 16x32 (W, H)
        for y_matrix in range(self.matrices_h): # 0, 1, 2, 3
            for y_pixel in range(8): # 0-7
                self.cs.off()
                for x_matrix in reversed(range(self.matrices_w)): # 1, 0
                    # This is the matrix index in the chain
                    # Assuming (0,0) is matrix 0, (8,0) is matrix 1
                    # (0,8) is matrix 2, (8,8) is matrix 3 ...
                    matrix_index = (y_matrix * self.matrices_w) + x_matrix
                    
                    # This is overly complex. Use the original driver's logic.
                    # This driver assumes a horizontal chain.
                    # We will treat the 16x32 as 4 stacked 16x8 sections.
                    # The driver only supports 8 pixels high.
                    # A 16x32 display *is* 8 8x8 matrices.
                    
                    # Let's use the correct show logic for a chained matrix
                    for y_col in range(8): # 0..7
                        self.cs.off()
                        for i in range(self.num_matrices -1, -1, -1):
                            # i = 7, 6, 5, 4, 3, 2, 1, 0
                            matrix_x_start = (i % self.matrices_w) * 8
                            matrix_y_start = (i // self.matrices_w) * 8
                            
                            byte = 0
                            for x_pix in range(8):
                                if self.pixel(matrix_x_start + x_pix, matrix_y_start + y_col):
                                    byte |= 1 << (7-x_pix)
                            
                            self.spi.write(bytearray([_DIGIT0 + y_col, byte]))
                        self.cs.on()