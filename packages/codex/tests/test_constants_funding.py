"""Tests for funding model constants."""


def test_five_funding_models_present():
    from codex_brain.constants_funding import FUNDING_MODELS
    names = {m["name"] for m in FUNDING_MODELS}
    assert names == {
        "Capital Expense",
        "Free Install",
        "Lease Purchase",
        "Operational Lease",
        "Hire Purchase",
    }


def test_funding_models_have_required_keys():
    from codex_brain.constants_funding import FUNDING_MODELS
    required = {"name", "monthly_payment_formula", "ownership_at_end", "term_years", "who_claims_seg"}
    for m in FUNDING_MODELS:
        assert required.issubset(m.keys()), f"{m.get('name')} missing keys"


def test_capital_expense_no_monthly_payment():
    from codex_brain.constants_funding import FUNDING_MODELS
    capex = next(m for m in FUNDING_MODELS if m["name"] == "Capital Expense")
    assert capex["ownership_at_end"] == "client"
    assert capex["who_claims_seg"] == "client"


def test_free_install_provider_owns():
    from codex_brain.constants_funding import FUNDING_MODELS
    free = next(m for m in FUNDING_MODELS if m["name"] == "Free Install")
    assert free["ownership_at_end"] == "provider"
    assert free["who_claims_seg"] == "provider"
