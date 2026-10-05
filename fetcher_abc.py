from abc import ABC, abstractmethod
from typing import Any, Dict

class Fetcher(ABC):

    @abstractmethod
    async def fetch(self) -> Dict[str, Any]:
        pass
