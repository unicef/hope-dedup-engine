import factory

from hope_dedup_engine.apps.biographic.models import (
    BiographicFinding,
    BiographicGroup,
    BiographicRecord,
    BiographicSet,
)

from .base import AutoRegisterModelFactory


class BiographicGroupFactory(AutoRegisterModelFactory):
    business_area = factory.Sequence(lambda n: f"ba-{n}")
    program_id = factory.Sequence(lambda n: f"program-{n}")
    name = None

    class Meta:
        model = BiographicGroup


class BiographicSetFactory(AutoRegisterModelFactory):
    group = factory.SubFactory(BiographicGroupFactory)
    state = BiographicSet.State.PENDING

    class Meta:
        model = BiographicSet


class BiographicRecordFactory(AutoRegisterModelFactory):
    dataset = factory.SubFactory(BiographicSetFactory)
    reference_pk = factory.Sequence(lambda n: f"cw-{n}")
    payload = factory.LazyFunction(
        lambda: {
            "full_name": "Maria Gonzalez",
            "given_name": "Maria",
            "family_name": "Gonzalez",
            "birth_date": "1990-05-15",
        }
    )

    class Meta:
        model = BiographicRecord


class BiographicFindingFactory(AutoRegisterModelFactory):
    record = factory.SubFactory(BiographicRecordFactory)
    matched_reference_pk = factory.Sequence(lambda n: f"match-{n}")
    score = 8.2
    proximity_to_score = 2.2
    status_code = BiographicFinding.StatusCode.DUPLICATE
    scope = BiographicFinding.Scope.POPULATION
    config = factory.LazyFunction(lambda: {"duplicate_score": 6.0})

    class Meta:
        model = BiographicFinding
