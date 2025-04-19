from abc import ABC, abstractmethod


class IModel(ABC):
    @abstractmethod
    def generate(self, query: str, temperature=0.8, max_token=2048, top_p=0.1) -> str:
        pass
