import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDTimestampMixin


class User(UUIDTimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)


class AuthSession(UUIDTimestampMixin, Base):
    """A revocable login. One row per sign-in, so one device can be cut off.

    The refresh token itself is never stored — only its digest — so a leaked
    database backup cannot be replayed as working credentials.
    """

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True, index=True
    )
    # Fixed at login and never moved by a refresh. Continuous use must not be
    # able to keep a session — or a stolen token — alive forever.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(UUIDTimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        Text, nullable=False, default="en", server_default="en"
    )


class WorkspaceBranding(UUIDTimestampMixin, Base):
    __tablename__ = "workspace_branding"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_branding_workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    logo_key: Mapped[str | None] = mapped_column(Text)
    logo_content_type: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    license_no: Mapped[str | None] = mapped_column(Text)
    accent_color: Mapped[str] = mapped_column(
        Text, nullable=False, default="#1F6F5B", server_default="#1F6F5B"
    )


class WorkspaceSubscription(UUIDTimestampMixin, Base):
    __tablename__ = "workspace_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", name="uq_workspace_subscriptions_workspace_id"
        ),
        UniqueConstraint(
            "stripe_subscription_id",
            name="uq_workspace_subscriptions_stripe_subscription_id",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, index=True)
    stripe_event_id: Mapped[str | None] = mapped_column(Text, index=True)
    stripe_event_type: Mapped[str | None] = mapped_column(Text)
    stripe_event_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    plan: Mapped[str] = mapped_column(
        Text, nullable=False, default="trial", server_default="trial"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="trialing", index=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )


class StripeWebhookEvent(UUIDTimestampMixin, Base):
    __tablename__ = "stripe_webhook_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_stripe_webhook_events_event_id"),
    )

    event_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    stripe_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceReportUsage(UUIDTimestampMixin, Base):
    __tablename__ = "workspace_report_usage"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "period_start", name="uq_workspace_report_usage_period"
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(nullable=False, index=True)
    report_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )


class Membership(UUIDTimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "workspace_id", name="uq_memberships_user_workspace"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class Vertical(UUIDTimestampMixin, Base):
    __tablename__ = "verticals"

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    zone_taxonomy: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    observation_schema: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    zone_labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    observation_labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    prompt_templates: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    report_template_id: Mapped[str] = mapped_column(Text, nullable=False)
    report_labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)


class ProfessionalProfile(UUIDTimestampMixin, Base):
    __tablename__ = "professional_profiles"
    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            "vertical_id",
            name="uq_professional_profiles_membership_vertical",
        ),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vertical_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)


class Contact(UUIDTimestampMixin, Base):
    __tablename__ = "contacts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    contact_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class Subject(UUIDTimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_subjects_workspace_id_id",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vertical_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("verticals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class Visit(UUIDTimestampMixin, Base):
    __tablename__ = "visits"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'sent_to_client')",
            name="visit_status",
        ),
        UniqueConstraint(
            "workspace_id",
            "capture_client_id",
            name="uq_visits_workspace_capture_client_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "subject_id"],
            ["subjects.workspace_id", "subjects.id"],
            name="fk_visits_workspace_subject_subjects",
            ondelete="RESTRICT",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        index=True,
    )
    professional_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("professional_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable because dashboard-created visits do not have a mobile capture
    # identity.  Mobile retries use this per-workspace key to make remote visit
    # creation idempotent after an ambiguous response.
    capture_client_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # IANA zone the capture device was in. Reports print the tour date, and a
    # UTC instant renders the wrong day for evening showings west of Greenwich.
    capture_timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft", server_default="draft", index=True
    )
    processing_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="not_started",
        server_default="not_started",
        index=True,
    )
    processing_failed_step: Mapped[str | None] = mapped_column(Text)
    processing_error: Mapped[str | None] = mapped_column(Text)
    processing_run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    consent_ack: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    # Which wording was attested to. A bare boolean cannot answer "what did
    # they actually agree to" once the wording has changed.
    consent_text_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Server receipt time, not the moment the agent tapped. The device clock is
    # client-asserted; this one is not, so it is the defensible timestamp.
    consent_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class Zone(UUIDTimestampMixin, Base):
    __tablename__ = "zones"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_type: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    start_transcript_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        index=True,
    )
    end_transcript_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        index=True,
    )


class RawMedia(UUIDTimestampMixin, Base):
    __tablename__ = "raw_media"
    __table_args__ = (
        UniqueConstraint(
            "visit_id",
            "client_id",
            name="uq_raw_media_visit_client_id",
        ),
    )

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The durable local media UUID lets a mobile retry reconcile an ambiguous
    # initial presign response without relying on the server-generated id.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column("storage_url", Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp_offset_ms: Mapped[float | None] = mapped_column("timestamp_offset", Float)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending", index=True
    )
    upload_url_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    # The room this capture belongs to, and how that was decided. Cleared when
    # reprocessing rebuilds zones, so a stale link never survives a re-run.
    # use_alter breaks the metadata sort cycle this closes: zones reference
    # transcript segments, which reference raw media, which now references
    # zones. The constraint is emitted separately rather than inline.
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "zones.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_raw_media_zone_id_zones",
        ),
        nullable=True,
        index=True,
    )
    zone_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when retention removed the stored object. The row deliberately
    # survives so the evidence chain still shows the media existed.
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VisitMarker(UUIDTimestampMixin, Base):
    """A timestamped, user-created marker in a visit capture."""

    __tablename__ = "visit_markers"
    __table_args__ = (
        UniqueConstraint(
            "visit_id",
            "client_id",
            name="uq_visit_markers_visit_client_id",
        ),
    )

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    marker_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="voice_tag", server_default="voice_tag"
    )
    timestamp_offset_ms: Mapped[float] = mapped_column(Float, nullable=False)


class TranscriptSegment(UUIDTimestampMixin, Base):
    __tablename__ = "transcript_segments"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_media_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("raw_media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text)
    # Anonymous diarized voice index, stable within one recording. Null for
    # segments transcribed before diarization was enabled.
    speaker: Mapped[int | None] = mapped_column(nullable=True)
    timestamp_start: Mapped[float | None] = mapped_column(Float)
    timestamp_end: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)


class Observation(UUIDTimestampMixin, Base):
    __tablename__ = "observations"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="SET NULL"),
        index=True,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_transcript_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        index=True,
    )
    source_media_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("raw_media.id", ondelete="SET NULL"),
        index=True,
    )
    timestamp_start: Mapped[float | None] = mapped_column(Float)
    timestamp_end: Mapped[float | None] = mapped_column(Float)
    ai_model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    review_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending", index=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(UUIDTimestampMixin, Base):
    __tablename__ = "reports"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    rendered_html: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft", server_default="draft", index=True
    )


class ReportRevision(UUIDTimestampMixin, Base):
    """An immutable snapshot of a professional report edit.

    ``previous_content`` and ``new_content`` intentionally remain JSONB: report
    structure is vertical-configured and can evolve without a migration.  The
    workspace, report, visit, and editor are ordinary columns because they are
    the tenancy, relationship, and audit dimensions used for querying.
    """

    __tablename__ = "report_revisions"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "revision_number",
            name="uq_report_revisions_report_revision_number",
        ),
        CheckConstraint(
            "revision_number > 0",
            name="report_revision_number_positive",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edited_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    new_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ReportShareLink(UUIDTimestampMixin, Base):
    __tablename__ = "report_share_links"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    token_lookup_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )


class ReportShareView(UUIDTimestampMixin, Base):
    __tablename__ = "report_share_views"

    share_link_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_share_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_agent_hash: Mapped[str] = mapped_column(Text, nullable=False)
    view_type: Mapped[str] = mapped_column(Text, nullable=False)


class ReportSend(UUIDTimestampMixin, Base):
    __tablename__ = "report_sends"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'outcome_unknown')",
            name="report_send_status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    share_link_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_share_links.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sent_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    to_email: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # Stable application-owned identity for the email.  SMTP providers do not
    # offer portable idempotency, so a safe retry must reuse this value.
    message_id: Mapped[str | None] = mapped_column(Text, unique=True)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PipelineRun(UUIDTimestampMixin, Base):
    __tablename__ = "pipeline_runs"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    step: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    tokens_out: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    duration_ms: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text)
