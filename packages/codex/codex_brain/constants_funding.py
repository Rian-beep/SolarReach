"""Five UK solar funding models — reference data shown on every pitch deck.

Source: standard UK commercial solar finance products as of 2026.
SEG = Smart Export Guarantee (export tariff for surplus generation).
"""

from __future__ import annotations

from typing import TypedDict


class FundingModel(TypedDict):
    name: str
    description: str
    monthly_payment_formula: str
    ownership_at_end: str  # "client" | "provider"
    term_years: int
    who_claims_seg: str  # "client" | "provider"
    capex_required_pct: float  # share of capex paid up-front by client (0..1)
    notes: str


FUNDING_MODELS: list[FundingModel] = [
    {
        "name": "Capital Expense",
        "description": "Outright purchase. Client pays full capex, owns the system from day one.",
        "monthly_payment_formula": "0",  # paid up-front
        "ownership_at_end": "client",
        "term_years": 0,
        "who_claims_seg": "client",
        "capex_required_pct": 1.0,
        "notes": "Best NPV. Client claims all SEG and can capital-allow against tax.",
    },
    {
        "name": "Free Install",
        "description": (
            "PPA-style. Provider funds, installs, owns, and operates. Client buys "
            "generation at a discounted unit rate via long-term Power Purchase Agreement."
        ),
        "monthly_payment_formula": "annual_kwh * ppa_rate_pence_per_kwh / 12 / 100",
        "ownership_at_end": "provider",
        "term_years": 25,
        "who_claims_seg": "provider",
        "capex_required_pct": 0.0,
        "notes": "Zero capex. Client savings ~30-40% of grid rate. Provider keeps SEG.",
    },
    {
        "name": "Lease Purchase",
        "description": "Fixed monthly lease over term, balloon transfers ownership at end.",
        "monthly_payment_formula": "(capex * (1 + apr) ** term_years - balloon) / (term_years * 12)",
        "ownership_at_end": "client",
        "term_years": 7,
        "who_claims_seg": "client",
        "capex_required_pct": 0.0,
        "notes": "Balance of cashflow + ownership. Tax-efficient.",
    },
    {
        "name": "Operational Lease",
        "description": "Pure rental. System never transferred. Off-balance-sheet treatment.",
        "monthly_payment_formula": "capex * lease_factor / 12",
        "ownership_at_end": "provider",
        "term_years": 5,
        "who_claims_seg": "client",
        "capex_required_pct": 0.0,
        "notes": "Lease payments fully tax-deductible. Client uses energy + claims SEG during term.",
    },
    {
        "name": "Hire Purchase",
        "description": "Asset finance. Client pays installments + nominal title fee at end.",
        "monthly_payment_formula": "(capex * (1 + apr) ** term_years) / (term_years * 12)",
        "ownership_at_end": "client",
        "term_years": 5,
        "who_claims_seg": "client",
        "capex_required_pct": 0.10,
        "notes": "VAT on full price up-front; capital allowances available from year 1.",
    },
]


def get_funding_model(name: str) -> FundingModel:
    for m in FUNDING_MODELS:
        if m["name"] == name:
            return m
    raise KeyError(f"Unknown funding model: {name}")
