"""Domain errors raised below the HTTP layer. The views map them to 409."""


class LifecycleConflictError(Exception):
    """The requested lifecycle step is not possible from the current state."""


class IndexMissingError(Exception):
    """The program's Elasticsearch index is gone, and a run needs what was in it.

    Either the program has approved sets, or the set to search was indexed earlier.
    Searching would find nothing, so the run stops until the index is rebuilt from
    the records kept in Postgres.
    """


class InvalidTransitionError(LifecycleConflictError):
    """A set is not in a state the requested transition allows."""
