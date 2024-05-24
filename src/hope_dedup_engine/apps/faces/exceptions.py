class NoFaceRegionsDetectedException(Exception):
    def __init__(self, message="No face regions detected"):
        self.message = message
        super().__init__(self.message)
