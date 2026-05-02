"""
SolarReach Codex Brain — Funding models reference data.
5 canonical models included in every pitch deck (slide 7).
"""

FUNDING_MODELS: list[dict] = [
    {
        "name": "Capital Expense",
        "short": "CAPEX",
        "headline": "Own it outright",
        "description": (
            "The company purchases the system upfront. Full ownership from day one, "
            "maximum long-term ROI, eligible for Enhanced Capital Allowances (ECAs) "
            "and 100% first-year tax write-off under AIA."
        ),
        "pros": [
            "Highest 25yr NPV",
            "Full AIA tax benefit",
            "No ongoing finance cost",
        ],
        "cons": [
            "Upfront cash outlay",
            "Balance sheet impact",
        ],
        "typical_payback_yrs": "6–9",
    },
    {
        "name": "Free Install",
        "short": "PPA",
        "headline": "£0 upfront — pay per kWh",
        "description": (
            "A Power Purchase Agreement: the installer owns the system, the company "
            "buys electricity at a fixed below-market rate (typically 12–15p/kWh). "
            "No upfront cost, instant saving, no maintenance liability."
        ),
        "pros": [
            "Zero capex",
            "Immediate bill reduction",
            "Maintenance included",
        ],
        "cons": [
            "Lower long-term saving vs ownership",
            "20yr contract commitment",
        ],
        "typical_payback_yrs": "Immediate (no outlay)",
    },
    {
        "name": "Lease Purchase",
        "short": "LEASE",
        "headline": "Fixed monthly, own at end",
        "description": (
            "An asset finance lease spread over 5–10 years. Monthly payments "
            "are treated as operating expenditure. Ownership transfers at the end "
            "of the term for a nominal final payment. Off-balance-sheet under IFRS 16."
        ),
        "pros": [
            "Preserves working capital",
            "OpEx treatment",
            "Ownership at end",
        ],
        "cons": [
            "Interest cost over term",
            "Requires credit approval",
        ],
        "typical_payback_yrs": "8–12",
    },
    {
        "name": "Operational Lease",
        "short": "OP LEASE",
        "headline": "Rent the system — hand back at end",
        "description": (
            "Pure rental: fixed monthly payments, no ownership at the end. "
            "Full OpEx treatment — payments are 100% tax deductible. "
            "System upgraded at end of term. Ideal for companies that cycle "
            "capital assets on a fixed schedule."
        ),
        "pros": [
            "Fully tax deductible",
            "Technology refresh at end",
            "Lowest monthly payment",
        ],
        "cons": [
            "No asset at end of term",
            "Higher total cost of ownership",
        ],
        "typical_payback_yrs": "N/A (ongoing OpEx)",
    },
    {
        "name": "Hire Purchase",
        "short": "HP",
        "headline": "Finance + own from day one",
        "description": (
            "Hire Purchase: the company pays a deposit then fixed monthly instalments. "
            "The asset appears on the balance sheet from day one, so the business "
            "can claim capital allowances immediately. Ownership is automatic on "
            "final payment. Most similar to CAPEX in financial treatment."
        ),
        "pros": [
            "Capital allowance from day one",
            "Low deposit option",
            "Fixed rate protection",
        ],
        "cons": [
            "On balance sheet",
            "Interest cost",
        ],
        "typical_payback_yrs": "7–10",
    },
]
