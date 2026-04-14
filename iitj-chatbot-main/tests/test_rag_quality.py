#!/usr/bin/env python3
"""
test_rag_quality.py — Answer Quality Checks for IIT Jammu Chatbot
===================================================================
Tests that the chatbot gives factually correct answers to known questions.
Runs against the live backend.

Usage:
    python tests/test_rag_quality.py
    python tests/test_rag_quality.py --url https://your-backend.onrender.com
"""
import sys, time, re, argparse
try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"

# (question, list_of_strings_that_MUST appear in answer, description)
QUALITY_TESTS = [
    (
        "What is the B.Tech fee for General category students at IIT Jammu?",
        ["1,51,720"],
        "B.Tech fee for General/OBC"
    ),
    (
        "What is the fee for SC ST students for B.Tech?",
        ["51,720"],
        "B.Tech fee SC/ST waiver"
    ),
    (
        "How do I apply for B.Tech admission at IIT Jammu?",
        ["jee", "josaa"],
        "B.Tech admission route"
    ),
    (
        "What B.Tech branches are available at IIT Jammu?",
        ["computer science", "electrical"],
        "B.Tech branch list"
    ),
    (
        "What is the GATE requirement for M.Tech admission?",
        ["gate"],
        "M.Tech GATE requirement"
    ),
    (
        "What fellowships are available for PhD students?",
        ["pmrf", "fellowship"],
        "PhD fellowship amounts"
    ),
    (
        "Where is IIT Jammu located?",
        ["jagti", "nagrota", "jammu"],
        "Campus location"
    ),
    (
        "What is the hostel fee at IIT Jammu?",
        ["41,320", "60,230"],
        "Hostel charges"
    ),
    (
        "What is the highest placement package at IIT Jammu?",
        ["crore", "lpa", "1.09"],
        "Highest placement CTC"
    ),
    (
        "Who is the Director of IIT Jammu?",
        ["manoj", "gaur"],
        "Director name"
    ),
]

MULTILINGUAL_TESTS = [
    (
        "IIT Jammu में B.Tech की फीस कितनी है?",
        ["1,51,720"],
        "Hindi: B.Tech fee query",
        "hi"
    ),
    (
        "What year was IIT Jammu established?",
        ["2016"],
        "Establishment year",
        "en"
    ),
]


def chat(url: str, message: str, timeout: int = 25):
    r = requests.post(f"{url}/chat", json={"message": message}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def check_answer(answer: str, must_contain: list) -> tuple:
    """Returns (all_found: bool, missing: list)"""
    answer_lower = answer.lower()
    missing = [kw for kw in must_contain if kw.lower() not in answer_lower]
    return len(missing) == 0, missing


def run(base_url: str):
    base_url = base_url.rstrip("/")
    print(f"\n{BOLD}IIT Jammu Chatbot — RAG Answer Quality Tests{RESET}")
    print(f"Target: {base_url}\n")

    # Verify server is up
    try:
        requests.get(f"{base_url}/health", timeout=5).raise_for_status()
    except Exception as e:
        print(f"{RED}✗ Backend not reachable: {e}{RESET}")
        sys.exit(1)

    passed = failed = 0

    print(f"{BOLD}  Factual accuracy tests:{RESET}")
    for question, must_contain, description in QUALITY_TESTS:
        try:
            t0 = time.time()
            d = chat(base_url, question)
            latency = round(time.time()-t0, 2)
            answer = d.get("answer", "")
            ok, missing = check_answer(answer, must_contain)

            if ok:
                print(f"  {GREEN}✓{RESET}  {description}  ({latency}s, conf={d.get('confidence',0):.2f})")
                passed += 1
            else:
                print(f"  {RED}✗{RESET}  {description}  ({latency}s)")
                print(f"       Missing keywords: {YELLOW}{missing}{RESET}")
                print(f"       Answer snippet:   '{answer[:150]}…'")
                failed += 1

        except Exception as e:
            print(f"  {RED}✗{RESET}  {description}  — {e}")
            failed += 1

        time.sleep(0.5)   # avoid hammering

    print(f"\n{BOLD}  Multilingual tests:{RESET}")
    for question, must_contain, description, expected_lang in MULTILINGUAL_TESTS:
        try:
            t0 = time.time()
            d = chat(base_url, question)
            latency = round(time.time()-t0, 2)
            answer   = d.get("answer","")
            det_lang = d.get("detected_language","?")
            ok, missing = check_answer(answer, must_contain)
            lang_ok  = det_lang == expected_lang

            status = GREEN+"✓"+RESET if (ok and lang_ok) else RED+"✗"+RESET
            print(f"  {status}  {description}  (detected={det_lang}, expected={expected_lang}, {latency}s)")

            if not lang_ok:
                print(f"       {YELLOW}Language mismatch: got '{det_lang}', expected '{expected_lang}'{RESET}")
            if not ok:
                print(f"       Missing: {YELLOW}{missing}{RESET}")
                print(f"       Answer: '{answer[:150]}…'")

            if ok and lang_ok: passed += 1
            else: failed += 1

        except Exception as e:
            print(f"  {RED}✗{RESET}  {description}  — {e}")
            failed += 1

        time.sleep(0.5)

    total = passed + failed
    pct = int(passed/max(total,1)*100)
    color = GREEN if pct >= 80 else (YELLOW if pct >= 50 else RED)
    bar = "█" * int(pct/5) + "░" * (20 - int(pct/5))
    print(f"\n{'─'*50}")
    print(f"  {color}{BOLD}Quality score: {passed}/{total}  [{bar}] {pct}%{RESET}\n")

    if failed:
        print(f"  {YELLOW}Low scores usually mean:{RESET}")
        print(f"    • Knowledge index needs re-crawling (run scraper/crawler.py)")
        print(f"    • Index needs rebuilding (run scraper/indexer.py)")
        print(f"    • Gemini temperature too high (check backend/gemini_client.py)")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    success = run(args.url)
    sys.exit(0 if success else 1)
