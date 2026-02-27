import math


class AreaCalculator:
    """Utility class to calculate areas of common shapes.

    Methods are static so the class can be used without instantiation.
    """

    @staticmethod
    def rectangle(width: float, height: float) -> float:
        """Return area of a rectangle: width * height.

        Raises ValueError for negative inputs.
        """
        if width < 0 or height < 0:
            raise ValueError("width and height must be non-negative")
        return width * height

    @staticmethod
    def circle(radius: float) -> float:
        """Return area of a circle: pi * r^2.

        Raises ValueError for negative radius.
        """
        if radius < 0:
            raise ValueError("radius must be non-negative")
        return math.pi * (radius ** 2)