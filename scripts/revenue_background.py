"""Non-foreground local runner for Windows Task Scheduler.

Run with pythonw.exe: no window focus, zero external write actions.
Reports / status / feedback live under a caller-selected private Drive directory.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from app.autonomous_agent import run_once  # noqa: E402

@contextmanager
def single_instance(directory: Path):
    """Prevent concurrent worker instances, even if a prior task remains running."""
    lock_path = directory / ".revenue-agent.lock"
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
        else:
            import fcntl
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                yield False
                return
        try:
            yield True
        finally:
            lock.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

def atomic_json(target: Path, body: dict):
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, target)

def cleanup(directory: Path, keep: int = 30):
    previous = sorted(directory.glob("scan-*.json"), reverse=True)
    for path in previous[keep:]:
        path.unlink(missing_ok=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, help="Private Google Drive folder for reports, DB and feedback")
    args = p.parse_args()
    out = Path(args.root)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with single_instance(out) as acquired:
        if not acquired:
            return
        try:
            os.environ["MAX_PER_SOURCE"] = os.environ.get("MAX_PER_SOURCE", "10")
            os.environ["HTTP_TIMEOUT_SECONDS"] = os.environ.get("HTTP_TIMEOUT_SECONDS", "10")
            report = asyncio.run(run_once(out / "jobs.db", perform_collection=True,
                                          feedback_path=out / "feedback.json"))
            # Never write OAuth tokens, private worker lists or personal account data to the report.
            assert sum(report["external_calls"].values()) == 0
            atomic_json(out / f"scan-{stamp}.json", report)
            atomic_json(out / "latest.json", report)
            cleanup(out)
            atomic_json(out / "status.json", {
                "last_run": report["run_at"], "status": "success",
                "job_sources": len(report["jobs"]["source_counts"]),
                "shortlist": len(report["jobs"]["shortlist"]),
                "mcp_discovered": len(report["mcp_catalog"]["candidates"]),
                "apify_discovered": len(report["apify_catalog"]["candidates"]),
                "writes": 0})
        except Exception as exc:
            # Do not dump remote API tokens/response bodies in errors.
            atomic_json(out / "status.json", {
                "last_run": datetime.now(timezone.utc).isoformat(),
                "status": "error", "error_type": type(exc).__name__})
            raise

if __name__ == "__main__":
    main()
