from typing import NamedTuple

from app.models import Membership, User, Workspace


class CurrentContext(NamedTuple):
    user: User
    workspace: Workspace
    membership: Membership
