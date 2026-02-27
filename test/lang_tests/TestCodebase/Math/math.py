from typing import Union

Number = Union[int, float]


class Calculator:
    """
    Simple calculator offering basic arithmetic operations.
    Methods accept ints or floats and return a Number.
    """

    @staticmethod
    def add(*values: Number) -> Number:
        """Return the sum of all provided values. Returns 0 for no args."""
        return sum(values) if values else 0

    @staticmethod
    def subtract(a: Number, b: Number) -> Number:
        """Return the result of a - b"""
        return a - b

    @staticmethod
    def multiply(*values: Number) -> Number:
        """Return the product of all provided values. Returns 1 for no args."""
        if not values:
            return 1
        prod = 1
        for v in values:
            prod *= v
        return prod
