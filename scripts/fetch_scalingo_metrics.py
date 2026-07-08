#!/usr/bin/env python3
"""Fetch container metrics from the Scalingo API and save them for later analysis.

Metrics pulled: cpu, memory, swap (per container type) and router (request
counts, optionally filtered by status code). Each metric is written as a
separate TSV file plus a combined long-format TSV, under a timestamped run
directory.

Auth flow (Scalingo uses a two-step exchange):
  1. You hold a long-lived API token (starts with `tk-...`), created at
     https://dashboard.scalingo.com/account/tokens
  2. That token is exchanged for a short-lived Bearer JWT via
     POST https://auth.scalingo.com/v1/tokens/exchange (HTTP Basic, token as password).
  3. The JWT is used as `Authorization: Bearer <jwt>` for the regional API.

Only the Python standard library is used, so this runs anywhere with python3.

Usage:
  export SCALINGO_API_TOKEN=tk-us-xxxxxxxx
  python scripts/fetch_scalingo_metrics.py --app my-app --since 48

  # secnum region (beta.gouv.fr apps are often here):
  python scripts/fetch_scalingo_metrics.py --app my-app --region osc-secnum-fr1

  # watch real-time stats to catch memory PEAKS (historical series are averaged
  # into ~14 min buckets and hide spikes); poll every 15s until Ctrl-C:
  python scripts/fetch_scalingo_metrics.py --app my-app --watch 15
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = "https://auth.scalingo.com/v1/tokens/exchange"

# Regional API base URLs. Override with --api-url if your region differs.
REGION_API_URLS = {
    "osc-fr1": "https://api.osc-fr1.scalingo.com",
    "osc-secnum-fr1": "https://api.osc-secnum-fr1.scalingo.com",
}

RESOURCE_METRICS = ("cpu", "memory", "swap")
ROUTER_STATUS_CODES = ("all", "2XX", "3XX", "4XX", "5XX")

# Fixed column order for the real-time watch output.
WATCH_COLUMNS = (
    "time",
    "id",
    "cpu_usage",
    "memory_usage",
    "memory_limit",
    "highest_memory_usage",
    "swap_usage",
    "swap_limit",
    "highest_swap_usage",
)

# Watch columns that are byte counts; each gets a "<col>_human" column beside it.
WATCH_BYTE_COLUMNS = {
    "memory_usage",
    "memory_limit",
    "highest_memory_usage",
    "swap_usage",
    "swap_limit",
    "highest_swap_usage",
}


def watch_header():
    """Column header for watch output, with a _human column after each byte column."""
    cols = []
    for col in WATCH_COLUMNS:
        cols.append(col)
        if col in WATCH_BYTE_COLUMNS:
            cols.append(f"{col}_human")
    return cols


def watch_row(row):
    """Format one watch row, adding human-readable byte values inline."""
    cells = []
    for col in WATCH_COLUMNS:
        cells.append(_fmt(row.get(col)))
        if col in WATCH_BYTE_COLUMNS:
            cells.append(_human_bytes(row.get(col)))
    return cells


# Metrics whose value is a byte count and gets a human-readable extra column.
BYTE_METRICS = {"memory", "swap"}


def _fmt(value):
    """Render a metric value for TSV: ints as ints, floats without sci notation."""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return "" if value is None else str(value)


def _human_bytes(value):
    """Render a byte count as a human-readable binary size, e.g. '304.4 MiB'."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def write_series_tsv(path, series, human=False):
    """Write a [{time, value}, ...] series as TSV (time<TAB>value).

    When human=True, append a value_human column with the byte size formatted
    for readability."""
    header = "time\tvalue\tvalue_human" if human else "time\tvalue"
    lines = [header]
    if isinstance(series, list):
        for point in series:
            value = point.get("value")
            row = f"{point.get('time', '')}\t{_fmt(value)}"
            if human:
                row += f"\t{_human_bytes(value)}"
            lines.append(row)
    path.write_text("\n".join(lines) + "\n")


def _request(url: str, *, headers: dict, method: str = "GET", data: bytes | None = None):
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {exc.code} calling {url}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error calling {url}: {exc.reason}") from exc
    return json.loads(body) if body else {}


def exchange_token(api_token: str) -> str:
    """Exchange a long-lived API token for a short-lived Bearer JWT."""
    basic = base64.b64encode(f":{api_token}".encode()).decode()
    payload = _request(
        AUTH_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
        data=b"{}",
    )
    token = payload.get("token")
    if not token:
        raise SystemExit(f"Token exchange returned no token: {payload}")
    return token


def fetch_metric(api_url, app, bearer, metric, *, container, since, status_code=None):
    """Fetch one metric series. Returns the parsed JSON response."""
    path = f"/v1/apps/{urllib.parse.quote(app)}/stats/{metric}"
    if metric != "router" and container:
        path += f"/{container}"
    query = {"since": str(since)}
    if metric == "router" and status_code:
        query["status_code"] = status_code
    url = f"{api_url}{path}?{urllib.parse.urlencode(query)}"
    headers = {"Authorization": f"Bearer {bearer}", "Accept": "application/json"}
    return _request(url, headers=headers)


def fetch_realtime_stats(api_url, app, bearer):
    """Fetch instantaneous per-container stats, including highest_memory_usage."""
    url = f"{api_url}/v1/apps/{urllib.parse.quote(app)}/stats"
    headers = {"Authorization": f"Bearer {bearer}", "Accept": "application/json"}
    return _request(url, headers=headers)


def run_watch(api_url, app, api_token, interval, out_path):
    """Poll real-time stats every `interval` seconds, appending one TSV row
    per container per poll. Catches memory peaks that the averaged historical
    metrics smooth away. Runs until interrupted (Ctrl-C)."""
    import time

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bearer = exchange_token(api_token)
    token_age = time.monotonic()
    print(f"Watching {app} every {interval}s -> {out_path} (Ctrl-C to stop)")
    with out_path.open("a") as fh:
        fh.write("\t".join(watch_header()) + "\n")
        fh.flush()
        while True:
            # Bearer JWTs are short-lived (~1h); refresh well before expiry.
            if time.monotonic() - token_age > 1800:
                bearer = exchange_token(api_token)
                token_age = time.monotonic()
            ts = dt.datetime.now(dt.timezone.utc).isoformat()
            try:
                payload = fetch_realtime_stats(api_url, app, bearer)
            except SystemExit as exc:
                print(f"  {ts} poll failed: {exc}", file=sys.stderr)
                time.sleep(interval)
                continue
            for stat in payload.get("stats", []):
                row = {"time": ts, **stat}
                fh.write("\t".join(watch_row(row)) + "\n")
            fh.flush()
            peaks = " ".join(
                f"{s.get('id')}={s.get('memory_usage', 0) // 1048576}"
                f"/{s.get('highest_memory_usage', 0) // 1048576}MB"
                for s in payload.get("stats", [])
            )
            print(f"  {ts} {peaks}")
            time.sleep(interval)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", default=os.environ.get("SCALINGO_APP"), help="App name (or set SCALINGO_APP).")
    parser.add_argument("--container", default="web", help="Container type for cpu/memory/swap (default: web).")
    parser.add_argument("--since", type=int, default=48, help="Look-back window in hours (default: 48).")
    parser.add_argument(
        "--region",
        default=os.environ.get("SCALINGO_REGION", "osc-fr1"),
        choices=sorted(REGION_API_URLS),
        help="Scalingo region (default: osc-fr1).",
    )
    parser.add_argument(
        "--api-url", default=os.environ.get("SCALINGO_API_URL"), help="Override the regional API base URL entirely."
    )
    parser.add_argument("--output-dir", default="scalingo_metrics", help="Directory to write TSV into.")
    parser.add_argument(
        "--watch",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Poll real-time stats (incl. highest_memory_usage) every SECONDS "
        "instead of fetching historical series. Catches peaks the averaged "
        "history hides. Runs until Ctrl-C.",
    )
    parser.add_argument(
        "--watch-output",
        default=None,
        help="TSV file for --watch output " "(default: <output-dir>/<app>_watch_<ts>.tsv).",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    api_token = os.environ.get("SCALINGO_API_TOKEN")
    if not api_token:
        raise SystemExit("Set SCALINGO_API_TOKEN (create one at dashboard > Account > Tokens).")
    if not args.app:
        raise SystemExit("Provide --app or set SCALINGO_APP.")

    api_url = (args.api_url or REGION_API_URLS[args.region]).rstrip("/")

    if args.watch:
        watch_ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        out_path = pathlib.Path(
            args.watch_output or pathlib.Path(args.output_dir) / f"{args.app}_watch_{watch_ts}.tsv"
        )
        try:
            run_watch(api_url, args.app, api_token, args.watch, out_path)
        except KeyboardInterrupt:
            print("\nStopped.")
        return 0

    bearer = exchange_token(api_token)

    run_ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = pathlib.Path(args.output_dir) / f"{args.app}_{run_ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # One TSV per metric (time<TAB>value) plus a combined long-format TSV
    # (metric<TAB>time<TAB>value<TAB>value_human) covering every series.
    combined_rows = ["metric\ttime\tvalue\tvalue_human"]

    def collect(label, series):
        if isinstance(series, list):
            for point in series:
                value = point.get("value")
                human = _human_bytes(value) if label in BYTE_METRICS else ""
                combined_rows.append(f"{label}\t{point.get('time', '')}\t{_fmt(value)}\t{human}")
            print(f"  {label:12s} -> {len(series)} points")
        else:
            print(f"  {label:12s} -> (no series)")

    for metric in RESOURCE_METRICS:
        data = fetch_metric(api_url, args.app, bearer, metric, container=args.container, since=args.since)
        write_series_tsv(out_dir / f"{metric}.tsv", data, human=metric in BYTE_METRICS)
        collect(metric, data)

    for code in ROUTER_STATUS_CODES:
        data = fetch_metric(api_url, args.app, bearer, "router", container=None, since=args.since, status_code=code)
        write_series_tsv(out_dir / f"router_{code}.tsv", data)
        collect(f"router_{code}", data)

    (out_dir / "all_metrics.tsv").write_text("\n".join(combined_rows) + "\n")
    print(f"\nSaved metrics to {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
