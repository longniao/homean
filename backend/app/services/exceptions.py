class EmailAlreadyRegisteredError(Exception):
    """The normalized email address is already registered."""


class InvalidCredentialsError(Exception):
    """Authentication credentials are invalid or no longer active."""


class InvalidTokenError(Exception):
    """A JWT is invalid, expired, or has the wrong token type."""


class VerticalNotSeededError(RuntimeError):
    """The required real-estate vertical has not been seeded."""


class ResourceNotFoundError(Exception):
    """A workspace-scoped resource does not exist for the current workspace."""


class ResourceConflictError(Exception):
    """The requested operation conflicts with the current resource state."""


class DomainValidationError(Exception):
    """Input passed schema validation but violates a domain rule."""


class PipelineUnavailableError(RuntimeError):
    """The asynchronous pipeline could not be scheduled."""


class SensitiveReviewRequiredError(DomainValidationError):
    """Sensitive observations must be reviewed before confirmation."""

    def __init__(self, observation_ids: list[str]) -> None:
        super().__init__("sensitive observations require explicit review")
        self.observation_ids = observation_ids


class PropertyRequiredError(DomainValidationError):
    """A showing must be attached to a subject before confirmation."""

    code = "property_required"

    def __init__(self) -> None:
        super().__init__("attach a property before confirming")


class DeliveryUnavailableError(RuntimeError):
    """A report delivery provider failed after the send was recorded."""
