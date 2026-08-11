#!/usr/bin/env python3
"""Detect containers whose ``docker logs`` reads are silently truncated.

A container can keep writing perfectly good logs while ``docker logs --since``
returns *nothing* for them. Monitoring that trusts ``--since`` then reports the
container as quiet, and quiet reads as healthy. This script catches that.

Why this exists
---------------
On 2026-08-10 the fleet log sweep reported ``epita lines=0 errs=0`` for a 12 h
window while the other six tenants reported 200-560 lines. epita was not quiet:
its log file held 2845 records spanning 08-06 to 08-10, 371 of them that day,
and it was serving live public traffic the whole time.

The cause was a **torn write** at physical line 402, produced during the
v0.11.0 rollout restart of 2026-08-07 -- two json-file records spliced into one
physical line::

    {"log":"202{"log":"ERROR [open_webui.env] Error running migrations: ...

Docker's json-file reader parses forward, record by record, and stops at the
malformed line. Everything written after the tear is unreachable to any forward
read: a full ``docker logs`` returns exactly the 401 lines that precede it, and
``--since`` returns 0 for any window after the tear. ``--tail N`` seeks backward
from EOF instead, so it reads recent lines correctly -- which is why asking for
*more* lines returned *fewer*::

    docker logs epita --tail 1000   -> 1000 lines, dated 08-09 and 08-10
    docker logs epita --tail 5000   ->  401 lines, dated 08-06 and 08-07
    docker logs epita --since 12h   ->    0 lines

That contradiction is the detector. Two independent signals are used:

1. **window disagreement** -- ``--since W`` returns nothing (or far less) than a
   backward ``--tail`` read restricted to the same window W;
2. **tail inversion** -- a larger ``--tail`` returns strictly fewer lines than a
   smaller one, which a healthy stream can never do.

Either one firing means forward reads of that container cannot be trusted.

Remedy
------
A tear is permanent for the life of the log file. ``docker restart`` does not
help: the container keeps appending to the same file. The file is replaced only
by recreating the container (``docker compose ... up -d --force-recreate``) or
by rotation, which needs the file to reach ``max-size`` (10m here -- weeks away
at ~0.5 MB). Until then, scan that container with ``--tail N``, never
``--since``, and keep N at or below the budget this script prints.

Overshooting that budget does not fail loudly. ``--tail N`` seeks back N records
and then parses *forward*, so once N reaches past the tear the read starts
before it and stops there. Overshoot by k and you get exactly k-1 lines, all of
them predating the tear, saturating at the pre-tear total. Measured on epita
with a budget of 2726 and 401 records before the tear::

    --tail 2726 -> 2726 lines, dated 08-07..08-11   (the whole live window)
    --tail 2728 ->    1 line,  dated 08-07          (stale)
    --tail 2800 ->   73 lines, dated 08-07          (stale)
    --tail 3128 ->  401 lines, dated 08-06..08-07   (stale, saturated)

A near miss is the dangerous case: a handful of lines reads as "quiet
container", not as a failed read, and every one of them is days old. Use
``--json`` to feed the budget straight into a scanner rather than copying the
number by hand -- it drifts upward as the container logs.

Read-only: runs ``docker ps`` / ``docker logs`` only, changes nothing.

Usage
-----
    python scripts/docker-log-health.py                     # all OWUI tenants
    python scripts/docker-log-health.py --window 24h
    python scripts/docker-log-health.py --match ''          # every container
    python scripts/docker-log-health.py --container epita-open-webui-open-webui-1
    python scripts/docker-log-health.py --json           # for a scanner to consume

Exit status is 1 if any container's forward reads are truncated, so the script
can gate a monitoring run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys

# Default: the Open WebUI tenant containers. Pass --match '' to scan everything.
DEFAULT_MATCH = "open-webui-open-webui-1"

# Backward reads used for the inversion probe. The larger one must be big enough
# to reach past a tear near the head of the file.
TAIL_SMALL = 1000
TAIL_LARGE = 100000

RFC3339 = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s")

WINDOW_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def parse_window(text: str) -> dt.timedelta:
    """'12h' -> timedelta(hours=12). Accepts s/m/h/d."""
    match = re.fullmatch(r"(\d+)([smhd])", text.strip())
    if not match:
        raise argparse.ArgumentTypeError(
            f"bad window {text!r}: expected e.g. 30m, 12h, 2d"
        )
    return dt.timedelta(**{WINDOW_UNITS[match.group(2)]: int(match.group(1))})


def docker(*args: str) -> list[str]:
    """Run a docker command, returning stdout+stderr as lines.

    Container logs go to both streams (uvicorn writes to stderr), so both are
    captured -- exactly what a monitoring sweep would collect.
    """
    proc = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return [line for line in out.splitlines() if line]


def list_containers(match: str) -> list[str]:
    names = docker("ps", "--format", "{{.Names}}")
    return sorted(n for n in names if match in n)


def stamps(lines: list[str]) -> list[dt.datetime]:
    """Docker-assigned timestamps from a ``--timestamps`` read.

    Continuation lines of a multi-line traceback carry no prefix; they are
    skipped rather than guessed at.
    """
    found = []
    for line in lines:
        match = RFC3339.match(line)
        if not match:
            continue
        text = match.group(1).replace("Z", "+00:00")
        try:
            found.append(dt.datetime.fromisoformat(text))
        except ValueError:
            continue
    return found


def safe_tail_budget(name: str, newest: dt.datetime) -> int | None:
    """Largest ``--tail N`` that still reads past the tear, by bisection.

    Knowing a container is truncated is not enough to scan it: ``--tail N``
    works only while N stays below the number of records written *after* the
    tear. Past that the read starts before the tear and stops at it, returning
    k-1 stale lines for an overshoot of k -- silently, which is the same failure
    the check exists to catch. See the module docstring for the measured curve.

    The ceiling rises as the container keeps logging (epita: 2587 -> 2726 in a
    day), so it is measured per run and never recorded.

    The predicate is "this read still reaches the newest record", not a line
    count: a healthy short log legitimately returns fewer lines than asked.
    Returns None if no cliff exists below ``TAIL_LARGE``.
    """
    def reaches_newest(n: int) -> bool:
        seen = stamps(docker("logs", name, "--tail", str(n), "--timestamps"))
        return bool(seen) and max(seen) >= newest

    if reaches_newest(TAIL_LARGE):
        return None
    lo, hi = 1, TAIL_LARGE  # lo known-good after the loop, hi known-bad
    if not reaches_newest(lo):
        return 0
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if reaches_newest(mid):
            lo = mid
        else:
            hi = mid
    return lo


def inspect(name: str, window: dt.timedelta) -> dict:
    cutoff = dt.datetime.now(dt.timezone.utc) - window
    since_arg = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    forward = docker("logs", name, "--since", since_arg, "--timestamps")
    tail_small = docker("logs", name, "--tail", str(TAIL_SMALL), "--timestamps")
    tail_large = docker("logs", name, "--tail", str(TAIL_LARGE), "--timestamps")

    # Backward view of the same window: the ground truth the forward read should
    # have matched. The two tail reads overlap, so the window is counted from
    # whichever is richer rather than by summing them.
    backward_n = max(
        len([t for t in stamps(tail_large) if t >= cutoff]),
        len([t for t in stamps(tail_small) if t >= cutoff]),
    )

    all_stamps = stamps(tail_small) or stamps(tail_large)
    last_seen = max(all_stamps) if all_stamps else None

    inversion = len(tail_large) < len(tail_small)
    # A forward read that finds nothing while a backward read finds plenty is the
    # signature. Anything under half is already untrustworthy.
    forward_n = len([t for t in stamps(forward) if t >= cutoff])
    disagreement = backward_n > 0 and forward_n < backward_n / 2

    if inversion or disagreement:
        verdict = "TRUNCATED"
    elif backward_n == 0 and forward_n == 0:
        verdict = "SILENT"
    else:
        verdict = "OK"

    budget = (
        safe_tail_budget(name, last_seen)
        if verdict == "TRUNCATED" and last_seen is not None
        else None
    )

    return {
        "name": name,
        "verdict": verdict,
        "forward": forward_n,
        "backward": backward_n,
        "tail_small": len(tail_small),
        "tail_large": len(tail_large),
        "inversion": inversion,
        "disagreement": disagreement,
        "last_seen": last_seen,
        "budget": budget,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect containers whose forward `docker logs` reads are truncated."
    )
    parser.add_argument(
        "--window",
        type=parse_window,
        default=parse_window("12h"),
        metavar="12h",
        help="window compared between forward and backward reads (default 12h)",
    )
    parser.add_argument(
        "--match",
        default=DEFAULT_MATCH,
        help=f"substring a container name must contain (default {DEFAULT_MATCH!r}; "
        "pass '' for every running container)",
    )
    parser.add_argument(
        "--container",
        action="append",
        dest="containers",
        help="explicit container name; repeatable, overrides --match",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the rows as JSON instead of a table, so a log scanner can "
        "cap its own `--tail` at each container's budget (null = no cap needed)",
    )
    args = parser.parse_args()

    names = args.containers or list_containers(args.match)
    if not names:
        print("no running container matched", file=sys.stderr)
        return 2

    if args.json:
        rows = [inspect(name, args.window) for name in names]
        for row in rows:
            last = row["last_seen"]
            row["last_seen"] = last.isoformat() if last else None
        print(json.dumps(rows, indent=2))
        return 1 if any(r["verdict"] == "TRUNCATED" for r in rows) else 0

    print(
        f"{'container':<42} {'verdict':<10} {'fwd':>6} {'back':>6} "
        f"{'tail1k':>7} {'tail100k':>9}  last log"
    )
    truncated = []
    for name in names:
        row = inspect(name, args.window)
        last = row["last_seen"]
        last_text = last.strftime("%Y-%m-%d %H:%M:%SZ") if last else "-"
        print(
            f"{row['name']:<42} {row['verdict']:<10} {row['forward']:>6} "
            f"{row['backward']:>6} {row['tail_small']:>7} {row['tail_large']:>9}  "
            f"{last_text}"
        )
        if row["verdict"] == "TRUNCATED":
            truncated.append(row)

    if truncated:
        print()
        print("Forward reads are TRUNCATED on:")
        for row in truncated:
            reasons = []
            if row["inversion"]:
                reasons.append(
                    f"tail inversion (--tail {TAIL_LARGE} returned "
                    f"{row['tail_large']} lines, --tail {TAIL_SMALL} returned "
                    f"{row['tail_small']})"
                )
            if row["disagreement"]:
                reasons.append(
                    f"--since saw {row['forward']} lines in the window, "
                    f"--tail saw {row['backward']}"
                )
            print(f"  {row['name']}: " + "; ".join(reasons))
            if row["budget"]:
                print(
                    f"      scan it with:  docker logs {row['name']} "
                    f"--tail {row['budget']}      <- do NOT exceed this"
                )
        print()
        print(
            "Scan these with `docker logs <name> --tail N`, never `--since`: a\n"
            "`--since` sweep reports them as quiet, and quiet reads as healthy.\n"
            "Keep N at or below the printed budget -- it drifts upward as the\n"
            "container logs, so re-measure every run (or use --json to cap a\n"
            "scanner automatically). Overshooting does not fail loudly: one line\n"
            "past returns a single stale line, a few past returns a few, and a\n"
            "large overshoot saturates at the pre-tear total. The near miss is\n"
            "the trap -- a handful of days-old lines reads as 'quiet container',\n"
            "not as a failed read.\n"
            "The tear is permanent until the log file is replaced -- `docker\n"
            "restart` keeps the same file; only `up -d --force-recreate` (or\n"
            "rotation at max-size) starts a new one."
        )
        return 1

    print()
    print("All forward reads agree with backward reads: `--since` sweeps are trustworthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
