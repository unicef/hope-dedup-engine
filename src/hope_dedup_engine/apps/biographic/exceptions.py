"""Domain errors raised below the HTTP layer. The views map them to 409."""


class LifecycleConflictError(Exception):
    """The requested lifecycle step is not possible from the current state."""


class InvalidTransitionError(LifecycleConflictError):
    """A set is not in a state the requested transition allows."""
