#!/usr/bin/env python3
"""Generate a daily XPRIZE fire detection report.

Usage:
    python -m scripts.daily_report               # Report for today (AEST)
    python -m scripts.daily_report 2026-04-10    # Report for a specific date
    python -m scripts.daily_report --all-dates   # Reports for all competition days so far

This script can be run standalone (outside the FastAPI server) or called
from the server's background scheduler. It queries the SQLite database
directly and writes output to data/reports/.
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure project root is on sys.path when run as script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.export import (
    AEST,
    COMPETITION_END,
    COMPETITION_START,
    save_daily_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def generate_for_date(report_date: date) -> dict:
    """Generate report for a single date."""
    logger.info("Generating daily report for %s", report_date.isoformat())
    result = await save_daily_report(report_date=report_date)
    logger.info(
        "Report complete: %d events, saved to %s",
        result["n_events"],
        result["geojson_path"],
    )
    return result


async def main():
    parser = argparse.ArgumentParser(
        description="Generate XPRIZE daily fire detection report"
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Report date in YYYY-MM-DD format. Defaults to today (AEST).",
    )
    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Generate reports for all competition days up to today.",
    )
    parser.add_argument(
        "--include-closed",
        action="store_true",
        default=True,
        help="Include CLOSED and RETRACTED events (default: True).",
    )

    args = parser.parse_args()

    if args.all_dates:
        from datetime import timedelta

        today_aest = date.today()  # Approximate; precise AEST handled inside
        current = COMPETITION_START
        while current <= min(today_aest, COMPETITION_END):
            await generate_for_date(current)
            current += timedelta(days=1)
    elif args.date:
        try:
            report_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("Invalid date format: %s (expected YYYY-MM-DD)", args.date)
            sys.exit(1)
        await generate_for_date(report_date)
    else:
        # Default: today in AEST
        from datetime import datetime, timezone

        now_aest = datetime.now(timezone.utc).astimezone(AEST)
        await generate_for_date(now_aest.date())


if __name__ == "__main__":
    asyncio.run(main())
