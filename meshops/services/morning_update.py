"""Build and schedule one concise Morning Update per local day."""

from datetime import datetime, time, timedelta
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from meshops.services.time_trust import SystemTimeTrust


log = logging.getLogger(__name__)


class MorningUpdateService:
    """Decide when a Morning Update is due without performing radio transport."""

    def __init__(
        self,
        bot,
        settings: dict,
        timezone: str,
        now_provider=datetime.now,
        time_is_trusted=None,
    ):
        self.bot = bot
        self.settings = settings
        self.timezone = ZoneInfo(timezone)
        self.now_provider = now_provider
        self.time_is_trusted = time_is_trusted or SystemTimeTrust().is_trusted
        self.state_path = Path(settings["state_file"])

    def due_report(self, context) -> str | None:
        """Return the report once in its scheduled window, or ``None``."""

        if not self.settings.get("enabled", False):
            return None
        if not self.time_is_trusted():
            return None

        now = self._local_now()
        scheduled_time = self._scheduled_time()
        grace = timedelta(minutes=self.settings.get("grace_minutes", 120))
        scheduled_at = datetime.combine(now.date(), scheduled_time, tzinfo=self.timezone)

        if not scheduled_at <= now <= scheduled_at + grace:
            return None
        if now.date().isoformat() in self._sent_dates():
            return None

        try:
            resolved_context = context() if callable(context) else context
        except Exception:
            log.exception("Unable to collect Morning Update data; sending local fallback")
            resolved_context = {}

        return self.build_report(resolved_context, deduplicate_alerts=True)

    def build_report(self, context: dict, *, deduplicate_alerts: bool = False) -> str:
        """Build a report for sending or previewing from current application data."""

        alert_arguments = {
            "weather": context.get("weather"),
            "aqi": context.get("aqi"),
            "statuses": context.get("statuses", []),
            "camp_node": context.get("home_node"),
        }
        alerts = (
            self.bot.check_alerts(**alert_arguments)
            if deduplicate_alerts
            else self.bot.current_alerts(**alert_arguments)
        )
        camp_status = "Online" if context.get("home_node") else "Unavailable"

        return self.bot.build_morning_report(
            weather=context.get("weather"),
            aqi=context.get("aqi"),
            sun=context.get("sun"),
            events=self.settings.get("events", []),
            node_count=context.get("node_count", 0),
            team_count=len(context.get("team", [])),
            camp_status=camp_status,
            statuses=context.get("statuses", []),
            alerts=alerts,
        )

    def mark_sent(self) -> None:
        """Persist today's successful send after transport confirms delivery."""

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        sent_on = self._sent_dates()
        today = self._local_now().date().isoformat()
        if today not in sent_on:
            sent_on.append(today)
        sent_on = sorted(sent_on)[-32:]
        payload = {"last_sent_on": today, "sent_on": sent_on}
        temporary_path = self.state_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload), encoding="utf-8")
        temporary_path.replace(self.state_path)

    def _local_now(self) -> datetime:
        now = self.now_provider()
        if now.tzinfo is None:
            return now.replace(tzinfo=self.timezone)
        return now.astimezone(self.timezone)

    def _scheduled_time(self) -> time:
        return time.fromisoformat(self.settings["time"])

    def _sent_dates(self) -> list[str]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, OSError):
            return []

        sent_on = payload.get("sent_on", [])
        if not isinstance(sent_on, list):
            sent_on = []
        last_sent_on = payload.get("last_sent_on")
        if isinstance(last_sent_on, str) and last_sent_on not in sent_on:
            sent_on.append(last_sent_on)
        return [value for value in sent_on if isinstance(value, str)]
