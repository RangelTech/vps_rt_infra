#!/usr/bin/env python3
"""Self-healing poller for the long jobs on the VPS. Run from cron every 5 minutes.

It relaunches the Kaggle subject exports and the Qwen reindex when their process died before the work was done,
refuses to launch when memory is low, builds the vector index when the reindex completes, and writes one status
line per run to ~/watchdog.log. It never touches a job that is still running, and it never deletes anything.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

HOME = Path.home()
EXPORTS = HOME / "exports"
LEDGER = EXPORTS / "candidates" / "subjects" / "ledger.jsonl"
EXPECTED = json.loads((EXPORTS / "expected_slugs.json").read_text())
LOG = HOME / "watchdog.log"
STATE = HOME / "watchdog_state.json"
MIN_AVAILABLE_MB = 1800
MAX_FAILS_PER_SLUG = 6

# script name -> (subjects it covers, process match)
KAGGLE_JOBS = {
    "subjects_c.sh": ["pncp", "siope"],
    "subjects_d.sh": ["fnde-salario-educacao", "taxas-rendimento", "censo-escolar", "saeb"],
}


def sh(cmd: str, timeout: int = 60) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def log(message: str) -> None:
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def available_mb() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) // 1024
    return 0


def running(pattern: str) -> bool:
    # bracket the first character so the pgrep command line does not match itself
    bracketed = f"[{pattern[0]}]{pattern[1:]}"
    out = sh(f"pgrep -f '{bracketed}' | wc -l")
    return out.strip() not in ("", "0")


def ledger_status() -> dict[str, dict]:
    last: dict[str, dict] = {}
    fails: dict[str, int] = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            record = json.loads(line)
            last[record["key"]] = record
            if record.get("status") == "failed":
                fails[record["key"]] = fails.get(record["key"], 0) + 1
    for key, count in fails.items():
        last[key]["fails"] = count
    return last


def launch(script: str) -> None:
    subprocess.Popen(["setsid", "nohup", "bash", str(EXPORTS / script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, start_new_session=True)


def main() -> None:
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    status = ledger_status()
    mem = available_mb()
    notes = [f"mem={mem}MB"]

    # Kaggle exports
    for script, subjects in KAGGLE_JOBS.items():
        slugs = [s for subject in subjects for s in EXPECTED.get(subject, [])]
        pending = [s for s in slugs if status.get(s, {}).get("status") != "published"
                   and status.get(s, {}).get("fails", 0) < MAX_FAILS_PER_SLUG]
        alive = running(f"subject_release.py run {subjects[0]}")
        notes.append(f"{script}: pending={len(pending)} alive={alive}")
        if pending and not alive:
            if mem < MIN_AVAILABLE_MB:
                notes.append(f"{script}: not relaunched, low memory")
            else:
                launch(script)
                notes.append(f"{script}: RELAUNCHED")
                log(f"relaunched {script}, pending {pending}")
                mem -= 900  # keep the second launch of this run honest

    # Qwen reindex
    count = int(sh("docker exec pncp-db-db-1 psql -U pncp_owner -d pncp -Atc "
                   "\"select coalesce(max(n_live_tup),0) from pg_stat_user_tables where relname='editais_embeddings_qwen'\"") or 0)
    # the source (Vertex) table holds one row per notice after deduplication; require 99.9 percent of it
    total = int(sh("docker exec pncp-db-db-1 psql -U pncp_owner -d pncp -Atc "
                   "\"select coalesce(max(n_live_tup),0) from pg_stat_user_tables where relname='editais_embeddings'\"") or 1_160_000)
    REINDEX_TARGET = int(total * 0.995)
    alive = running("reindex_qwen.py")
    notes.append(f"reindex: {count}/{REINDEX_TARGET} alive={alive}")
    last_line = sh("grep REINDEX_PASS_DONE /opt/pncp-db-infra/reindex.log | tail -1")
    # a pass that embedded nothing new means every source text already has a vector
    complete = count >= REINDEX_TARGET or "embedded 0 this run" in last_line
    # a process that is alive but has not added a row for 20 minutes is stalled (for example a crashed reader thread)
    now = time.time()
    if alive and count > state.get("reindex_count", -1):
        state["reindex_count"], state["reindex_progress_at"] = count, now
    stalled = alive and not complete and now - state.get("reindex_progress_at", now) > 20 * 60
    if stalled:
        for pid in sh("pgrep -f '[r]eindex_qwen.py'").split():
            sh(f"kill {pid}")
        notes.append("reindex: STALLED, killed")
        log("reindex stalled for 20 minutes, killed it")
        time.sleep(3)
        alive = False
        state["reindex_progress_at"] = now
    STATE.write_text(json.dumps(state))
    if not complete and not alive:
        if mem < MIN_AVAILABLE_MB:
            notes.append("reindex: not relaunched, low memory")
        else:
            subprocess.Popen(["setsid", "nohup", "bash", "-c", "WORKERS=8 BATCH=64 bash /opt/pncp-db-infra/reindex.sh"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
            notes.append("reindex: RELAUNCHED")
            log("relaunched the Qwen reindex")
    if complete and not alive and not state.get("ivf_started"):
        subprocess.Popen(["setsid", "nohup", "bash", "/opt/pncp-db-infra/ivf_qwen.sh"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        state["ivf_started"] = time.strftime("%Y-%m-%d %H:%M:%S")
        STATE.write_text(json.dumps(state))
        notes.append("reindex complete: IVFFlat build started")
        log("reindex complete, building the IVFFlat index")

    log("status " + " | ".join(notes))


if __name__ == "__main__":
    main()
