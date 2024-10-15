from django.core.management import BaseCommand

from hope_dedup_engine.apps.core.models import ExternalSystem


class Command(BaseCommand):  # pragma: no cover
    help = "Creates external system"

    def add_arguments(self, parser):
        parser.add_argument("name")

    def handle(self, *args, **options):
        system, created = ExternalSystem.objects.get_or_create(
            name=(name := options["name"])
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'"{name}" system created.'))
        else:
            self.stdout.write(self.style.WARNING(f'"{name}" already exists.'))
