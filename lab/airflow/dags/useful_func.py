import json
from pathlib import Path
from typing import Any

import yaml

DAGS_DIR = Path(__file__).parent


def read_json(filename: str) -> Any:
    with open(filename) as file:
        return json.load(file)


def read_yaml(filename: str) -> Any:
    with open(DAGS_DIR / filename) as file:
        return yaml.safe_load(file)
