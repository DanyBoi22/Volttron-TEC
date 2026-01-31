import json
from pathlib import Path
from typing import Any


def save_json(path: Path, data: Any) -> None:
    """
    Save any serializable Python object as JSON.
    """
    #path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_json(path: Path) -> Any:
    """
    Load JSON file into a Python object.
    """
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)
    
