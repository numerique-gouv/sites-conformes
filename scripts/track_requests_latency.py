#!/usr/bin/env python3
"""Capture per-request latency from Scalingo router logs during a slowness episode.

Streams `scalingo logs --follow`, keeps only `[router]` lines, and reformats
each into tab-separated columns, easy to eyeball live and to sort/analyse later:

    timestamp  status  latency_s  path  user_agent  <remaining fields>

Router log lines look like (key=value, some values double-quoted):

    2026-07-08 15:41:14.188 +0200 CEST [router] method=GET path="/x?a=1"
    host=... request_id=... container=web-1 from="57.141.0.26" protocol=https
    status=200 duration=0.118s bytes=73555 referer="-" user_agent="meta-..."

Usage:
    export SCALINGO_APP=agreste-test
    # stream live during an incident (writes to a file AND prints to screen):
    python scripts/track_requests_latency.py --app agreste-test --region osc-secnum-fr1

    # or feed it existing log text (or a `scalingo logs` pipe):
    scalingo --app agreste-test logs --follow | python scripts/track_requests_latency.py --stdin
    python scripts/track_requests_latency.py --stdin < some_logs.txt

Requires the Scalingo CLI on PATH when not using --stdin.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys

# Matches key=value pairs, where value is either "double quoted" or a bare token.
FIELD_RE = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')

# Columns we surface first, in this order. Everything else is appended as-is.
LEAD_KEYS = ("status", "duration", "path", "user_agent")


def parse_router_line(line: str) -> dict | None:
    """Return {timestamp, fields{}} for a router line, or None if not a router line."""
    marker = line.find("[router]")
    if marker == -1:
        return None
    timestamp = line[:marker].strip()
    fields: dict[str, str] = {}
    for key, quoted, bare in FIELD_RE.findall(line[marker:]):
        fields[key] = quoted if bare == "" else bare
    return {"timestamp": timestamp, "fields": fields}


def format_row(parsed: dict) -> str:
    fields = parsed["fields"]
    latency = fields.get("duration", "-").rstrip("s")  # "0.118s" -> "0.118"
    cols = [
        parsed["timestamp"],
        fields.get("status", "-"),
        latency,
        fields.get("path", "-"),
        fields.get("user_agent", "-"),
    ]
    shown = set(LEAD_KEYS)
    rest = " ".join(f"{k}={v}" for k, v in fields.items() if k not in shown)
    return "\t".join(cols) + (f"\t{rest}" if rest else "")


def line_source(args):
    """Yield raw log lines, either from stdin or from a `scalingo logs` subprocess."""
    if args.stdin:
        yield from sys.stdin
        return
    cmd = ["scalingo"]
    if args.region:
        cmd += ["--region", args.region]
    cmd += ["--app", args.app, "logs", "--follow", "--lines", str(args.lines)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, bufsize=1)
    try:
        yield from proc.stdout
    finally:
        proc.terminate()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--app",
        default=os.environ.get("SCALINGO_APP"),
        help="App name (or set SCALINGO_APP). Not needed with --stdin.",
    )
    parser.add_argument(
        "--region", default=os.environ.get("SCALINGO_REGION"), help="Scalingo region, e.g. osc-secnum-fr1."
    )
    parser.add_argument(
        "--lines", type=int, default=100, help="History lines to pull before following (default: 100)."
    )
    parser.add_argument(
        "--stdin", action="store_true", help="Read log text from stdin instead of running the Scalingo CLI."
    )
    parser.add_argument(
        "--output", default=None, help="File to append rows to " "(default: scalingo_metrics/router_latency_<ts>.tsv)."
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.stdin and not args.app:
        raise SystemExit("Provide --app / SCALINGO_APP, or use --stdin.")

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = pathlib.Path(args.output or f"scalingo_metrics/router_latency_{ts}.tsv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = "# timestamp\tstatus\tlatency_s\tpath\tuser_agent\trest"

    print(f"Writing router latency to {out_path} (Ctrl-C to stop)", file=sys.stderr)
    with out_path.open("a") as fh:
        fh.write(header + "\n")
        fh.flush()
        try:
            for line in line_source(args):
                parsed = parse_router_line(line)
                if parsed is None:
                    continue
                row = format_row(parsed)
                fh.write(row + "\n")
                fh.flush()
                print(row)
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
