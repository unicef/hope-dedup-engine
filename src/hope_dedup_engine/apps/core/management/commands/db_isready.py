import sys
import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, connections


class Command(BaseCommand):
    args = ""
    help = "Help text here...."
    requires_migrations_checks = False

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            "--sleep",
            default=1,
            action="store",
            type=int,
            help="sleep time between attempt",
        )
        parser.add_argument(
            "--wait",
            default=False,
            action="store_true",
            help="wait until database is available",
        )
        parser.add_argument(
            "--debug",
            default=False,
            action="store_true",
            help="debug mode. WARNING can dump passwords",
        )
        parser.add_argument(
            "--timeout",
            default=30,
            type=int,
            help="timeout in sec before OperationalError",
        )

        parser.add_argument(
            "--connection",
            default="default",
            help="timeout in sec before OperationalError",
        )

    def _get_cursor(self, conn):
        conn.cursor()
        return conn

    def handle(self, *args, **options):
        conn = connections[options["connection"]]
        elapsed = 0
        retcode = 1
        try:
            self.stdout.write(f"Checking connnection {options['connection']}...")

            while True:
                try:
                    conn = self._get_cursor(conn)
                except OperationalError as e:
                    if options["wait"] and elapsed < options["timeout"]:
                        self.stdout.write("." * elapsed, ending="\r")
                        self.stdout.flush()
                        time.sleep(options["sleep"])
                        elapsed += 1
                    else:
                        self.stderr.write(
                            f"\nDatabase on {conn.settings_dict['HOST']}:{conn.settings_dict['PORT']} "
                            f"is not available after {elapsed} secs"
                        )
                        if options["debug"]:
                            self.stderr.write(f"Error is: {e}")
                        retcode = 1
                        break
                else:
                    self.stdout.write(f"Connection {options['connection']} successful")
                    retcode = 0
                    break
        except KeyboardInterrupt:  # pragma: no-cover
            self.stdout.write("Interrupted")
        sys.exit(retcode)
