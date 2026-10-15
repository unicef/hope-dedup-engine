class GroupDeleteError(Exception):
    message = "Cannot delete group while processing is running."


class GroupSettingsLockedError(Exception):
    message = "Cannot change settings while a processing job is running."


class GroupSettingsApprovedError(Exception):
    message = "Cannot change settings while an approved deduplication set exists."
