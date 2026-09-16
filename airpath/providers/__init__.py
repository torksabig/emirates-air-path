"""Weather-archive adapters for Phase 1/2 path matching."""

from .catalog import PROVIDERS, get_provider, list_providers
from .http import AuthRequired, PlannedRequest
from .match import MatchResult, attach_observations, match_flight

__all__ = [
    "PROVIDERS",
    "AuthRequired",
    "MatchResult",
    "PlannedRequest",
    "attach_observations",
    "get_provider",
    "list_providers",
    "match_flight",
]
