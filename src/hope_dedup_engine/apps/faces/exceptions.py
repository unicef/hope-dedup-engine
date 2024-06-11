class StorageKeyError(Exception):
    """
    Exception raised when the storage key does not exist.
    """

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Storage key '{key}' does not exist.")
