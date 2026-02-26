from typing import Iterable, Union

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

    @staticmethod
    def divide(a: Number, b: Number) -> Number:
        """Return a / b. Raises ZeroDivisionError if b == 0."""
        if b == 0:
            raise ZeroDivisionError("division by zero")
        return a / b

    @staticmethod
    def average(values: Iterable[Number]) -> float:
        """Return the arithmetic mean of the given iterable. Raises ValueError on empty."""
        vals = list(values)
        if not vals:
            raise ValueError("average of empty sequence")
        return sum(vals) / len(vals)
