"""Qt adapter for the manual planner check; HTTP lives in planner_client."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from PySide6.QtCore import QThread, Signal

# Re-export existing functions so current imports continue to work.
from .planner_client import (
    get_schedule, propose_event, propose_deadline, confirm_event_proposal,
    cancel_event_proposal, get_availability, get_reminders,
)


class PlannerReader(QThread):
    events_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, token, parent=None):
        super().__init__(parent)
        self._token = token

    def run(self):
        try:
            timezone = ZoneInfo("America/Los_Angeles")
            today = datetime.now(timezone).date()

            if self.isInterruptionRequested():
                return

            schedule = get_schedule(
                token=self._token,
                start=today.isoformat(),
                end=(today + timedelta(days=1)).isoformat(),
                timezone=timezone.key,
            )

            if not self.isInterruptionRequested():
                self.events_ready.emit(schedule)

        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(
                    f"{type(error).__name__}: {error}"
                )

        finally:
            self._token = None
