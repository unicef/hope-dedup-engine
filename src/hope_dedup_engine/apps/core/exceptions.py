class DownloaderKeyError(Exception):
    """
    Exception raised when the downloader key does not exist.
    """

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Downloader key '{key}' does not exist.")
