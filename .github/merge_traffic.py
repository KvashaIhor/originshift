"""Merge a traffic snapshot into the record, keeping every day ever seen.

The API returns a rolling fourteen-day window. Merging by date means a day
observed once is kept even after GitHub forgets it, which is the whole point.
Referrers and paths carry no date, so each snapshot is stamped with the day it
was taken and appended.
"""

import json
import pathlib
import datetime

OUT = pathlib.Path("traffic")
OUT.mkdir(exist_ok=True)
today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def load(path):
    p = OUT / path
    return json.loads(p.read_text()) if p.exists() else {}


def save(path, data):
    (OUT / path).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


for kind in ("views", "clones"):
    fresh = json.loads(pathlib.Path(f"/tmp/{kind}.json").read_text())
    record = load(f"{kind}.json")
    days = {d["timestamp"][:10]: d for d in record.get("days", [])}
    for d in fresh.get(kind, []):
        days[d["timestamp"][:10]] = d
    save(f"{kind}.json", {"days": [days[k] for k in sorted(days)]})

for kind in ("referrers", "paths"):
    fresh = json.loads(pathlib.Path(f"/tmp/{kind}.json").read_text())
    record = load(f"{kind}.json")
    seen = record.get("snapshots", {})
    if fresh:
        seen[today] = fresh
    save(f"{kind}.json", {"snapshots": seen})

print("merged traffic for", today)
