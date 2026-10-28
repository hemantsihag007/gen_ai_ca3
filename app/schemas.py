"""Schema definition + validation rules (the 'VALIDATION' step of the workflow)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Health", "Entertainment", "Other"]
PAYMENT_METHODS = ["Cash", "UPI", "Card", "Other"]
MAX_AMOUNT = 10_000_000


class ExtractRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class Draft(BaseModel):
    """Fields the user can preview/edit and then save. Everything optional so we can
    report *what* is missing instead of failing with a generic error."""
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    category: Optional[str] = None
    merchant: Optional[str] = None
    date: Optional[str] = None
    payment_method: Optional[str] = None


class SaveRequest(Draft):
    raw_input: Optional[str] = Field(default=None, max_length=500)


def _clean_text(value, limit: int) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value[:limit] if value else None


def validate_draft(raw: dict, today: date) -> dict:
    """Return {valid, errors, warnings, cleaned}. Errors block saving; warnings do not.
    Missing values are reported, never silently invented."""
    errors: list[str] = []
    warnings: list[str] = []
    cleaned: dict = {}

    # amount (required)
    amount = raw.get("amount")
    if amount in (None, ""):
        amount = None
        errors.append("Amount is missing. Enter how much was spent.")
    else:
        try:
            amount = round(float(amount), 2)
            if amount <= 0:
                errors.append("Amount must be greater than 0.")
            elif amount > MAX_AMOUNT:
                errors.append("Amount looks too large. Check for extra zeros.")
        except (TypeError, ValueError):
            amount = None
            errors.append("Amount is not a valid number.")
    cleaned["amount"] = amount

    # currency
    currency = (_clean_text(raw.get("currency"), 3) or "INR").upper()
    if len(currency) != 3 or not currency.isalpha():
        warnings.append("Currency code was invalid, so INR is used.")
        currency = "INR"
    cleaned["currency"] = currency

    # category (enum)
    category = _clean_text(raw.get("category"), 30)
    match = next((c for c in CATEGORIES if category and c.lower() == category.lower()), None)
    if match is None:
        warnings.append("Category not recognised. Set to Other. Change it if needed.")
        match = "Other"
    cleaned["category"] = match

    # merchant (optional)
    merchant = _clean_text(raw.get("merchant"), 120)
    if merchant is None:
        warnings.append("Merchant was not mentioned.")
    cleaned["merchant"] = merchant

    # date (required, YYYY-MM-DD, not in the future)
    date_str = _clean_text(raw.get("date"), 10)
    if date_str is None:
        warnings.append("Date was not mentioned. Today's date is filled in. Please confirm it.")
        date_str = today.isoformat()
    else:
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            if parsed > today:
                errors.append("Date is in the future.")
            elif parsed.year < 2000:
                errors.append("Date is too old.")
        except ValueError:
            errors.append("Date must be in YYYY-MM-DD format.")
    cleaned["date"] = date_str

    # payment method (enum)
    pm = _clean_text(raw.get("payment_method"), 20)
    pm_match = next((p for p in PAYMENT_METHODS if pm and p.lower() == pm.lower()), None)
    if pm_match is None:
        warnings.append("Payment method not mentioned or unknown. Set to Other.")
        pm_match = "Other"
    cleaned["payment_method"] = pm_match

    return {"valid": not errors, "errors": errors, "warnings": warnings, "cleaned": cleaned}
