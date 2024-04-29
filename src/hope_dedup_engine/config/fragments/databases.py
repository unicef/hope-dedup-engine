from hope_dedup_engine.config import env

RO_CONN = dict(**env.db("DATABASE_HOPE_URL")).copy()
RO_CONN.update(
    **{
        "OPTIONS": {"options": "-c default_transaction_read_only=on"},
    }
)
RO_CONN.update(
    {
        "OPTIONS": {"options": "-c default_transaction_read_only=on"},
        "TEST": {
            "READ_ONLY": True,  # Do not manage this database during tests
        },
    }
)
DATABASES = {
    "default": env.db("DATABASE_URL"),
    "hope_ro": RO_CONN,
}

DATABASE_ROUTERS = ("hope_dedup_engine.apps.core.dbrouters.DbRouter",)
DATABASE_APPS_MAPPING: dict[str, str] = {
    "hope": "hope",
}
