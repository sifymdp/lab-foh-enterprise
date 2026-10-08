"""
Central ID generation.
All models use uuid4 strings — never millisecond timestamps,
which collide under concurrent load.
"""
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def generate_id(prefix: str = "") -> str:
    uid = str(uuid.uuid4())
    return f"{prefix}-{uid[:8]}" if prefix else uid

