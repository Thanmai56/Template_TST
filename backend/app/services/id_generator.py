from datetime import datetime, timezone
from uuid import uuid4


def new_uuid() -> str:
    return str(uuid4())


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
