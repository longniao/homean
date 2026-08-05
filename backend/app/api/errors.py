from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.exceptions import (
    DeliveryUnavailableError,
    DomainValidationError,
    PipelineUnavailableError,
    ResourceConflictError,
    ResourceNotFoundError,
    SensitiveReviewRequiredError,
    VerticalNotSeededError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SensitiveReviewRequiredError)
    async def sensitive_review_required(
        request: Request, exception: SensitiveReviewRequiredError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "detail": str(exception),
                "offending_observation_ids": exception.observation_ids,
            },
        )

    @app.exception_handler(ResourceNotFoundError)
    async def not_found(
        request: Request, exception: ResourceNotFoundError
    ) -> JSONResponse:
        del request, exception
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Not found"}
        )

    @app.exception_handler(ResourceConflictError)
    async def conflict(
        request: Request, exception: ResourceConflictError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exception) or "Resource conflict"},
        )

    @app.exception_handler(DomainValidationError)
    async def invalid_domain_input(
        request: Request, exception: DomainValidationError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exception)},
        )

    @app.exception_handler(VerticalNotSeededError)
    async def missing_vertical(
        request: Request, exception: VerticalNotSeededError
    ) -> JSONResponse:
        del request, exception
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Application configuration is unavailable"},
        )

    @app.exception_handler(PipelineUnavailableError)
    async def pipeline_unavailable(
        request: Request, exception: PipelineUnavailableError
    ) -> JSONResponse:
        del request, exception
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "AI processing could not be queued"},
        )

    @app.exception_handler(DeliveryUnavailableError)
    async def delivery_unavailable(
        request: Request, exception: DeliveryUnavailableError
    ) -> JSONResponse:
        del request, exception
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Report delivery failed"},
        )
