from .azure_llama_api import AzureLlamaAPI
from .i_model import IModel


class CloudModel(IModel):
    def __init__(self):
        self.__model = AzureLlamaAPI()
    
    def generate(self, query: str, temperature=0.8, max_token=2048, top_p=0.1) -> str:
        return self.__model.ask(query, temperature, max_token, top_p)
