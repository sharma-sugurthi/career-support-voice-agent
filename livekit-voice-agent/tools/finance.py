"""Money math for study/career budgets.

All arithmetic happens in Python, never in the model - an LLM doing currency
math is a hallucination vector. Exchange rates come from the free, keyless
Frankfurter API (European Central Bank data) and are always returned with
their source and date.
"""
from datetime import datetime, timezone

import httpx

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


async def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert an amount between currencies at the latest ECB reference rate.
    Returns {converted, rate, rate_date, source}. Raises on network errors or
    unknown currency codes - callers speak the failure, never guess a rate."""
    from_currency = from_currency.strip().upper()
    to_currency = to_currency.strip().upper()
    if from_currency == to_currency:
        return {
            "converted": round(float(amount), 2),
            "rate": 1.0,
            "rate_date": datetime.now(timezone.utc).date().isoformat(),
            "source": "same currency",
        }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            FRANKFURTER_URL, params={"base": from_currency, "symbols": to_currency}
        )
        resp.raise_for_status()
        data = resp.json()

    rate = data["rates"][to_currency]
    return {
        "converted": round(float(amount) * rate, 2),
        "rate": rate,
        "rate_date": data["date"],
        "source": "European Central Bank via frankfurter.dev",
    }


def compute_budget(items: list[dict]) -> dict:
    """Total a list of {label, amount} line items deterministically.
    Returns {total, items, count}. Rejects malformed items loudly."""
    cleaned = []
    total = 0.0
    for i, item in enumerate(items):
        try:
            label = str(item["label"]).strip()
            amount = float(item["amount"])
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Budget item {i} is malformed ({item!r}): {e}") from e
        cleaned.append({"label": label, "amount": round(amount, 2)})
        total += amount
    return {"total": round(total, 2), "items": cleaned, "count": len(cleaned)}
