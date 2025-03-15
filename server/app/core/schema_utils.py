# LLM_interviewer/server/app/core/schema_utils.py
from pydantic import BaseModel

def clean_model_title(cls: type[BaseModel]) -> type[BaseModel]:
    """
    A decorator to automatically set the Pydantic model's OpenAPI title
    to its class name. This helps in generating cleaner $ref names in
    the OpenAPI schema, especially for ReDoc compatibility.
    
    Assumes Pydantic v1 style `class Config:` for setting the title.
    If using Pydantic v2 `model_config`, this would need adjustment,
    but the target models are being set to use `class Config:`.
    """
    if not hasattr(cls, 'Config'):
        class Config:
            pass
        cls.Config = Config
    
    cls.Config.title = cls.__name__
    return cls
