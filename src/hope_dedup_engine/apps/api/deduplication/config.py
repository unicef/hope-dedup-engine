from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectionConfig:
    ...
    # dnn_files_source: str = field(
    #     default_factory=lambda: constance_cfg.DNN_FILES_SOURCE
    # )
    # dnn_backend: int = field(default_factory=lambda: constance_cfg.DNN_BACKEND)
    # dnn_target: int = field(default_factory=lambda: constance_cfg.DNN_TARGET)
    # blob_from_image_scale_factor: float = field(
    #     default_factory=lambda: constance_cfg.BLOB_FROM_IMAGE_SCALE_FACTOR
    # )
    # blob_from_image_mean_values: tuple[float, float, float] = field(
    #     default_factory=lambda: tuple(
    #         map(float, constance_cfg.BLOB_FROM_IMAGE_MEAN_VALUES.split(", "))
    #     )
    # )
    # confidence: float = field(
    #     default_factory=lambda: constance_cfg.FACE_DETECTION_CONFIDENCE
    # )
    # nms_threshold: float = field(default_factory=lambda: constance_cfg.NMS_THRESHOLD)


@dataclass
class RecognitionConfig:
    ...
    # num_jitters: int = field(
    #     default_factory=lambda: constance_cfg.FACE_ENCODINGS_NUM_JITTERS
    # )
    # model: Literal["small", "large"] = field(
    #     default_factory=lambda: constance_cfg.FACE_ENCODINGS_MODEL
    # )
    # preprocessors: list[str] = field(default_factory=list)


@dataclass
class DuplicatesConfig:
    ...
    # tolerance: float = field(
    #     default_factory=lambda: constance_cfg.FACE_DISTANCE_THRESHOLD
    # )


@dataclass
class ConfigDefaults:
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    duplicates: DuplicatesConfig = field(default_factory=DuplicatesConfig)

    def apply_config_overrides(
        self, config_settings: dict[str, Any] | None = None
    ) -> None:
        """
        Updates the instance with values from the provided config settings.

        Parameters:
            config_settings (dict | None): Optional dictionary of configuration overrides, structured to match
                sections in ConfigDefaults (e.g., "detection", "recognition", "duplicates"). Only matching attributes
                are updated. No changes are made if `config_settings` is `None` or empty.
        """
        if config_settings:
            for section_name, section_data in config_settings.items():
                dataclass_section = getattr(self, section_name, None)
                if dataclass_section and isinstance(section_data, dict):
                    for k, v in section_data.items():
                        if hasattr(dataclass_section, k):
                            setattr(dataclass_section, k, v)
