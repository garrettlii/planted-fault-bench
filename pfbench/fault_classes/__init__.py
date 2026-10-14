"""Registry of fault classes. Add new classes here (see prompts/GENERATE_FAULT_CLASS.md)."""
from .motion_group_confound import MotionGroupConfound

REGISTRY = {cls.name: cls for cls in [MotionGroupConfound]}


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"unknown fault class {name!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[name]()
