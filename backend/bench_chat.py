"""Latency / reply-length benchmark for POST /api/chat (calls the live model).

Run from backend/ while the server is up:
    ../.venv/bin/python bench_chat.py [port] [rounds]
"""

import statistics
import sys
import time

import httpx

PORT = sys.argv[1] if len(sys.argv) > 1 else "8000"
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 2

QUESTIONS = [
    ("on-topic", "How much is the Basic Hoodie Big Yale?", None),
    ("on-topic", "Do you have the Crew Left Chest Hoodie in a medium?", None),
    ("on-topic", "What quarter-zips do you have?", None),
    ("on-topic", "Is this in stock in large?", {"path": "/products/ice-hockey-left-chest-hoodie"}),
    ("off-topic", "What's the capital of France?", None),
    ("off-topic", "Can you help me write a cover letter?", None),
    ("off-topic", "Who won the NBA finals last year?", None),
]


def main() -> None:
    rows = []
    with httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=180) as client:
        for _ in range(ROUNDS):
            for kind, message, page in QUESTIONS:
                payload = {"message": message, "history": []}
                if page:
                    payload["page"] = page
                start = time.perf_counter()
                r = client.post("/api/chat", json=payload)
                elapsed = time.perf_counter() - start
                reply = r.json().get("reply", "") if r.status_code == 200 else f"HTTP {r.status_code}"
                rows.append((kind, message, elapsed, len(reply.split()), reply))
                print(f"{elapsed:5.1f}s {len(reply.split()):3d}w [{kind}] {message}\n        {reply!r}")

    print("\nSummary")
    for kind in ("on-topic", "off-topic"):
        times = [r[2] for r in rows if r[0] == kind]
        words = [r[3] for r in rows if r[0] == kind]
        print(f"  {kind:9s} median {statistics.median(times):4.1f}s  mean {statistics.mean(times):4.1f}s  "
              f"median reply {statistics.median(words):.0f} words  (n={len(times)})")


if __name__ == "__main__":
    main()
