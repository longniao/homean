import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, ReportSend, ReportShareLink, ReportShareView, Visit


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, *entities: object) -> None:
        self.session.add_all(entities)

    async def flush(self) -> None:
        await self.session.flush()

    async def get_visit_report(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> tuple[Visit, Report] | None:
        row = await self.session.execute(
            select(Visit, Report)
            .join(Report, Report.visit_id == Visit.id)
            .where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(1)
        )
        return row.tuples().one_or_none()

    async def get_link(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        link_id: uuid.UUID,
    ) -> ReportShareLink | None:
        return await self.session.scalar(
            select(ReportShareLink)
            .join(Report, Report.id == ReportShareLink.report_id)
            .join(Visit, Visit.id == Report.visit_id)
            .where(
                ReportShareLink.id == link_id,
                ReportShareLink.workspace_id == workspace_id,
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_public_link(
        self, token: str
    ) -> tuple[ReportShareLink, Report] | None:
        row = await self.session.execute(
            select(ReportShareLink, Report)
            .join(Report, Report.id == ReportShareLink.report_id)
            .where(ReportShareLink.token == token)
        )
        return row.tuples().one_or_none()

    async def get_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit | None:
        return await self.session.scalar(
            select(Visit).where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def list_share_links_with_open_counts(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[tuple[ReportShareLink, int]]:
        rows = await self.session.execute(
            select(ReportShareLink, func.count(ReportShareView.id))
            .join(Report, Report.id == ReportShareLink.report_id)
            .join(Visit, Visit.id == Report.visit_id)
            .outerjoin(
                ReportShareView,
                ReportShareView.share_link_id == ReportShareLink.id,
            )
            .where(
                ReportShareLink.workspace_id == workspace_id,
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .group_by(ReportShareLink.id)
            .order_by(ReportShareLink.created_at.desc(), ReportShareLink.id.desc())
        )
        return [(link, int(open_count)) for link, open_count in rows.tuples()]

    async def list_sends(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[ReportSend]:
        rows = await self.session.scalars(
            select(ReportSend)
            .where(
                ReportSend.workspace_id == workspace_id,
                ReportSend.visit_id == visit_id,
            )
            .order_by(ReportSend.created_at.desc(), ReportSend.id.desc())
        )
        return list(rows)
