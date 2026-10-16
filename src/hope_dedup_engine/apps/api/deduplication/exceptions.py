class GroupError(Exception):
    message: str

    def __init__(self) -> None:
        super().__init__(self.message)


class GroupDeleteError(GroupError):
    message = "Cannot delete group while processing is running."


class GroupSettingsLockedError(GroupError):
    message = "Cannot change settings while a processing job is running."


class GroupSettingsApprovedError(GroupError):
    message = "Cannot change settings while an approved deduplication set exists."
