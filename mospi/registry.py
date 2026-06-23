"""
Dataset registry loader.

Reads registry/datasets.yaml (the single source of truth for dataset DATA)
and exposes the same module-level structures the server has historically
hardcoded, so the rest of the codebase can import from here instead of
maintaining parallel literals.

Dependency-light: PyYAML + stdlib only.

Module-level exports (built from the YAML at import time):
    VALID_DATASETS              list[str]   - dataset codes, in file order
    DATASET_SWAGGER             dict        - code -> (swagger_file, data_endpoint)
    DATASETS_REQUIRING_INDICATOR list[str]  - codes where indicator_code is mandatory
    DATASET_METADATA            dict        - code -> {"name", "description", "use_for"}

Functions:
    registry_path()             -> str      - absolute path to datasets.yaml
    load_registry()             -> dict     - the full parsed YAML document
"""

import os
from typing import Any, Dict, List, Tuple

import yaml

# Repo root is the parent of the directory holding this file (mospi/).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REGISTRY_PATH = os.path.join(_REPO_ROOT, "registry", "datasets.yaml")


def registry_path() -> str:
    """Return the absolute path to the registry YAML file."""
    return _REGISTRY_PATH


def load_registry() -> Dict[str, Any]:
    """Load and return the full parsed registry document.

    Returns:
        The parsed YAML as a dict with a top-level "datasets" list.
    """
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "datasets" not in data:
        raise ValueError(
            f"Invalid registry file {_REGISTRY_PATH!r}: expected a mapping with a "
            "'datasets' key."
        )
    return data


def _records() -> List[Dict[str, Any]]:
    """Return the list of dataset records in file order."""
    return load_registry()["datasets"]


def _build_valid_datasets(records: List[Dict[str, Any]]) -> List[str]:
    return [rec["code"] for rec in records]


def _build_dataset_swagger(
    records: List[Dict[str, Any]],
) -> Dict[str, Tuple[str, str]]:
    return {
        rec["code"]: (rec["swagger_file"], rec["data_endpoint"])
        for rec in records
    }


def _build_requiring_indicator(records: List[Dict[str, Any]]) -> List[str]:
    return [rec["code"] for rec in records if rec.get("requires_indicator")]


def _build_dataset_metadata(
    records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    return {
        rec["code"]: {
            "name": rec["name"],
            "description": rec["description"],
            "use_for": rec["use_for"],
        }
        for rec in records
    }


# Build the module-level structures once at import time.
_RECORDS = _records()
VALID_DATASETS: List[str] = _build_valid_datasets(_RECORDS)
DATASET_SWAGGER: Dict[str, Tuple[str, str]] = _build_dataset_swagger(_RECORDS)
DATASETS_REQUIRING_INDICATOR: List[str] = _build_requiring_indicator(_RECORDS)
DATASET_METADATA: Dict[str, Dict[str, str]] = _build_dataset_metadata(_RECORDS)


__all__ = [
    "VALID_DATASETS",
    "DATASET_SWAGGER",
    "DATASETS_REQUIRING_INDICATOR",
    "DATASET_METADATA",
    "load_registry",
    "registry_path",
]
