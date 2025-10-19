class Vector:
    def __init__(self, array):
        self.array = array
    
    def __add__(self, o):
        """Element-wise addition of two lists"""
        return [x + y for x, y in zip(self.array, o.array)]

    def __sub__(self, o):
        """Element-wise subtraction of two lists"""
        return [x - y for x, y in zip(self.array, o.array)]

    def mul_elements(self, a, b):
        """Element-wise multiplication of two lists"""
        return [x * y for x, y in zip(a.array, b.array)]

    def div_elements(self, a, b):
        """Element-wise division of two lists (float division)"""
        return [x / y for x, y in zip(a.array, b.array)]


class Vector2(Vector):
    def __init__(self, array):
        super().__init__(array=array)

    def __mul__(self, other):
        if not isinstance(other, Vector2):
            raise TypeError("Dot product requires another 2D vector.")
        return self.array[0]*other.array[0] + self.array[1]*other.array[1]


class Vector3(Vector):
    def __init__(self, array):
        super().__init__(array=array)

    def __mul__(self, other):
        """Multiplication behaves as cross product in 3D."""
        if not isinstance(other, Vector3):
            raise TypeError("Cross product requires another 3D vector.")
        x1, y1, z1 = self.array[0], self.array[1], self.array[2]
        x2, y2, z2 = other.array[0], other.array[1], other.array[2]
        result = [y1*z2 - z1*y2,
                z1*x2 - x1*z2,
                x1*y2 - y1*x2]
        return Vector3(result)