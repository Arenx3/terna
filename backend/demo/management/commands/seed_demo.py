from django.core.management.base import BaseCommand

from config.env import env
from demo.seed import DEFAULT_PASSWORD, seed


class Command(BaseCommand):
    help = "Create the demo companies, team and jobs. Safe to run again: only adds what is missing."

    def handle(self, *args, **options):
        report = seed(password=env("DEMO_PASSWORD", DEFAULT_PASSWORD))
        for line in report:
            self.stdout.write(line)
