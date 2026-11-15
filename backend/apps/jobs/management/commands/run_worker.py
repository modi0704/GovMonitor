"""Background worker (MASTERPLAN 6.7): the job loop, the scheduler pass and the heartbeat."""

import logging
import signal
import socket
import time

from django.core.management.base import BaseCommand

from apps.jobs import heartbeat, worker

log = logging.getLogger("worker")


class Command(BaseCommand):
    help = "Run the background worker loop."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=15.0, help="Seconds between loop passes")
        parser.add_argument("--once", action="store_true", help="Run one pass and exit (tests, cron)")

    def handle(self, *args, interval: float, once: bool, **options):
        self._stop = False

        def _stop(signum, frame):
            log.info("worker: received signal %s, stopping", signum)
            self._stop = True

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        host = socket.gethostname()
        requeued = worker.requeue_stale()
        log.info("worker: started on %s (%s stale job(s) re-queued)", host, requeued)
        while not self._stop:
            heartbeat.beat(host=host)
            try:
                worker.schedule_pass()
                ran = worker.run_pending()
                if ran:
                    log.info("worker: ran %s job(s)", ran)
            except Exception:  # noqa: BLE001 — the loop must survive one bad pass
                log.exception("worker: pass failed")
            if once:
                break
            slept = 0.0
            while slept < interval and not self._stop:
                time.sleep(0.5)
                slept += 0.5
        log.info("worker: stopped")
