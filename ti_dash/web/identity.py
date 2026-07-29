import uuid

DEVICE_COOKIE = "device_id"
ADMIN_COOKIE = "is_admin"


def new_device_id() -> str:
    return uuid.uuid4().hex
