from typing import Iterable, Union

Number = Union[int, float]

class Calculator2:
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