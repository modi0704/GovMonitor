"""Background worker. Until P7.7 this is a stub loop that only records a heartbeat (P0.5)."""

import logging
import signal
import socket
import time

from django.core.management.base import BaseCommand

from apps.jobs import heartbeat

log = logging.getLogger("worker")


class Command(BaseCommand):
    help = "Run the background worker loop."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=15.0, help="Seconds between loop passes")
        parser.add_argument("--once", action="store_true", help="Run one pass and exit (tests)")

    def handle(self, *args, interval: float, once: bool, **options):
        self._stop = False

        def _stop(signum, frame):
            log.info("worker: received signal %s, stopping", signum)
            self._stop = True

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        host = socket.gethostname()
        log.info("worker: started on %s", host)
        while not self._stop:
            heartbeat.beat(host=host)
            if once:
                break
            slept = 0.0
            while slept < interval and not self._stop:
                time.sleep(0.5)
                slept += 0.5
        log.info("worker: stopped")
