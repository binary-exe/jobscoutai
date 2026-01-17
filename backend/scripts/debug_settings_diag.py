# region agent log
"""
Debug-mode diagnostic for Settings parsing behavior.

Run (PowerShell):
  $env:JOBSCOUT_ENABLED_PROVIDERS='remotive,remoteok'
  $env:JOBSCOUT_SCHEDULED_QUERIES='automation engineer,data engineer'
  python backend/scripts/debug_settings_diag.py
"""

import json
import os
import time


LOG_PATH = r"c:\Users\abdul\Desktop\jobscout\.cursor\debug.log"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def main() -> None:
    log("H_SETTINGS_PARSE", __file__, "start", {})
    from backend.app.core.config import Settings  # noqa: PLC0415

    s = Settings()
    log(
        "H_SETTINGS_PARSE",
        __file__,
        "settings_loaded",
        {
            "enabled_providers_type": type(s.enabled_providers).__name__,
            "enabled_providers": s.enabled_providers,
            "scheduled_queries_type": type(s.scheduled_queries).__name__,
            "scheduled_queries": s.scheduled_queries,
            "env_enabled_providers": os.getenv("JOBSCOUT_ENABLED_PROVIDERS"),
            "env_scheduled_queries": os.getenv("JOBSCOUT_SCHEDULED_QUERIES"),
        },
    )
    log("H_SETTINGS_PARSE", __file__, "end", {})


if __name__ == "__main__":
    main()

# endregion

