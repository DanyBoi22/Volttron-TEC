from pathlib import Path
from typing import Type, TypeVar, List, Dict
from pydantic import BaseModel
from .json_io import save_json, load_json

#-------------- Lists of Pydantic models --------------

def save_model_list(path: Path, models: List[BaseModel]) -> None:
    """Save a list of Pydantic models to JSON."""
    data = [m.model_dump() for m in models]
    save_json(path, data)


def load_model_list(path: Path, model_class: Type[BaseModel]) -> List[BaseModel]:
    """Load a list of Pydantic models from JSON."""
    data = load_json(path)
    return [model_class.model_validate(item) for item in data]

#-------------- Dicts of Pydantic models --------------

def save_model_dict(path: Path, model_dict: Dict[str, BaseModel]) -> None:
    """Save a dict of Pydantic models to JSON."""
    data = {k: v.model_dump() for k, v in model_dict.items()}
    save_json(path, data)


def load_model_dict(path: Path, model_class: Type[BaseModel]) -> Dict[str, BaseModel]:
    """Load a dict of Pydantic models from JSON."""
    data = load_json(path)
    return {key: model_class.model_validate(value) for key, value in data.items()}