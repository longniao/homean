import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_context, get_review_service
from app.schemas.review import (
    ObservationCreate,
    ObservationUpdate,
    ReportUpdate,
    ShowingConfirmationResponse,
    TranscriptSegmentUpdate,
)
from app.schemas.showings import (
    ObservationResponse,
    ReportResponse,
    TranscriptSegmentResponse,
)
from app.services import CurrentContext, RealEstateReviewService

router = APIRouter(tags=["review"])


@router.patch("/observations/{observation_id}", response_model=ObservationResponse)
async def update_observation(
    observation_id: uuid.UUID,
    payload: ObservationUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> ObservationResponse:
    return ObservationResponse.from_observation(
        await service.update_observation(context, observation_id, payload)
    )


@router.post(
    "/observations/{observation_id}/confirm", response_model=ObservationResponse
)
async def confirm_observation(
    observation_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> ObservationResponse:
    return ObservationResponse.from_observation(
        await service.confirm_observation(context, observation_id)
    )


@router.post(
    "/observations/{observation_id}/dismiss", response_model=ObservationResponse
)
async def dismiss_observation(
    observation_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> ObservationResponse:
    return ObservationResponse.from_observation(
        await service.dismiss_observation(context, observation_id)
    )


@router.post(
    "/observations",
    response_model=ObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_observation(
    payload: ObservationCreate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> ObservationResponse:
    return ObservationResponse.from_observation(
        await service.add_observation(context, payload)
    )


@router.patch(
    "/transcript-segments/{segment_id}", response_model=TranscriptSegmentResponse
)
async def update_transcript_segment(
    segment_id: uuid.UUID,
    payload: TranscriptSegmentUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> TranscriptSegmentResponse:
    return TranscriptSegmentResponse.from_segment(
        await service.update_transcript_segment(context, segment_id, payload.text)
    )


@router.patch("/reports/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> ReportResponse:
    return ReportResponse.from_report(
        await service.update_report(
            context, report_id, payload.content.model_dump(mode="json")
        )
    )


@router.post(
    "/showings/{visit_id}/confirm", response_model=ShowingConfirmationResponse
)
async def confirm_showing(
    visit_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateReviewService, Depends(get_review_service)],
) -> ShowingConfirmationResponse:
    visit, report = await service.confirm_showing(context, visit_id)
    return ShowingConfirmationResponse(
        visit_id=visit.id,
        report_id=report.id,
        visit_status=visit.status,
        report_status=report.status,
    )
