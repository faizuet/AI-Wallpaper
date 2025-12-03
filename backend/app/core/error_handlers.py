from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request, FastAPI

def add_exception_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Collect all error messages
        messages = [err["msg"] for err in exc.errors()]
        # If only one error, return a single message
        if len(messages) == 1:
            return JSONResponse(status_code=422, content={"msg": messages[0]})
        # Otherwise return them all
        return JSONResponse(status_code=422, content={"errors": messages})

