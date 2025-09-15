import os
import shutil
from pathlib import Path

import numpy as np
from constance import config as constance_cfg
from deepface import DeepFace
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Downloads and caches pre-trained models for DeepFace if they are missing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force deletion of existing models before syncing to ensure a clean state.",
        )

    def handle(self, *args, **options):
        force_sync = options["force"]
        deepface_home = os.getenv("DEEPFACE_HOME")
        if not deepface_home:
            self.stderr.write(self.style.ERROR("DEEPFACE_HOME environment variable is not set."))
            return

        if force_sync:
            deepface_dir = Path(deepface_home) / ".deepface"
            if deepface_dir.exists():
                self.stdout.write(f"Removing existing DeepFace model directory due to --force flag: {deepface_dir}")
                try:
                    shutil.rmtree(deepface_dir)
                    self.stdout.write(self.style.SUCCESS("Successfully removed existing models."))
                except OSError as e:
                    self.stderr.write(self.style.ERROR(f"Error removing directory {deepface_dir}: {e}"))
                    return

        self.stdout.write("Ensuring pre-trained models for DeepFace are available...")

        models_to_sync = [constance_cfg.FACE_RECOGNITION_MODEL]
        detectors_to_sync = [constance_cfg.FACE_DETECTOR_BACKEND]

        for model_name in models_to_sync:
            self.stdout.write(f"  - Checking model: {model_name}")
            try:
                DeepFace.build_model(model_name)
                self.stdout.write(self.style.SUCCESS(f"    '{model_name}' model is available."))
            except (ValueError, RuntimeError) as e:
                self.stderr.write(self.style.ERROR(f"    Failed to load model '{model_name}': {e}"))

        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)

        for backend in detectors_to_sync:
            self.stdout.write(f"  - Checking detector backend: {backend}")
            try:
                DeepFace.extract_faces(img_path=dummy_image, detector_backend=backend, enforce_detection=False)
                self.stdout.write(self.style.SUCCESS(f"    '{backend}' detector is available."))
            except (ValueError, RuntimeError) as e:
                self.stderr.write(self.style.ERROR(f"    Failed to load detector '{backend}': {e}"))

        self.stdout.write(self.style.SUCCESS("Finished model check."))
