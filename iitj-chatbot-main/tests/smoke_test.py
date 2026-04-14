#!/usr/bin/env python3
"""
smoke_test.py — Quick API smoke test for IIT Jammu Chatbot
===========================================================
Run this from anywhere (no project imports needed).
It only needs: requests  (pip install requests)

Usage:
    python tests/smoke_test.py
    python tests/smoke_test.py --url https://iitj-chatbot-backend.onrender.com
"""
import sys, time, json, argparse

try:
    import requests
except ImportError:
    print("Install requests first:  pip install requests")
    sys.exit(1)

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"

def ok(msg): print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg): print(f"  {RED}✗{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")

TESTS = [
    # (description, method, path, payload, expected_status, validator_fn)
    ("Health check",
     "GET", "/health", None, 200,
     lambda d: d.get("status") == "ok"),

    ("Index stats",
     "GET", "/index/stats", None, 200,
     lambda d: len(d.get("top_level_sections",[])) >= 1),

    ("Suggested questions",
     "GET", "/suggestions", None, 200,
     lambda d: len(d.get("questions",[])) >= 3),

    ("Chat: English fee query",
     "POST", "/chat",
     {"message": "What is the B.Tech fee structure at IIT Jammu?"},
     200,
     lambda d: d.get("answer") and len(d["answer"]) > 30),

    ("Chat: Hindi query",
     "POST", "/chat",
     {"message": "आईआईटी जम्मू में प्रवेश कैसे होता है?"},
     200,
     lambda d: d.get("answer") and d.get("detected_language") == "hi"),

    ("Chat: empty message → 422",
     "POST", "/chat",
     {"message": ""},
     422,
     lambda d: True),

    ("Chat: very long message → 422",
     "POST", "/chat",
     {"message": "x" * 2100},
     422,
     lambda d: True),

    ("Chat: multilingual — Tamil",
     "POST", "/chat",
     {"message": "IIT Jammu இல் PhD சேர்க்கை எப்படி?"},
     200,
     lambda d: d.get("answer") and len(d["answer"]) > 20),
]


def run(base_url: str, skip_chat: bool):
    base_url = base_url.rstrip("/")
    print(f"\n{BOLD}IIT Jammu Chatbot — API Smoke Test{RESET}")
    print(f"Target: {base_url}\n")

    passed = failed = 0

    for desc, method, path, payload, exp_status, validator in TESTS:
        if skip_chat and path == "/chat":
            warn(f"{desc}  [skipped]")
            continue

        url = f"{base_url}{path}"
        t0 = time.time()
        try:
            if method == "GET":
                r = requests.get(url, timeout=25)
            else:
                r = requests.post(url, json=payload, timeout=25)
            latency = round(time.time()-t0, 3)

            if r.status_code != exp_status:
                fail(f"{desc}  — expected HTTP {exp_status}, got {r.status_code}  ({latency}s)")
                failed += 1
                continue

            try:
                data = r.json()
            except Exception:
                data = {}

            if not validator(data):
                fail(f"{desc}  — response validation failed  ({latency}s)\n     {json.dumps(data)[:200]}")
                failed += 1
            else:
                extra = ""
                if path == "/chat" and data.get("answer"):
                    extra = f" | lang={data.get('detected_language')} | conf={data.get('confidence')} | {len(data['answer'])} chars"
                ok(f"{desc}  ({latency}s){extra}")
                passed += 1

        except requests.exceptions.ConnectionError:
            fail(f"{desc}  — Cannot connect to {url}")
            print(f"     {RED}→ Is the backend running? Start with: uvicorn main:app --port 8000{RESET}")
            failed += 1
        except requests.exceptions.Timeout:
            fail(f"{desc}  — Timeout (>25s)")
            failed += 1
        except Exception as e:
            fail(f"{desc}  — {e}")
            failed += 1

    total = passed + failed
    print(f"\n{'─'*50}")
    color = GREEN if failed == 0 else (YELLOW if passed > failed else RED)
    print(f"{color}{BOLD}  {passed}/{total} passed{RESET}")
    if failed:
        print(f"{RED}  {failed}/{total} failed{RESET}")
    print()
    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--skip-chat", action="store_true",
                        help="Skip /chat calls (saves Gemini quota)")
    args = parser.parse_args()
    success = run(args.url, args.skip_chat)
    sys.exit(0 if success else 1)
