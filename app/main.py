"""FinPilot backend: FastAPI. Serves the API and the frontend (static/index.html)."""
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai import AIError, extract_transaction
from .db import Transaction, get_db
from .schemas import CATEGORIES, PAYMENT_METHODS, Draft, ExtractRequest, SaveRequest, validate_draft

app = FastAPI(title="FinPilot", description="Personal finance intelligence: text to ledger")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> date:
    return datetime.now(IST).date()


@app.exception_handler(AIError)
async def ai_error_handler(_: Request, exc: AIError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {"categories": CATEGORIES, "payment_methods": PAYMENT_METHODS}


# ---- Step 1: AI extraction -> schema-guided JSON -> validation (preview only, nothing saved) ----
@app.post("/api/extract")
async def extract(req: ExtractRequest):
    text = req.text.strip()
    if len(text) < 3:
        raise HTTPException(422, "Please type or say an expense, e.g. 'Spent 450 on pizza by UPI'.")
    today = today_ist()
    ai_out = await extract_transaction(text, today.isoformat(), today.strftime("%A"))

    if not ai_out.get("is_transaction"):
        raise HTTPException(
            422, "No expense found in that text. Try something like 'Paid 250 for auto by cash today'."
        )

    result = validate_draft(ai_out, today)
    return {
        "draft": result["cleaned"],
        "valid": result["valid"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "confidence": ai_out.get("confidence"),
        "missing_fields": ai_out.get("missing_fields", []),
    }


# ---- Re-validate after the user edits the preview ----
@app.post("/api/validate")
def validate(draft: Draft):
    result = validate_draft(draft.model_dump(), today_ist())
    return {"draft": result["cleaned"], **{k: result[k] for k in ("valid", "errors", "warnings")}}


# ---- Step 2: DATABASE CREATE (only after the user confirms) ----
@app.post("/api/transactions", status_code=201)
def create_transaction(req: SaveRequest, db: Session = Depends(get_db)):
    result = validate_draft(req.model_dump(), today_ist())
    if not result["valid"]:  # never trust the client: validate again on the server
        raise HTTPException(422, " ".join(result["errors"]))
    c = result["cleaned"]
    txn = Transaction(
        amount=c["amount"], currency=c["currency"], category=c["category"],
        merchant=c["merchant"], txn_date=date.fromisoformat(c["date"]),
        payment_method=c["payment_method"], raw_input=req.raw_input,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn.to_dict()


# ---- DATABASE UPDATE ----
@app.put("/api/transactions/{txn_id}")
def update_transaction(txn_id: int, req: SaveRequest, db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found.")
    result = validate_draft(req.model_dump(), today_ist())
    if not result["valid"]:
        raise HTTPException(422, " ".join(result["errors"]))
    c = result["cleaned"]
    txn.amount, txn.currency, txn.category = c["amount"], c["currency"], c["category"]
    txn.merchant, txn.payment_method = c["merchant"], c["payment_method"]
    txn.txn_date = date.fromisoformat(c["date"])
    db.commit()
    db.refresh(txn)
    return txn.to_dict()


@app.delete("/api/transactions/{txn_id}")
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found.")
    db.delete(txn)
    db.commit()
    return {"deleted": txn_id}


@app.get("/api/transactions")
def list_transactions(db: Session = Depends(get_db)):
    rows = db.scalars(select(Transaction).order_by(Transaction.txn_date.desc(), Transaction.id.desc()).limit(200))
    return [r.to_dict() for r in rows]


@app.get("/api/summary")
def summary(db: Session = Depends(get_db)):
    first = today_ist().replace(day=1)
    rows = db.execute(
        select(Transaction.category, func.sum(Transaction.amount))
        .where(Transaction.txn_date >= first)
        .group_by(Transaction.category)
    ).all()
    by_cat = {cat: round(total, 2) for cat, total in rows}
    return {"month_start": first.isoformat(), "total": round(sum(by_cat.values()), 2), "by_category": by_cat}


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
