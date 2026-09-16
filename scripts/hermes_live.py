#!/usr/bin/env python3
"""Hermes-friendly wrapper around `airpath live`.

Hermes Agent (Nous Research) is a separate self-hosted agent with cron /
no-agent script jobs. It is NOT installed in this package and is not
required. If you deploy Hermes later, schedule this script (or the same
CLI) as a no-agent cron job, for example:

  hermes cron create "every 5m" --no-agent --script hermes_live.py \\
    --name airpath-ek001

This file only forwards to the stdlib airpath live extractor.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airpath.cli import main  # noqa: E402


def _default_argv(argv: list[str]) -> list[str]:
    """If the user passes no subcommand, default to `live` with free sources."""
    if not argv or argv[0].startswith("-"):
        return ["live", *argv]
    return argv


if __name__ == "__main__":
    raise SystemExit(main(_default_argv(sys.argv[1:])))
