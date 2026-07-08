from abc import ABC, abstractmethod
from pathlib import Path


class BaseLoader(ABC):

    @abstractmethod
    def load(self, file_path: Path) -> str:
        pass
