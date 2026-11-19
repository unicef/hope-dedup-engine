"""Domain errors raised below the HTTP layer; views map lifecycle conflicts to 409."""


class LifecycleConflictError(Exception):
    """The requested lifecycle step is not possible from the current state."""


class IndexMissingError(Exception):
    """The program's Elasticsearch index is gone, and the operation needs it restored.

    Either the program has approved sets, or the set to search was indexed earlier.
    Searching would find nothing, so the run stops until the index is rebuilt from
    the records kept in Postgres.

    A single-set rebuild also refuses a missing index, because the whole group
    must be rebuilt first.
    """


class IndexRebuildRequiredError(Exception):
    """The group's index requires a complete rebuild before it can be used."""


class InvalidTransitionError(LifecycleConflictError):
    """A set is not in a state the requested transition allows."""


class GroupDeletedError(LifecycleConflictError):
    """The program was deleted, so nothing may be processed or rebuilt for it."""

    message = "Biographic deduplication was deleted for this program."


class GroupDeleteError(LifecycleConflictError):
    """The program cannot be deleted while a task is running for it."""

    message = "Cannot delete biographic deduplication while processing is running."
