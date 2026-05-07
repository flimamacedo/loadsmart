import os

import pytest

# Force credentials for pytest so they always match `auth_header`, even when the shell
# has API_BASIC_* set (e.g. admin/changeme from the README) — setdefault would not override.
os.environ["API_BASIC_USER"] = "testuser"
os.environ["API_BASIC_PASSWORD"] = "testpass"


@pytest.fixture
def auth_header() -> dict[str, str]:
    import base64

    token = base64.b64encode(b"testuser:testpass").decode()
    return {"Authorization": f"Basic {token}"}
