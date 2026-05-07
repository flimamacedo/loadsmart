"""OpenAPI 2.0 SRE test API: healthcheck and ALB target management."""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Any

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from src.elb_service import (
    ElbService,
    InstanceAlreadyRegistered,
    InstanceNotRegistered,
    machine_info_to_schema,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.elb_service = ElbService()
    yield


app = FastAPI(title="Site Reliable Engineer Test", version="1.0.0", lifespan=_lifespan)

_basic = HTTPBasic(auto_error=False)


@app.exception_handler(ClientError)
async def _aws_client_error(request: Request, exc: ClientError) -> JSONResponse:
    _ = request
    msg = exc.response.get("Error", {}).get("Message", str(exc))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"AWS error: {msg}"},
    )


@app.exception_handler(BotoCoreError)
async def _aws_botocore_error(request: Request, exc: BotoCoreError) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"AWS error: {exc}"},
    )


@app.exception_handler(RequestValidationError)
async def _validation_to_400(request: Request, exc: RequestValidationError) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "wrong data format", "errors": exc.errors()},
    )


def _get_elb_service(request: Request) -> ElbService:
    return request.app.state.elb_service


def _expected_basic() -> tuple[str, str]:
    user = os.environ.get("API_BASIC_USER", "")
    password = os.environ.get("API_BASIC_PASSWORD", "")
    if not user or not password:
        raise RuntimeError("API_BASIC_USER and API_BASIC_PASSWORD must be set")
    return user, password


def require_basic(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    user, password = _expected_basic()
    ok_user = secrets.compare_digest(credentials.username.encode(), user.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (ok_user and ok_pass):
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
) -> list[dict[str, Any]]:
    machines = svc.list_machines(elb_name)
    if machines is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ELB not found")
    return [machine_info_to_schema(m) for m in machines]


@app.post("/elb/{elb_name}", tags=["elb"], status_code=status.HTTP_201_CREATED)
def attach_instance(
    elb_name: str,
    body: MachineIdBody,
    _: Annotated[None, Depends(require_basic)],
    svc: Annotated[ElbService, Depends(_get_elb_service)],
) -> dict[str, Any]:
    try:
        created = svc.attach_instance(elb_name, body.instanceId)
    except InstanceAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instance already on load balancer",
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if created is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ELB not found")
    return machine_info_to_schema(created)


@app.delete("/elb/{elb_name}", tags=["elb"], status_code=status.HTTP_201_CREATED)
def detach_instance(
    elb_name: str,
    body: MachineIdBody,
    _: Annotated[None, Depends(require_basic)],
    svc: Annotated[ElbService, Depends(_get_elb_service)],
) -> dict[str, Any]:
    try:
        removed = svc.detach_instance(elb_name, body.instanceId)
    except InstanceNotRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instance is not on load balancer",
        ) from None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if removed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ELB not found")
    return machine_info_to_schema(removed)
