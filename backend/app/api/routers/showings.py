import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_context, get_showing_service
from app.schemas import (
    MediaDownloadResponse,
    MediaPresignRequest,
    MediaPresignResponse,
    ShowingCreate,
    ShowingDetailResponse,
    ShowingFinishResponse,
    ShowingListResponse,
    ShowingResponse,
)
from app.schemas.contacts import ContactResponse
from app.schemas.properties import PropertyResponse
from app.schemas.showings import (
    MediaResponse,
    ObservationResponse,
    ReportResponse,
    TranscriptSegmentResponse,
    ZoneResponse,
)
from app.services import CurrentContext, RealEstateShowingService
from app.services.showings import ShowingDetail, ShowingRecord

router = APIRouter(prefix="/showings", tags=["showings"])


def showing_response(record: ShowingRecord) -> ShowingResponse:
    visit = record.visit
    return ShowingResponse(
        id=visit.id,
        status=visit.status,
        processing_status=visit.processing_status,
        processing_failed_step=visit.processing_failed_step,
        processing_error=visit.processing_error,
        started_at=visit.started_at,
        ended_at=visit.ended_at,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
        property=PropertyResponse.from_subject(record.subject),
        contact=(
            ContactResponse.model_validate(record.contact) if record.contact else None
        ),
    )


def showing_detail_response(detail: ShowingDetail) -> ShowingDetailResponse:
    summary = showing_response(detail.record)
    return ShowingDetailResponse(
        **summary.model_dump(),
        media=[MediaResponse.from_media(item) for item in detail.media],
        zones=[ZoneResponse.from_zone(item) for item in detail.zones],
        observations=[
            ObservationResponse.from_observation(item) for item in detail.observations
        ],
        transcript=[
            TranscriptSegmentResponse.from_segment(item) for item in detail.transcript
        ],
        report=ReportResponse.from_report(detail.report) if detail.report else None,
    )


@router.post("", response_model=ShowingResponse, status_code=status.HTTP_201_CREATED)
async def create_showing(
    payload: ShowingCreate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> ShowingResponse:
    return showing_response(await service.create_showing(context, payload))


@router.get("", response_model=ShowingListResponse)
async def list_showings(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
    contact_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    showing_status: Annotated[
        Literal["draft", "confirmed", "sent_to_client"] | None,
        Query(alias="status"),
    ] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    query: Annotated[str | None, Query(alias="q", max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ShowingListResponse:
    page = await service.list_showings(
        context,
        contact_id=contact_id,
        subject_id=subject_id,
        status=showing_status,
        date_from=date_from,
        date_to=date_to,
        query=query,
        cursor=cursor,
        limit=limit,
    )
    return ShowingListResponse(
        items=[showing_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{visit_id}", response_model=ShowingDetailResponse)
async def get_showing(
    visit_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> ShowingDetailResponse:
    return showing_detail_response(await service.get_showing(context, visit_id))


@router.post("/{visit_id}/media/presign", response_model=MediaPresignResponse)
async def presign_media(
    visit_id: uuid.UUID,
    payload: MediaPresignRequest,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> MediaPresignResponse:
    result = await service.presign_media(context, visit_id, payload)
    return MediaPresignResponse(
        media_id=result.media.id,
        upload_url=result.upload_url,
        headers={"Content-Type": result.media.content_type},
        expires_in=result.expires_in,
        max_size_bytes=result.max_size_bytes,
    )


@router.post("/{visit_id}/media/{media_id}/complete", response_model=MediaResponse)
async def complete_media(
    visit_id: uuid.UUID,
    media_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> MediaResponse:
    return MediaResponse.from_media(
        await service.complete_media(context, visit_id, media_id)
    )


@router.get(
    "/{visit_id}/media/{media_id}/download", response_model=MediaDownloadResponse
)
async def download_media(
    visit_id: uuid.UUID,
    media_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> MediaDownloadResponse:
    result = await service.get_media_download(context, visit_id, media_id)
    return MediaDownloadResponse(**result.__dict__)


@router.post("/{visit_id}/finish", response_model=ShowingFinishResponse)
async def finish_showing(
    visit_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> ShowingFinishResponse:
    return ShowingFinishResponse.from_visit(
        await service.finish_showing(context, visit_id)
    )


@router.post("/{visit_id}/reprocess", response_model=ShowingFinishResponse)
async def reprocess_showing(
    visit_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateShowingService, Depends(get_showing_service)],
) -> ShowingFinishResponse:
    return ShowingFinishResponse.from_visit(
        await service.reprocess_showing(context, visit_id)
    )
