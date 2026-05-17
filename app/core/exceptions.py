"""app/core/exceptions.py — custom application exceptions."""


class DataSourceError(RuntimeError):
    """Raised when the upstream data source is unreachable."""


class ETLError(RuntimeError):
    """Raised when a transformation step fails."""


class RecordNotFoundError(LookupError):
    """Raised when a requested record ID does not exist."""
