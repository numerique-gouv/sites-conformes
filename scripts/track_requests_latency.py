#!/usr/bin/env python3
"""Capture per-request latency from Scalingo logs during a slowness episode.

Streams `scalingo logs --follow` and captures BOTH latency sources so they can
be compared side by side in one file:

  * [router] lines  -> `duration` (full time incl. queue wait)
  * [web-N] lines    -> Gunicorn `%(L)s` (view time once a worker picks it up)

Each is reformatted into the same tab-separated columns (a `source` column
distinguishes them), easy to eyeball live and to sort/analyse later:

    timestamp  source  status  latency_s  path  user_agent  rest

To compare the two numbers for a given request, grep the path: the [router]
and [web] rows for the same URL show total-vs-view time (their gap = queue wait).

Router lines are key=value; web lines are NCSA combined with a trailing latency:

    ... CEST [router] method=GET path="/x?a=1" ... status=200 duration=0.118s ...
    ... CEST [web-1] 10.0.0.45 - - [..] "GET /x?a=1 HTTP/1.1" 200 72633 "-" "ua" 0.147

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

# Unified output columns for both log sources.
COLUMNS = ("timestamp", "source", "status", "latency_s", "path", "user_agent", "rest")

# Router lines: key=value pairs, value either "double quoted" or a bare token.
FIELD_RE = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')
ROUTER_SURFACED = {"status", "duration", "path", "user_agent"}

# Gunicorn access lines (combined format) tagged [web-N]. The trailing latency
# (%(L)s, in seconds) is optional so pre-deploy lines without it still parse.
WEB_RE = re.compile(
    r"\[web-\d+\]\s+"
    r"(?P<remote>\S+)\s+\S+\s+\S+\s+"  # remote ident authuser
    r"\[[^\]]+\]\s+"  # [local time]
    r'"(?P<request>[^"]*)"\s+'  # "METHOD path proto"
    r"(?P<status>\d{3})\s+(?P<bytes>\S+)\s+"  # status bytes
    r'"(?P<ref>[^"]*)"\s+"(?P<ua>[^"]*)"'  # "referer" "user-agent"
    r"(?:\s+(?P<lat>[0-9.]+))?\s*$"  # optional trailing latency (s)
)


def parse_router_line(line: str) -> dict | None:
    """Parse a [router] line into a unified row dict, or None if not one."""
    marker = line.find("[router]")
    if marker == -1:
        return None
    fields: dict[str, str] = {}
    for key, quoted, bare in FIELD_RE.findall(line[marker:]):
        fields[key] = quoted if bare == "" else bare
    rest = " ".join(f"{k}={v}" for k, v in fields.items() if k not in ROUTER_SURFACED)
    return {
        "timestamp": line[:marker].strip(),
        "source": "router",
        "status": fields.get("status", "-"),
        "latency_s": fields.get("duration", "-").rstrip("s"),  # "0.118s" -> "0.118"
        "path": fields.get("path", "-"),
        "user_agent": fields.get("user_agent", "-"),
        "rest": rest,
    }


def parse_web_line(line: str) -> dict | None:
    """Parse a [web-N] Gunicorn access line into a unified row dict, or None."""
    match = WEB_RE.search(line)
    if match is None:
        return None
    request = match.group("request")
    parts = request.split(" ")
    method, path = (parts[0], parts[1]) if len(parts) >= 2 else ("-", request)
    return {
        "timestamp": line[: match.start()].strip(),  # Scalingo prefix before [web-N]
        "source": "web",
        "status": match.group("status"),
        "latency_s": match.group("lat") or "-",
        "path": path,
        "user_agent": match.group("ua"),
        "rest": f"method={method} bytes={match.group('bytes')} "
        f"referer={match.group('ref')} remote={match.group('remote')}",
    }


def parse_line(line: str) -> dict | None:
    """Dispatch a raw log line to the router or web parser."""
    if "[router]" in line:
        return parse_router_line(line)
    if "[web-" in line:
        return parse_web_line(line)
    return None


def format_row(parsed: dict) -> str:
    return "\t".join(str(parsed.get(col, "")) for col in COLUMNS)


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
        "--output",
        default=None,
        help="File to append rows to (default: scalingo_metrics/requests_latency_<ts>.tsv).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.stdin and not args.app:
        raise SystemExit("Provide --app / SCALINGO_APP, or use --stdin.")

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = pathlib.Path(args.output or f"scalingo_metrics/requests_latency_{ts}.tsv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = "# " + "\t".join(COLUMNS)

    print(f"Writing request latency (web + router) to {out_path} " f"(Ctrl-C to stop)", file=sys.stderr)
    with out_path.open("a") as fh:
        fh.write(header + "\n")
        fh.flush()
        try:
            for line in line_source(args):
                parsed = parse_line(line)
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
