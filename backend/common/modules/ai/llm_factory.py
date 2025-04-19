from enum import StrEnum
from typing import Literal

from .model.cloud_model import CloudModel
from .model.i_model import IModel
from .model.local_model import LocalModel

# from 

class ModelType(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"

class LlmFactory():
    def create(self, model_type: Literal["local", "cloud"]="local", model_name: str="llama3.2"):
        if model_type == ModelType.CLOUD:
            return CloudModel()
        elif model_type == ModelType.LOCAL:
            return LocalModel(model_name)
        else:
            raise Exception("error: Invalid model type")
