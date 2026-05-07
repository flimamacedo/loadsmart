import base64

import pytest
from fastapi.testclient import TestClient

from src.elb_service import InstanceAlreadyRegistered, InstanceNotRegistered, MachineInfo
from src.main import app, _get_elb_service


class FakeElbService:
    def __init__(self) -> None:
        self.list_result: list[MachineInfo] | None = []
        self.attach_result: MachineInfo | None = MachineInfo(
            instance_id="i-abc",
            instance_type="t3.micro",
            launch_date="2020-01-01T00:00:00.000Z",
        )
        self.detach_result: MachineInfo | None = self.attach_result
        self.attach_exc: Exception | None = None
        self.detach_exc: Exception | None = None

    def list_machines(self, elb_name: str) -> list[MachineInfo] | None:
        _ = elb_name
        return self.list_result

    def attach_instance(self, elb_name: str, instance_id: str) -> MachineInfo | None:
        _ = elb_name
        if self.attach_exc:
            raise self.attach_exc
        return self.attach_result

    def detach_instance(self, elb_name: str, instance_id: str) -> MachineInfo | None:
        _ = elb_name
        if self.detach_exc:
            raise self.detach_exc
        return self.detach_result


@pytest.fixture
def client():
    fake = FakeElbService()

    def _override_svc() -> FakeElbService:
        return fake

    app.dependency_overrides[_get_elb_service] = _override_svc
    with TestClient(app) as c:
        c.fake = fake  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


def _basic(u: str, p: str) -> dict[str, str]:
    t = base64.b64encode(f"{u}:{p}".encode()).decode()
    return {"Authorization": f"Basic {t}"}


def test_healthcheck_public(client: TestClient) -> None:
    r = client.get("/healthcheck")
    assert r.status_code == 200


def test_healthcheck_with_auth(client: TestClient, auth_header: dict[str, str]) -> None:
    r = client.get("/healthcheck", headers=auth_header)
    assert r.status_code == 200


def test_elb_requires_auth(client: TestClient) -> None:
    r = client.get("/elb/my-alb")
    assert r.status_code == 401


def test_wrong_password(client: TestClient) -> None:
    r = client.get("/elb/any", headers=_basic("testuser", "wrong"))
    assert r.status_code == 401


def test_list_machines(client: TestClient, auth_header: dict[str, str]) -> None:
    c = client
    fake: FakeElbService = c.fake  # type: ignore[attr-defined]
    fake.list_result = [
        MachineInfo(
            instance_id="i-1",
            instance_type="t3.micro",
            launch_date="2020-01-01T00:00:00.000Z",
        )
    ]
    r = c.get("/elb/my-alb", headers=auth_header)
    assert r.status_code == 200
    assert r.json() == [
        {"instanceId": "i-1", "instanceType": "t3.micro", "launchDate": "2020-01-01T00:00:00.000Z"}
    ]


def test_list_machines_empty(client: TestClient, auth_header: dict[str, str]) -> None:
    r = client.get("/elb/my-alb", headers=auth_header)
    assert r.status_code == 200
    assert r.json() == []


def test_list_machines_404(client: TestClient, auth_header: dict[str, str]) -> None:
    c = client
    fake: FakeElbService = c.fake  # type: ignore[attr-defined]
    fake.list_result = None
    r = c.get("/elb/missing", headers=auth_header)
    assert r.status_code == 404


def test_attach_201(client: TestClient, auth_header: dict[str, str]) -> None:
    r = client.post(
        "/elb/x",
        headers={**auth_header, "Content-Type": "application/json"},
        json={"instanceId": "i-abc"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["instanceId"] == "i-abc"


def test_attach_404(client: TestClient, auth_header: dict[str, str]) -> None:
    c = client
    fake: FakeElbService = c.fake  # type: ignore[attr-defined]
    fake.attach_result = None
    r = c.post(
        "/elb/missing",
        headers={**auth_header, "Content-Type": "application/json"},
        json={"instanceId": "i-x"},
    )
    assert r.status_code == 404


def test_attach_409(client: TestClient, auth_header: dict[str, str]) -> None:
    c = client
    fake: FakeElbService = c.fake  # type: ignore[attr-defined]
    fake.attach_exc = InstanceAlreadyRegistered("i-x")
    r = c.post(
        "/elb/x",
        headers={**auth_header, "Content-Type": "application/json"},
        json={"instanceId": "i-x"},
    )
    assert r.status_code == 409


def test_attach_400_body(client: TestClient, auth_header: dict[str, str]) -> None:
    r = client.post(
        "/elb/x",
        headers={**auth_header, "Content-Type": "application/json"},
        json={"nope": 1},
    )
    assert r.status_code == 400


def test_detach_201(client: TestClient, auth_header: dict[str, str]) -> None:
    r = client.request(
        "DELETE",
        "/elb/x",
        headers={**auth_header, "Content-Type": "application/json"},
        json={"instanceId": "i-abc"},
    )
    assert r.status_code == 201
    assert r.json()["instanceId"] == "i-abc"


def test_detach_409(client: TestClient, auth_header: dict[str, str]) -> None:
    c = client
    fake: FakeElbService = c.fake  # type: ignore[attr-defined]
    fake.detach_exc = InstanceNotRegistered("i-x")
    r = c.request(
        "DELETE",
        "/elb/x",
        headers={**auth_header, "Content-Type": "application/json"},
        json={"instanceId": "i-x"},
    )
    assert r.status_code == 409
