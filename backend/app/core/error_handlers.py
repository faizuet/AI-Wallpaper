import logging
from logging.handlers import RotatingFileHandler
import time

from fastapi import Request, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------
# Configure Logging
# ---------------------------
logger = logging.getLogger("genwalls")
logger.setLevel(logging.INFO)

# Create logs directory if missing
import os
os.makedirs("logs", exist_ok=True)

# File handler (rotating logs)
file_handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,            # Keep last 5 logs
)
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Log format
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers if not already added
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ---------------------------
# Add Exception Handlers
# ---------------------------
def add_exception_handlers(app: FastAPI):

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        logger.info(f"Incoming request: {request.method} {request.url}")

        response = await call_next(request)

        duration = time.time() - start_time

        #  Performance logging (slow requests)
        if duration > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.url} took {duration:.2f}s"
            )
        else:
            logger.info(
                f"Completed request: {request.method} {request.url} in {duration:.2f}s"
            )

        return response

    #  Validation Errors (Pydantic / FastAPI)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        messages = [err["msg"] for err in exc.errors()]

        logger.warning(
            f"Validation error at {request.url}: {messages}"
        )

        if len(messages) == 1:
            return JSONResponse(status_code=422, content={"msg": messages[0]})
        return JSONResponse(status_code=422, content={"errors": messages})

    #  HTTPException (raise HTTPException)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(
            f"HTTPException at {request.url}: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"msg": exc.detail},
        )

    #  ValueError (your validators)
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.error(
            f"ValueError at {request.url}: {str(exc)}"
        )
        return JSONResponse(
            status_code=400,
            content={"msg": str(exc)},
        )

    #  Catch-All for Unexpected Errors
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.critical(
            f"Unexpected error at {request.url}: {repr(exc)}"
        )
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={"msg": "An unexpected error occurred. Please try again."},
        )

