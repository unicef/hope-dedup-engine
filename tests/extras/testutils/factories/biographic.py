import factory

from hope_dedup_engine.apps.biographic.models import (
    BiographicFinding,
    BiographicGroup,
    BiographicJob,
    BiographicRecord,
    BiographicSet,
)

from .base import AutoRegisterModelFactory


class BiographicGroupFactory(AutoRegisterModelFactory):
    business_area = factory.Sequence(lambda n: f"ba{n}")
    program_code = factory.Sequence(lambda n: f"p{n:03d}")
    settings = factory.LazyFunction(dict)

    class Meta:
        model = BiographicGroup


class BiographicSetFactory(AutoRegisterModelFactory):
    group = factory.SubFactory(BiographicGroupFactory)
    state = BiographicSet.State.PENDING

    class Meta:
        model = BiographicSet


class BiographicJobFactory(AutoRegisterModelFactory):
    dataset = factory.SubFactory(BiographicSetFactory, state=BiographicSet.State.INDEXING)
    config_overrides = factory.LazyFunction(dict)

    class Meta:
        model = BiographicJob


class BiographicRecordFactory(AutoRegisterModelFactory):
    dataset = factory.SubFactory(BiographicSetFactory)
    reference_pk = factory.Sequence(lambda n: f"cw-{n}")
    payload = factory.LazyFunction(
        lambda: {
            "full_name": "Maria Gonzalez",
            "given_name": "Maria",
            "family_name": "Gonzalez",
            "birth_date": "1990-05-15",
            "sex": "FEMALE",
        }
    )
    full_name = factory.LazyAttribute(lambda o: o.payload.get("full_name") or "")

    class Meta:
        model = BiographicRecord


class BiographicFindingFactory(AutoRegisterModelFactory):
    record = factory.SubFactory(BiographicRecordFactory)
    dataset = factory.SelfAttribute("record.dataset")
    matched_reference_pk = factory.Sequence(lambda n: f"match-{n}")
    matched_full_name = "Maria Gonzales"
    matched_birth_date = "1990-05-15"
    score = 14.0
    proximity_to_score = 8.0
    scope = BiographicFinding.Scope.POPULATION
    config = factory.LazyFunction(lambda: {"duplicate_score": 6.0})

    class Meta:
        model = BiographicFinding
