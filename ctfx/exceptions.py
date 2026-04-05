"""CTFx application exceptions."""


class CTFxError(Exception):
    """Base exception for user-facing CTFx errors."""


class ConfigError(CTFxError):
    """Configuration-related errors."""


class WorkspaceError(CTFxError):
    """Workspace-related errors."""


class PlatformError(CTFxError):
    """Platform integration errors."""
