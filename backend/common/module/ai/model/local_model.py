from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

from .i_model import IModel

DEFAULT_MODEL_NAME="llama3.2"

class LocalModel(IModel):
    def __init__(self, model_name=DEFAULT_MODEL_NAME):
        self.__model = ChatOllama(
            model = model_name
        )
        self.__chain = self.__model | StrOutputParser()

    def generate(self, query: str, temperature=0.8, max_token=2048, top_p=0.1) -> str:
        message = [HumanMessage(content=query)]
        self.__model.temperature = temperature
        self.__model.top_p = top_p
        self.__model.num_predict = max_token
        return self.__chain.invoke(message)
