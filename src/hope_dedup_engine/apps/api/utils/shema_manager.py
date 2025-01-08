class SchemaManager:  # pragma: no cover
    """
    Manages loading, validating, and saving the JSON schema file.

    Attributes:
        schema_path (Path): Path to the JSON schema file.

    Methods:
        get_or_create() -> dict:
        save(schema: dict) -> None:
    """

    ...
    # schema_path = Path(settings.CONFIG_SETTINGS_SCHEMA_FILE)

    # @classmethod
    # def get_or_create(cls) -> dict:
    #     """
    #     Attempts to load and validate the schema from the JSON schema file.

    #     Returns:
    #         dict: The loaded JSON schema as a dictionary. If the file is not found, returns
    #         an empty dictionary as a fallback.

    #     Raises:
    #         ValidationError: If the schema file exists but contains invalid JSON
    #         or fails JSON Schema validation.
    #     """
    #     try:
    #         schema = json.loads(cls.schema_path.read_text())
    #         Draft202012Validator.check_schema(schema)
    #         return schema
    #     except FileNotFoundError:
    #         logger.warning("Schema file not found.")
    #         return {}
    #     except (json.JSONDecodeError, exceptions.SchemaError) as e:
    #         logger.error(f"Failed to load schema: {e}")
    #         raise ValidationError("Failed to load the schema file.") from e

    # @classmethod
    # def save(cls, schema: dict) -> None:
    #     """
    #     Validates and writes the provided schema dictionary to the schema file.

    #     Args:
    #         schema (dict): The JSON schema to be saved, provided as a dictionary.

    #     Raises:
    #         ValidationError: If the schema does not meet JSON Schema standards or if
    #         there is an IOError when writing to the file.
    #     """
    #     try:
    #         Draft202012Validator.check_schema(schema)
    #         cls.schema_path.write_text(json.dumps(schema, indent=4))
    #         logger.info(f"Schema saved to {cls.schema_path}")
    #     except exceptions.SchemaError as e:
    #         raise ValidationError("Invalid schema format.") from e
    #     except IOError as e:
    #         logger.error(f"Failed to save schema: {e}")
    #         raise ValidationError("Failed to save the schema file.") from e
