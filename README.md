# FinPilot: Personal Finance Intelligence
**CSB312 Generative AI Foundations | CA3 Mini Project 2 | Option 8**
**Automation idea:** Convert a spoken or typed expense into a structured transaction and save it to a ledger.

## Workflow
```
User input (text / voice)
  -> AI extraction (Gemini)
  -> schema-guided JSON
  -> validation (server, Pydantic-style rules)
  -> user preview + confirmation
  -> Backend API (FastAPI)
  -> Database CREATE / UPDATE (SQLite or PostgreSQL)
  -> Frontend confirmation + ledger
```

## Project structure
```
finpilot/
  app/main.py        API endpoints (extract, validate, create, update, delete, list, summary)
  app/ai.py          Gemini call, schema, prompt, AI error handling
  app/schemas.py     Schema (categories, payment methods) + validation rules
  app/db.py          Database model (transactions table)
  static/index.html  Frontend (input, preview/edit, confirm, ledger)
  tests/             Unit tests for validation
  render.yaml        Deployment config
```

## 1. Run locally
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then paste your Gemini key into .env
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

Get a free Gemini key: https://aistudio.google.com/apikey

Run tests: `python -m pytest -q`

## 2. API
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/extract` | AI extraction + validation. Returns a preview, saves nothing |
| POST | `/api/validate` | Re-validates after the user edits the preview |
| POST | `/api/transactions` | **DB create** (after confirmation; validated again on server) |
| PUT | `/api/transactions/{id}` | **DB update** |
| DELETE | `/api/transactions/{id}` | Delete |
| GET | `/api/transactions` | Ledger list |
| GET | `/api/summary` | Monthly totals by category |

## 3. Schema (AI output)
| Field | Type | Rule |
|---|---|---|
| amount | number | required, > 0, never guessed |
| currency | string | 3-letter code, default INR |
| category | enum | Food, Travel, Shopping, Bills, Health, Entertainment, Other |
| merchant | string/null | optional |
| date | YYYY-MM-DD | not in the future; missing date is flagged, then today is filled in for the user to confirm |
| payment_method | enum | Cash, UPI, Card, Other |
| is_transaction | boolean | false for text that is not an expense |
| confidence | 0-1 | shown to the user |
| missing_fields | list | fields the AI could not find |

Sample output:
```json
{"is_transaction": true, "amount": 450, "currency": "INR", "category": "Food",
 "merchant": "Dominos", "date": "2026-10-27", "payment_method": "UPI",
 "confidence": 0.95, "missing_fields": []}
```

## 4. Database
Table `transactions`: `id, amount, currency, category, merchant, txn_date, payment_method, raw_input, created_at, updated_at`.
Create: `POST /api/transactions` inserts a row after confirmation. Update: `PUT /api/transactions/{id}` edits a saved row.

## 5. Deployment (compulsory)
One service serves both backend and frontend, so **the Render URL is your deployed frontend URL**.

1. **Database:** create a free PostgreSQL on Neon (neon.tech) or Supabase. Copy the connection string.
   (Render's free disk is temporary, so SQLite data would be lost on restart. Use Postgres for the live site.)
2. Push this folder to a GitHub repository.
3. On https://render.com choose **New > Web Service**, connect the repo (or use the `render.yaml` Blueprint).
4. Build command: `pip install -r requirements.txt`
   Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment variables: `GEMINI_API_KEY`, `DATABASE_URL`, `PYTHON_VERSION=3.12.3`
6. Open the Render URL, run the test cases below on the live site, and submit that URL.
   (The free plan sleeps when idle. The first load may take about 50 seconds.)

## 6. Test cases (take a screenshot of each for the report)
| # | Type | Input | Expected result |
|---|---|---|---|
| 1 | Success | Paid 250 for auto to college today by cash | Preview valid, saved, appears in ledger |
| 2 | Success | Spent 450 rupees on pizza at Dominos yesterday using UPI | Date resolved to yesterday, saved |
| 3 | Missing field | Bought coffee | "Amount is missing", save button disabled |
| 4 | Invalid input | asdfgh | "No expense found in that text" |
| 5 | Invalid value | Edit the amount to -5 in the preview | Error shown, save blocked |
| 6 | Failed request | Set a wrong `GEMINI_API_KEY` locally | "AI service rejected the request" message |
| 7 | Update | Click Edit on a row, change the amount, update | Row changes in the ledger |

## 7. Safeguards for sensitive data
- API key is only in server environment variables, never in the browser.
- Preview and explicit confirmation before anything is written to the database.
- Server re-validates every save, so the browser is never trusted.
- Input limited to 500 characters. User text is wrapped as data in the prompt (basic prompt-injection defence).
- Frontend renders user text with `textContent` (prevents XSS).
- Do not enter bank account numbers, card numbers or passwords.

## 8. Limitations and future work
- No login, so all users share one ledger. Add authentication and per-user data.
- Voice uses the browser Web Speech API (Chrome/Edge). Server-side audio transcription could be added.
- Single currency in totals. Add currency conversion.
- Receipt photo/PDF extraction (OCR) and budget limits with alerts.
- Free AI tier has rate limits.

## 9. Report outline (10 marks)
Follow the checklist in the assignment:
1. Title, objective, problem statement, selected automation idea
2. Architecture/workflow diagram and tech stack (FastAPI, Gemini, SQLAlchemy, PostgreSQL, HTML/JS, Render)
3. Schema definition and sample AI output (section 3 above)
4. Database design and explanation of create/update (section 4)
5. Screenshots: interface, preview, successful DB update, each test case
6. Limitations and future improvements (section 8)
7. Deployed frontend URL

## 10. Viva preparation
- **Why this project?** Clear schema, easy to validate, everyday use.
- **What is schema-guided prompting?** The prompt and the API `responseSchema` define fields and types, so the model returns structured JSON and not free text.
- **How do you handle missing or invalid values?** The AI returns `null` and `missing_fields`. `validate_draft` blocks missing amount and bad dates, and warns for the rest. Nothing is invented silently.
- **Why validate again on the server?** The client can be bypassed.
- **Why preview and confirm?** Saving money data is consequential, and the AI can be wrong.
- **What happens if the AI fails?** `AIError` returns a friendly message (timeout, bad key, rate limit, invalid JSON) and the frontend shows it.
- **Which DB operations?** Create (`POST`) and update (`PUT`).
- **Why temperature 0?** For consistent extraction.
