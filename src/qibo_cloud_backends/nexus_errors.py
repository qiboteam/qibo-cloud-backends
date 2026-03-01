"""Custom exceptions raised by the Nexus backend."""

from __future__ import annotations


class NexusBackendError(RuntimeError):
    """Base class for qibo-nexus backend errors."""


class NexusAuthError(NexusBackendError):
    """Raised when Nexus authentication/context setup fails."""


class NexusResultMappingError(NexusBackendError):
    """Raised when Nexus result payload cannot be converted to Qibo results."""


class UnsupportedExecutionError(NexusBackendError):
    """Raised when user asks for unsupported execution modes."""
