import os
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Dict, List, Optional

import psycopg
import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

# Đọc biến môi trường với giá trị mặc định
SERVICE_NAME = os.getenv("SERVICE_NAME", "iot-ingestion")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://lab05:lab05pass@localhost:5432/iotdb",
)
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:9000")


app = FastAPI(
    title="FIT4110 Lab 05 - IoT Ingestion Service",
    version=SERVICE_VERSION,
    description=(
        "IoT Ingestion API chạy trong ngữ cảnh Docker Compose cho Lab 05. "
        "Luồng logic được kế thừa từ Lab 04 và tiếp tục được dùng để kiểm thử end‑to‑end."
    ),
)


class SensorMetric(str, Enum):
    temperature = "temperature"
    humidity = "humidity"
    motion = "motion"
    smoke = "smoke"


class SensorUnit(str, Enum):
    celsius = "celsius"
    percent = "percent"
    boolean = "boolean"
    ppm = "ppm"


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class SensorReadingCreate(BaseModel):
    device_id: str = Field(..., min_length=3, examples=["ESP32-LAB-A01"])
    metric: SensorMetric = Field(..., examples=["temperature"])
    value: float = Field(
        ...,
        ge=-40,
        le=80,
        description="Boundary range used in Lab 03 và Lab 04: -40 đến 80.",
        examples=[31.5],
    )
    unit: Optional[SensorUnit] = Field(default=None, examples=["celsius"])
    timestamp: str = Field(..., examples=["2026-05-13T08:30:00+07:00"])


class SensorReading(BaseModel):
    reading_id: str
    device_id: str
    metric: SensorMetric
    value: float
    unit: Optional[SensorUnit] = None
    timestamp: str
    created_at: str


class SensorReadingCreated(BaseModel):
    reading_id: str
    device_id: str
    metric: SensorMetric
    accepted: bool
    created_at: str


CREATE_READINGS_TABLE = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id VARCHAR(32) PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    metric VARCHAR(32) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(32),
    measured_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL
)
"""


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def ensure_database() -> None:
    with get_connection() as connection:
        connection.execute(CREATE_READINGS_TABLE)


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    try:
        default_title = HTTPStatus(exc.status_code).phrase
    except ValueError:
        default_title = "HTTP Error"

    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=default_title,
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", default_title)
    problem.setdefault("type", "about:blank")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_reading_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM sensor_readings"
        ).fetchone()
    return f"R-{today}-{row['total'] + 1:04d}"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        ensure_database()
        response = requests.get(f"{AI_SERVICE_URL}/health", timeout=3)
        response.raise_for_status()
    except (psycopg.Error, requests.RequestException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_problem(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="Service Unavailable",
                detail=f"Dependency is not ready: {exc}",
                instance="/health",
            ),
        ) from exc

    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
    )


@app.post(
    "/readings",
    response_model=SensorReadingCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
        429: {"model": ProblemDetails},
    },
)
def create_reading(payload: SensorReadingCreate, response: Response) -> SensorReadingCreated:
    # Ví dụ logic cảnh báo: nếu nhiệt độ >= 70 thì thêm header cảnh báo
    if payload.metric == SensorMetric.temperature and payload.value >= 70:
        response.headers["X-Warning"] = "high-temperature"

    try:
        ensure_database()
        ai_response = requests.post(f"{AI_SERVICE_URL}/predict", timeout=3)
        ai_response.raise_for_status()

        reading_id = next_reading_id()
        created_at = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sensor_readings (
                    reading_id, device_id, metric, value, unit, measured_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    reading_id,
                    payload.device_id,
                    payload.metric.value,
                    payload.value,
                    payload.unit.value if payload.unit else None,
                    payload.timestamp,
                    created_at,
                ),
            )
    except (psycopg.Error, requests.RequestException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_problem(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="Service Unavailable",
                detail=f"Could not reach a required dependency: {exc}",
                instance="/readings",
            ),
        ) from exc

    return SensorReadingCreated(
        reading_id=reading_id,
        device_id=payload.device_id,
        metric=payload.metric,
        accepted=True,
        created_at=created_at,
    )


@app.get("/readings/latest", dependencies=[Depends(verify_bearer_token)])
def latest_readings(
    device_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> Dict[str, List[Dict]]:
    ensure_database()
    query = """
        SELECT reading_id, device_id, metric, value, unit,
               measured_at AS timestamp, created_at
        FROM sensor_readings
    """
    params: List[object] = []
    if device_id:
        query += " WHERE device_id = %s"
        params.append(device_id)
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with get_connection() as connection:
        items = connection.execute(query, params).fetchall()

    return {"items": list(reversed(items))}


@app.get("/readings/{reading_id}", dependencies=[Depends(verify_bearer_token)])
def get_reading(reading_id: str) -> Dict:
    ensure_database()
    with get_connection() as connection:
        item = connection.execute(
            """
            SELECT reading_id, device_id, metric, value, unit,
                   measured_at AS timestamp, created_at
            FROM sensor_readings
            WHERE reading_id = %s
            """,
            (reading_id,),
        ).fetchone()

    if item:
        return item

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=build_problem(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=f"Reading {reading_id} does not exist",
            instance=f"/readings/{reading_id}",
            problem_type="https://smart-campus.local/problems/not-found",
        ),
    )
