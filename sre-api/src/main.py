"""OpenAPI 2.0 SRE test API: healthcheck and ALB target management."""

import os
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from src.elb_service import ElbService, InstanceAlreadyRegistered, InstanceNotRegistered

_AUTH_USER = os.environ.get("API_BASIC_USER", "")
_AUTH_PASSWORD = os.environ.get("API_BASIC_PASSWORD", "")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if not _AUTH_USER or not _AUTH_PASSWORD:
        raise RuntimeError("API_BASIC_USER and API_BASIC_PASSWORD must be set")
    app.state.elb_service = ElbService()
    yield


app = FastAPI(title="Site Reliable Engineer Test", version="1.0.0", lifespan=_lifespan)

_basic = HTTPBasic(auto_error=False)


@app.exception_handler(ClientError)
async def _aws_client_error(request: Request, exc: ClientError) -> JSONResponse:
    _ = request
    msg = exc.response.get("Error", {}).get("Message", str(exc))
    return JSONResponse(status_code=503, content={"detail": f"AWS error: {msg}"})


@app.exception_handler(BotoCoreError)
async def _aws_botocore_error(request: Request, exc: BotoCoreError) -> JSONResponse:
    _ = request
    return JSONResponse(status_code=503, content={"detail": f"AWS error: {exc}"})


@app.exception_handler(RequestValidationError)
async def _validation_to_400(request: Request, exc: RequestValidationError) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=400,
        content={"detail": "wrong data format", "errors": exc.errors()},
    )


def _get_elb_service(request: Request) -> ElbService:
    return request.app.state.elb_service


def require_basic(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    ok = secrets.compare_digest(credentials.username.encode(), _AUTH_USER.encode()) and \
         secrets.compare_digest(credentials.password.encode(), _AUTH_PASSWORD.encode())
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


class MachineIdBody(BaseModel):
    instanceId: str


@app.get("/healthcheck", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"version": os.environ.get("APP_VERSION", "unknown")}


@app.get("/elb/{elb_name}", tags=["elb"])
def list_machines_elb(
    elb_name: str,
    _: Annotated[None, Depends(require_basic)],
    svc: Annotated[ElbService, Depends(_get_elb_service)],
) -> list[dict]:
    machines = svc.list_machines(elb_name)
    if machines is None:
        raise HTTPException(status_code=404, detail="ELB not found")
    return [m.to_dict() for m in machines]


@app.post("/elb/{elb_name}", tags=["elb"], status_code=status.HTTP_201_CREATED)
def attach_instance(
    elb_name: str,
    body: MachineIdBody,
    _: Annotated[None, Depends(require_basic)],
    svc: Annotated[ElbService, Depends(_get_elb_service)],
) -> dict:
    try:
        created = svc.attach_instance(elb_name, body.instanceId)
    except InstanceAlreadyRegistered:
        raise HTTPException(status_code=409, detail="Instance already on load balancer") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if created is None:
        raise HTTPException(status_code=404, detail="ELB not found")
    return created.to_dict()


@app.delete("/elb/{elb_name}", tags=["elb"], status_code=status.HTTP_201_CREATED)
def detach_instance(
    elb_name: str,
    body: MachineIdBody,
    _: Annotated[None, Depends(require_basic)],
    svc: Annotated[ElbService, Depends(_get_elb_service)],
) -> dict:
    try:
        removed = svc.detach_instance(elb_name, body.instanceId)
    except InstanceNotRegistered:
        raise HTTPException(status_code=409, detail="Instance is not on load balancer") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if removed is None:
        raise HTTPException(status_code=404, detail="ELB not found")
    return removed.to_dict()
