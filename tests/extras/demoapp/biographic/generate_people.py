#!/usr/bin/env python3
"""Generate fake people for the biographic demo. Standard library only.

Writes three files to the output directory:

* population.json - households that are processed and approved first, the
  program's existing population
* new_registration.json - a later registration: new households plus planted
  cases, each a known variation of a population person
* expected.json - what each planted case should produce, read by check_expected

Every filler person has a unique given/family name pair, and names too close to
each other to be told apart by a fuzzy match are dropped, so fillers never match
each other. Every reported pair should therefore be a planted one.
"""

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# No two names here share a Double Metaphone code, checked with Elasticsearch's
# `_analyze`: a sound-alike pair would match by phonetics despite the spelling.
# fmt: off
MALE = [
    "Ahmad", "Bashir", "Daoud", "Farhad", "Ghulam", "Habib", "Idris", "Jawed", "Khalil", "Latif",
    "Mansoor", "Nasir", "Qadir", "Rashid", "Sabir", "Tawfiq", "Wahid", "Yaqub", "Akbar", "Hekmat",
    "Ismail", "Najib", "Parwiz", "Shafiq", "Waris", "Zalmai", "Elyas", "Fawad", "Haroon", "Murad",
    "Obaid", "Sohail", "Tamim", "Yunus", "Zahir",
]

FEMALE = [
    "Bibi", "Fatima", "Hasina", "Jamila", "Khadija", "Malalai", "Nargis", "Parwana", "Roya", "Sadia",
    "Shabnam", "Tahmina", "Wazhma", "Yalda", "Zarghona", "Freshta", "Homa", "Lida", "Mursal", "Nazia",
    "Palwasha", "Rabia", "Sima", "Zainab", "Marzia", "Mina",
]

FAMILY = [
    "Ahmadi", "Amiri", "Azizi", "Barakzai", "Durrani", "Faizi", "Ghafoori", "Habibi", "Hashimi",
    "Jalali", "Kakar", "Khogyani", "Mohmand", "Nazari", "Popal", "Qaderi", "Rasuli", "Safi", "Samadi",
    "Shinwari", "Stanekzai", "Tajik", "Wardak", "Zazai", "Sadat", "Mangal", "Hotak", "Lodin", "Niazi",
    "Osmani", "Rahmani", "Sharifi", "Tokhi", "Yaftali", "Zaheer", "Mirzad", "Nuristani", "Paktiawal",
    "Andar", "Baheer", "Daudzai", "Ghani", "Hakimi", "Ibrahimi", "Jabarkhel", "Kohistani", "Logari",
    "Noorzai", "Panjshiri", "Qarizada", "Rezai", "Sahak", "Taniwal", "Zadran",
]
# fmt: on

ANCHORS = [
    {
        "reference_pk": "POP-AMINA",
        "given_name": "Amina",
        "family_name": "Yusufi",
        "sex": "FEMALE",
        "birth_date": "1990-04-12",
        "phone_no": "+93700111222",
        "relationship": "HEAD",
    },
    {
        "reference_pk": "POP-MARIAM",
        "given_name": "Mariam",
        "family_name": "Haidari",
        "sex": "FEMALE",
        "birth_date": "1987-09-30",
        "phone_no": "+93700222333",
        "relationship": "HEAD",
    },
    {
        "reference_pk": "POP-RAHIM",
        "given_name": "Rahim",
        "family_name": "Sultani",
        "sex": "MALE",
        "birth_date": "1979-01-05",
        "phone_no": "+93700333444",
        "relationship": "HEAD",
    },
    {
        "reference_pk": "POP-JOHN",
        "given_name": "John",
        "family_name": "Brown",
        "sex": "MALE",
        "birth_date": "1983-06-21",
        "phone_no": "+93700444555",
        "relationship": "HEAD",
    },
    {
        "reference_pk": "POP-HAMID",
        "given_name": "Hamid",
        "family_name": "Noori",
        "sex": "MALE",
        "birth_date": "1975-11-02",
        "phone_no": "+93700555666",
        "relationship": "HEAD",
    },
    {
        "reference_pk": "POP-AHMAD",
        "given_name": "Ahmad",
        "family_name": "Rahimi",
        "sex": "MALE",
        "birth_date": "1985-03-17",
        "phone_no": "+93700666777",
        "relationship": "HEAD",
    },
    {
        "reference_pk": "POP-NADIA",
        "given_name": "Nadia",
        "family_name": "Karimi",
        "sex": "FEMALE",
        "birth_date": "1992-08-08",
        "phone_no": "+93700777888",
        "relationship": "HEAD",
    },
]
ANCHOR_FAMILIES = {"Yusufi", "Haidari", "Sultani", "Brown", "Noori", "Rahimi", "Karimi", "Ahmadzai"}


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def allowed_typos(a: str, b: str) -> int:
    """The edits Elasticsearch's `AUTO:3,6` fuzziness allows, for the longer of the two."""
    length = max(len(a), len(b))
    return 0 if length < 3 else 1 if length < 6 else 2


def distinct(names: list[str], reserved: list[str]) -> list[str]:
    """Drop every name a fuzzy match could confuse with a reserved or an earlier name."""
    kept: list[str] = []
    for name in names:
        lowered = name.lower()
        if all(edit_distance(lowered, other.lower()) > allowed_typos(lowered, other) for other in reserved + kept):
            kept.append(name)
    return kept


def person(reference_pk: str, payload: dict) -> dict:
    payload = {"middle_name": None, "phone_no_alternative": None, **payload}
    if "full_name" not in payload:
        payload["full_name"] = f"{payload['given_name']} {payload['family_name']}"
    return {"reference_pk": reference_pk, "payload": payload}


class Generator:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        anchor_given = [a["given_name"] for a in ANCHORS] + ["Johnny", "Maryam", "Rhaim", "Zahra", "Laila"]
        self.male = distinct(MALE, anchor_given)
        self.female = distinct(FEMALE, anchor_given + self.male)
        self.families = [f for f in distinct(FAMILY, sorted(ANCHOR_FAMILIES)) if f not in ANCHOR_FAMILIES]
        self.used_names: set[tuple[str, str]] = {(a["given_name"], a["family_name"]) for a in ANCHORS}
        self.used_phones: set[str] = {a["phone_no"] for a in ANCHORS}

    def phone(self) -> str:
        while True:
            number = f"+9379{self.rng.randrange(10**7):07d}"
            if number not in self.used_phones:
                self.used_phones.add(number)
                return number

    def birth_date(self, first_year: int, last_year: int) -> str:
        start = date(first_year, 1, 1)
        return (start + timedelta(days=self.rng.randrange((date(last_year, 12, 31) - start).days))).isoformat()

    def given_name(self, sex: str, family: str) -> str | None:
        pool = self.male if sex == "MALE" else self.female
        candidates = [g for g in pool if (g, family) not in self.used_names]
        if not candidates:
            return None
        name = self.rng.choice(candidates)
        self.used_names.add((name, family))
        return name

    def household(self, prefix: str, number: int) -> list[dict]:
        family = self.rng.choice(self.families)
        phone = self.phone()
        head_sex = self.rng.choice(("MALE", "FEMALE"))
        members = [("HEAD", head_sex, self.birth_date(1960, 1995), phone)]
        if self.rng.random() < 0.7:
            spouse_sex = "FEMALE" if head_sex == "MALE" else "MALE"
            members.append(("WIFE_HUSBAND", spouse_sex, self.birth_date(1962, 1998), phone))
        members.extend(
            ("SON_DAUGHTER", self.rng.choice(("MALE", "FEMALE")), self.birth_date(2000, 2020), None)
            for _ in range(self.rng.randrange(4))
        )

        people = []
        for index, (relationship, sex, birth_date, member_phone) in enumerate(members, 1):
            given = self.given_name(sex, family)
            if given is None:
                continue
            people.append(
                person(
                    f"{prefix}-{number:04d}-{index}",
                    {
                        "given_name": given,
                        "family_name": family,
                        "sex": sex,
                        "birth_date": birth_date,
                        "phone_no": member_phone,
                        "relationship": relationship,
                    },
                )
            )
        return people

    def households(self, prefix: str, size: int) -> list[dict]:
        people: list[dict] = []
        number = 0
        while len(people) < size:
            number += 1
            people.extend(self.household(prefix, number))
        return people[:size]


def anchor(reference_pk: str) -> dict:
    found = next(a for a in ANCHORS if a["reference_pk"] == reference_pk)
    return {k: v for k, v in found.items() if k != "reference_pk"}


def planted_cases() -> tuple[list[dict], list[dict]]:
    """New records that vary a population person in a known way, and what each should produce."""
    hamid = anchor("POP-HAMID")
    nadia = anchor("POP-NADIA")
    laila = {
        "given_name": "Laila",
        "family_name": "Ahmadzai",
        "sex": "FEMALE",
        "birth_date": "1998-02-14",
        "phone_no": "+93700888999",
        "relationship": "HEAD",
    }
    records = [
        person("NEW-EXACT", anchor("POP-AMINA")),
        person("NEW-SOUNDALIKE", {**anchor("POP-MARIAM"), "given_name": "Maryam"}),
        person("NEW-TYPO", {**anchor("POP-RAHIM"), "given_name": "Rhaim"}),
        person("NEW-NICKNAME", {**anchor("POP-JOHN"), "given_name": "Johnny"}),
        person("NEW-NEWPHONE", {**hamid, "phone_no": "+93700999000", "birth_date": "1975-12-02"}),
        person(
            "NEW-HOUSEHOLD",
            {
                "given_name": "Zahra",
                "family_name": "Noori",
                "sex": "FEMALE",
                "birth_date": "1980-07-19",
                "phone_no": hamid["phone_no"],
                "relationship": "WIFE_HUSBAND",
            },
        ),
        person(
            "NEW-NAMESAKE",
            {
                **anchor("POP-AHMAD"),
                "birth_date": "2001-10-01",
                "phone_no": "+93700123123",
                "relationship": "SON_DAUGHTER",
            },
        ),
        person("NEW-NOGIVEN", {**nadia, "given_name": None, "full_name": "Nadia Karimi"}),
        person("NEW-BATCH-A", laila),
        person("NEW-BATCH-B", laila),
    ]
    expected = [
        {
            "case": "Exact re-registration",
            "reference_pk": "NEW-EXACT",
            "matched_reference_pk": "POP-AMINA",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Same sound, different spelling (Maryam / Mariam)",
            "reference_pk": "NEW-SOUNDALIKE",
            "matched_reference_pk": "POP-MARIAM",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Typo (Rhaim / Rahim)",
            "reference_pk": "NEW-TYPO",
            "matched_reference_pk": "POP-RAHIM",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Nickname from the synonyms file (Johnny / John)",
            "reference_pk": "NEW-NICKNAME",
            "matched_reference_pk": "POP-JOHN",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Same person, new phone and corrected birth date",
            "reference_pk": "NEW-NEWPHONE",
            "matched_reference_pk": "POP-HAMID",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Household member: same family name and phone, different person",
            "reference_pk": "NEW-HOUSEHOLD",
            "matched_reference_pk": "POP-HAMID",
            "scope": "population",
            "duplicate": False,
        },
        {
            "case": "Namesake: same names, different birth date and phone (flagged on names alone)",
            "reference_pk": "NEW-NAMESAKE",
            "matched_reference_pk": "POP-AHMAD",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Given name missing, matched on full name",
            "reference_pk": "NEW-NOGIVEN",
            "matched_reference_pk": "POP-NADIA",
            "scope": "population",
            "duplicate": True,
        },
        {
            "case": "Same person twice in the new registration",
            "reference_pk": "NEW-BATCH-A",
            "matched_reference_pk": "NEW-BATCH-B",
            "scope": "batch",
            "duplicate": True,
        },
        {
            "case": "Same person twice in the new registration (other direction)",
            "reference_pk": "NEW-BATCH-B",
            "matched_reference_pk": "NEW-BATCH-A",
            "scope": "batch",
            "duplicate": True,
        },
    ]
    return records, expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="directory to write the JSON files to")
    parser.add_argument("--population", type=int, default=400, help="approved population size")
    parser.add_argument("--new", type=int, default=50, help="new, unrelated people in the new registration")
    parser.add_argument("--seed", type=int, default=328)
    args = parser.parse_args()

    generator = Generator(args.seed)
    population = [person(a["reference_pk"], anchor(a["reference_pk"])) for a in ANCHORS]
    population += generator.households("POP", args.population - len(population))
    planted, expected = planted_cases()
    new_registration = generator.households("NEW", args.new) + planted
    generator.rng.shuffle(new_registration)

    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ("population.json", population),
        ("new_registration.json", new_registration),
        ("expected.json", expected),
    ):
        (args.output / name).write_text(json.dumps(content, indent=2) + "\n")
    sys.stderr.write(
        f"{len(population)} population people, {len(new_registration)} new ({len(planted)} planted) in {args.output}\n"
    )


if __name__ == "__main__":
    main()
