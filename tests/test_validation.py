from datetime import date

from app.schemas import validate_draft

TODAY = date(2026, 10, 28)


def test_success_case():
    r = validate_draft({"amount": 250, "category": "Travel", "merchant": "Auto",
                        "date": "2026-10-28", "payment_method": "Cash"}, TODAY)
    assert r["valid"] and not r["errors"]


def test_missing_amount_blocks_save():
    r = validate_draft({"amount": None, "merchant": "Cafe"}, TODAY)
    assert not r["valid"]
    assert any("Amount" in e for e in r["errors"])


def test_negative_amount_rejected():
    assert not validate_draft({"amount": -5}, TODAY)["valid"]


def test_bad_date_rejected():
    assert not validate_draft({"amount": 10, "date": "28/10/2026"}, TODAY)["valid"]


def test_future_date_rejected():
    assert not validate_draft({"amount": 10, "date": "2027-01-01"}, TODAY)["valid"]


def test_unknown_category_defaults_with_warning():
    r = validate_draft({"amount": 10, "category": "Spaceships"}, TODAY)
    assert r["valid"] and r["cleaned"]["category"] == "Other" and r["warnings"]


def test_missing_date_is_flagged_not_silent():
    r = validate_draft({"amount": 10}, TODAY)
    assert r["cleaned"]["date"] == "2026-10-28"
    assert any("Date was not mentioned" in w for w in r["warnings"])
