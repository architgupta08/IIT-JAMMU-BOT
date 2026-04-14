# IIT Jammu Chatbot — Test Suite

Three test files — run them in order.

---

## 1. `test_all.py` — Full System Health Check
Checks every layer: env vars, dependencies, knowledge index, scraper logic,
indexer logic, backend models, language detection, RAG engine, live server,
frontend files, and deployment configs.

```bash
# From project root:
cd iitj-chatbot

# Run everything
python tests/test_all.py

# Skip live Gemini API calls (saves quota)
python tests/test_all.py --skip-api

# Test only one group
python tests/test_all.py --only index
python tests/test_all.py --only server
python tests/test_all.py --only scraper

# Test against deployed backend
python tests/test_all.py --backend-url https://iitj-chatbot-backend.onrender.com
```

**Groups tested:**
| # | Group | What it checks |
|---|-------|---------------|
| 0 | env | .env file, required vars, Python version |
| 1 | deps | All pip packages installed |
| 2 | index | JSON tree valid, nodes present, text/summaries |
| 3 | scraper | URL normalisation, HTML→MD conversion (no network) |
| 4 | indexer | Topic assignment, offline summariser, section parsing |
| 5 | backend | Language detection, RAG tree loading, Pydantic models |
| 6 | gemini | Live Gemini API ping (skippable) |
| 7 | server | All REST endpoints, /chat correctness |
| 8 | frontend | Files exist, node_modules, dist build |
| 9 | deploy | Docker/Render/Railway config files |

---

## 2. `smoke_test.py` — Quick API Smoke Test
Fast pass/fail test of every API endpoint. No project imports needed —
copy to any machine that has `requests`.

```bash
# Local
python tests/smoke_test.py

# Against deployed URL
python tests/smoke_test.py --url https://iitj-chatbot-backend.onrender.com

# Skip /chat to save Gemini quota
python tests/smoke_test.py --skip-chat
```

---

## 3. `test_rag_quality.py` — Answer Quality Verification
Sends 12 real questions to the chatbot and checks that answers contain
expected facts (fee amounts, branch names, location, etc.).

```bash
python tests/test_rag_quality.py
python tests/test_rag_quality.py --url https://iitj-chatbot-backend.onrender.com
```

A quality score ≥ 80% means the RAG pipeline is working correctly.

---

## Typical output when everything is working

```
IIT Jammu Chatbot — System Health Check
Working dir: /path/to/iitj-chatbot

──────────────────────────────────────────────────────────
  0 · Environment & Configuration
──────────────────────────────────────────────────────────
  ✓ PASS  .env file exists
  ✓ PASS  $GEMINI_API_KEY set  — AIzaSy…
  ✓ PASS  Python 3.11 (need ≥3.10)

... (all groups) ...

══════════════════════════════════════════════════════════
  SUMMARY
══════════════════════════════════════════════════════════
  ✓ PASS  52/55 checks passed
  ⚠ WARN  2 warnings
  - SKIP  1 skipped

  Health: [████████████████████████████████████░░░░] 95%
```
