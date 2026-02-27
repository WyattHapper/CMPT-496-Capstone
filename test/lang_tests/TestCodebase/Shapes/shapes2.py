class AreaCalculator2:
    @staticmethod
    def triangle(base: float, height: float) -> float:
        """Return area of a triangle: 0.5 * base * height.

        Raises ValueError for negative inputs.
        """
        if base < 0 or height < 0:
            raise ValueError("base and height must be non-negative")
        return 0.5 * base * height
