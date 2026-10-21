"""
@file agent/testing/runners/base_runner.py
@brief Defines shared functionlity for all of the other runners 
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class base_runner(ABC):

    """
    @brief The base runner class
    
    @details holds all of the shared functionality that all of the runners need to use
    """

    TIMEOUT = 600

   

    @staticmethod
    def _decode_output(output) -> str:
        """Normalize timeout output across Python versions."""
        if output is None:
            return ""
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        return str(output)