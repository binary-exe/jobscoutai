#!/usr/bin/env python3
"""
Smoke test for public JobScout API endpoints (no auth).
Usage:
  API_BASE=https://jobscout-api.fly.dev/api/v1 python scripts/smoke_api.py
  python scripts/smoke_api.py  # defaults to http://localhost:8000/api/v1
"""
import os
import sys
import urllib.request
import urllib.error

def main():
    base = os.environ.get("API_BASE", "http://localhost:8000/api/v1").rstrip("/")
    root = base.replace("/api/v1", "").rstrip("/")
    failed = []

    def get(url_path: str, *, use_root: bool = False) -> int:
        path = url_path if url_path.startswith("/") else "/" + url_path
        url = (root.rstrip("/") + path) if use_root else (base.rstrip("/") + path)
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception as e:
            print(f"  ERROR: {e}")
            return 0

    def post(url_path: str, body: bytes, *, use_root: bool = False) -> int:
        path = url_path if url_path.startswith("/") else "/" + url_path
        url = (root.rstrip("/") + path) if use_root else (base.rstrip("/") + path)
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception as e:
            print(f"  ERROR: {e}")
            return 0

    print(f"Smoke testing API at {base}")

    # Health
    print("  GET /health ...", end=" ")
    status = get("/health", use_root=True)
    if status == 200:
        print("OK")
    else:
        print(f"WARN ({status})")

    # Jobs
    print("  GET /jobs?page_size=1 ...", end=" ")
    status = get("/jobs?page_size=1", use_root=False)
    if status == 200:
        print("OK")
    else:
        print(f"FAIL ({status})")
        failed.append("/jobs")

    # Runs latest
    print("  GET /runs/latest ...", end=" ")
    status = get("/runs/latest", use_root=False)
    if status == 200:
        print("OK")
    else:
        print(f"FAIL ({status})")
        failed.append("/runs/latest")

    # Admin stats
    print("  GET /admin/stats ...", end=" ")
    status = get("/admin/stats", use_root=False)
    if status == 200:
        print("OK")
    else:
        print(f"FAIL ({status})")
        failed.append("/admin/stats")

    # KB (Second Brain) - expect 401/422 without auth
    print("  POST /kb/index (no auth) ...", end=" ")
    status = post("/kb/index", b'{"source_type":"note","text":"test"}', use_root=False)
    if status in (401, 422):
        print("OK (auth required)")
    else:
        print(f"WARN ({status})")

    print("  POST /kb/query (no auth) ...", end=" ")
    status = post("/kb/query", b'{"question":"test"}', use_root=False)
    if status in (401, 422):
        print("OK (auth required)")
    else:
        print(f"WARN ({status})")

    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)
    print("All smoke checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
