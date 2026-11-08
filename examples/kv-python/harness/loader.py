"""Imports the product core from a tree, without writing __pycache__ into it."""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
DEFAULT_TREE = HERE.parent / "product"


class LoadError(Exception):
    pass


def load_product(tree: Path) -> ModuleType:
    path = tree / "kvcore.py"
    # Agents never write into the product tree, and a .pyc is a write.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(f"kvcore_{id(path)}", path)
    if spec is None or spec.loader is None:
        raise LoadError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tree_digest(tree: Path) -> str:
    """sha256 of the product source, so a tape says which code it ran against."""
    return hashlib.sha256((tree / "kvcore.py").read_bytes()).hexdigest()[:16]
