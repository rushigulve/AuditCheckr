"""Abstract base class for all reporters."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import DiffResult


class ReporterBase(ABC):
    reporter_id: str = ""

    @abstractmethod
    def report(self, result: DiffResult, output_dir: str) -> str:
        """Write the report and return the output file path."""
