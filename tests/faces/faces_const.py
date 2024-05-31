from typing import Dict, Final

FILENAME: Final[str] = "test_file.jpg"
FILENAMES: Final[list[str]] = ["test_file.jpg", "test_file2.jpg"]
DEPLOY_PROTO_SHAPE: Final[Dict[str, int]] = {"batch_size": 1, "channels": 3, "height": 300, "width": 300}
