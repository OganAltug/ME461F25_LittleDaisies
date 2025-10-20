from abc import ABC, abstractmethod

class Vector(ABC):
    """Abstract base class for vectors."""

    def _init_(self, *components):
        self.components = components

    @abstractmethod
    def dot(self, other):
        """Abstract method for dot product."""
        pass

    def _add_(self, other):
        if len(self.components) != len(other.components):
            raise ValueError("Vectors must have the same dimension for addition.")
        result = [a + b for a, b in zip(self.components, other.components)]
        return self._class_(*result)

    def _sub_(self, other):
        if len(self.components) != len(other.components):
            raise ValueError("Vectors must have the same dimension for subtraction.")
        result = [a - b for a, b in zip(self.components, other.components)]
        return self._class_(*result)

    def _repr_(self):
        cname = self._class.name_
        return f"{cname}{self.components}"

class Vector2D(Vector):
    """2D vector class."""

    def _init_(self, x, y):
        super()._init_(x, y)

    def dot(self, other):
        if not isinstance(other, Vector2D):
            raise TypeError("Dot product requires another 2D vector.")
        return self.components[0]*other.components[0] + self.components[1]*other.components[1]

    def _mul_(self, other):
        """Multiplication behaves as dot product in 2D."""
        return self.dot(other)

class Vector3D(Vector):
    """3D vector class."""

    def _init_(self, x, y, z):
        super()._init_(x, y, z)

    def dot(self, other):
        if not isinstance(other, Vector3D):
            raise TypeError("Dot product requires another 3D vector.")
        return (self.components[0]*other.components[0] +
                self.components[1]*other.components[1] +
                self.components[2]*other.components[2])

    def _mul_(self, other):
        """Multiplication behaves as cross product in 3D."""
        if not isinstance(other, Vector3D):
            raise TypeError("Cross product requires another 3D vector.")
        x1, y1, z1 = self.components
        x2, y2, z2 = other.components
        return Vector3D(y1*z2 - z1*y2,
                        z1*x2 - x1*z2,
                        x1*y2 - y1*x2)