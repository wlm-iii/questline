from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from questline.providers.google_maps import MapsUnavailable

CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "import_too_large",
    422: "validation_error",
    503: "provider_unavailable",
}


async def http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    detail = exc.detail
    error = (
        detail
        if isinstance(detail, dict)
        else {"code": CODES.get(exc.status_code, "request_failed"), "message": str(detail)}
    )
    return JSONResponse({"error": error}, status_code=exc.status_code, headers=exc.headers)


async def maps_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, MapsUnavailable)
    return JSONResponse(
        {"error": {"code": "provider_unavailable", "message": str(exc)}}, status_code=503
    )


async def validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Avoid echoing input values (tokens, transcripts, credentials) into error responses.
    return JSONResponse(
        {"error": {"code": "validation_error", "message": "Invalid request fields"}},
        status_code=422,
    )
