"""Planted faults and the product loader.

A plant is a text patch on a copy of the product tree, made in a temp dir. The
real tree is never touched. A patch whose anchor is missing or ambiguous fails
loudly: a stale plant that silently applies nothing would grade the sim green.
"""

import importlib.util
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
DEFAULT_TREE = HERE.parent / "product"


@dataclass(frozen=True)
class Plant:
    file: str
    old: str
    new: str
    catches: str


PLANTS = {
    "ack_before_fsync": Plant(
        file="kvcore.py",
        old="        if isinstance(done, AppendDone):\n            return []\n",
        new="        if isinstance(done, AppendDone):\n"
        "            return self._ack_through(self._pending.get(done.op, -1))\n",
        catches="acked write lost after crash before fsync",
    ),
    "accept_mid_log_corruption": Plant(
        file="kvcore.py",
        old="            if rec.at_tail:\n",
        new="            if rec.at_tail or True:\n",
        catches="recovery truncated a corrupt record instead of refusing",
    ),
    "refuse_torn_tail": Plant(
        file="kvcore.py",
        old='        return Bad("short body", at_tail=True)\n',
        new='        return Bad("short body", at_tail=False)\n',
        catches="recovery refused a torn write as corruption",
    ),
}


class PlantError(Exception):
    pass


def load_product(tree: Path, plant: str | None = None) -> ModuleType:
    """Import kvcore from `tree`, or from a patched copy of it when `plant` names one."""
    if plant is None:
        return _import(tree / "kvcore.py")
    if plant not in PLANTS:
        raise PlantError(f"unknown plant {plant!r}; known: {', '.join(PLANTS)}")
    spec = PLANTS[plant]
    with tempfile.TemporaryDirectory(prefix=f"kv-plant-{plant}-") as tmp:
        copy = Path(tmp) / "product"
        shutil.copytree(tree, copy)
        target = copy / spec.file
        text = target.read_text()
        if text.count(spec.old) != 1:
            raise PlantError(f"plant {plant}: anchor found {text.count(spec.old)} times in {spec.file}")
        target.write_text(text.replace(spec.old, spec.new))
        return _import(target)


def _import(path: Path) -> ModuleType:
    # Importing must not write __pycache__ into the product tree: agents never write there.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(f"kvcore_{id(path)}", path)
    if spec is None or spec.loader is None:
        raise PlantError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
