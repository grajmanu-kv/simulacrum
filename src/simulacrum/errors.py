"""Domain exceptions.

Each one also derives from the closest builtin exception, so callers that catch ``ValueError``,
``KeyError`` etc. keep working while the API layer can map ``SimulacrumError`` subclasses to
precise HTTP statuses.
"""

from __future__ import annotations


class SimulacrumError(Exception):
    """Base class for every error this package raises on purpose."""


class SpecError(SimulacrumError, ValueError):
    """An ecosystem spec is structurally valid JSON but semantically wrong."""


class UnknownComponentError(SimulacrumError, KeyError):
    """A spec or request names a brain/action/system/... that is not registered."""

    def __str__(self) -> str:  # KeyError would repr() the message
        return str(self.args[0]) if self.args else ""


class PluginLoadError(SimulacrumError, ImportError):
    """A plugin could not be imported."""


class PluginSecurityError(SimulacrumError, PermissionError):
    """A plugin path escapes the operator-controlled ecosystems directory."""


class PerturbationError(SimulacrumError, ValueError):
    """An external input is not enabled for this ecosystem, or its parameters are invalid."""


class ReplayMismatch(SimulacrumError, RuntimeError):
    """A replay asked for an LLM response that was never recorded."""


class ProviderConfigError(SimulacrumError, RuntimeError):
    """An LLM provider is unknown or not configured (e.g. missing API key)."""


class ProviderReplyError(SimulacrumError, RuntimeError):
    """A provider answered, but not with usable text (blocked, truncated, empty). Triggers the offline fallback."""


class SessionNotFound(SimulacrumError, LookupError):
    """The session id is unknown or was evicted."""


class EcosystemNotFound(SimulacrumError, LookupError):
    """No ecosystem file with that id exists in the ecosystems directory."""


class LimitExceeded(SimulacrumError, ValueError):
    """A request exceeds a configured operational limit."""
