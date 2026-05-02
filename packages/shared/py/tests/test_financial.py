"""Tests for solarreach_shared financial + compliance helpers."""

from __future__ import annotations

import pytest

from solarreach_shared import constants
from solarreach_shared.compliance import hash_recipient, is_live_outbound
from solarreach_shared.financial import (
    annual_saving_gbp,
    capex,
    composite_score,
    npv_25yr,
    payback_years,
    roi_gate,
)


# --- composite_score ---

def test_composite_score_max():
    assert composite_score(1.0, 1.0, 1.0) == 100


def test_composite_score_min():
    assert composite_score(0.0, 0.0, 0.0) == 0


def test_composite_score_weighting():
    # 0.8*0.5 + 0.6*0.3 + 0.4*0.2 = 0.66 -> 66
    assert composite_score(0.8, 0.6, 0.4) == 66


def test_composite_score_clamps_high():
    assert composite_score(2.0, 2.0, 2.0) == 100


def test_composite_score_clamps_low():
    assert composite_score(-1.0, -1.0, -1.0) == 0


# --- roi_gate ---

def test_roi_gate_threshold_default_passes():
    assert roi_gate(70) is True
    assert roi_gate(85) is True


def test_roi_gate_threshold_default_fails():
    assert roi_gate(69) is False
    assert roi_gate(0) is False


def test_roi_gate_custom_threshold():
    assert roi_gate(80, threshold=75) is True
    assert roi_gate(74, threshold=75) is False


# --- capex ---

def test_capex_zero_panels_zero():
    assert capex(0) == 0.0


def test_capex_positive_with_panels():
    n_panels = 24
    rated_kw = n_panels * constants.PANEL_RATED_KW
    base = (
        n_panels * constants.PANEL_UNIT_COST_GBP
        + rated_kw * constants.INSTALL_COST_PER_KW_GBP
    )
    expected = base * (1 + constants.INSTALLER_MARGIN_PCT)
    assert capex(n_panels) == pytest.approx(expected, rel=1e-6)


# --- annual_saving / payback_years ---

def test_annual_saving_positive():
    s = annual_saving_gbp(10000.0)
    # 5000*0.27 + 5000*0.15 = 1350+750 = 2100
    assert s == pytest.approx(2100.0, rel=1e-6)


def test_annual_saving_zero():
    assert annual_saving_gbp(0) == 0.0


def test_payback_years_basic():
    assert payback_years(20000.0, 2000.0) == pytest.approx(10.0)


def test_payback_years_zero_saving_returns_inf():
    assert payback_years(20000.0, 0.0) == float("inf")


def test_payback_years_negative_saving_returns_inf():
    assert payback_years(20000.0, -100.0) == float("inf")


# --- npv_25yr ---

def test_npv_25yr_positive_for_good_project():
    val = npv_25yr(capex_gbp=10000.0, annual_saving_gbp=2500.0)
    assert val > 0


def test_npv_25yr_negative_for_bad_project():
    val = npv_25yr(capex_gbp=100000.0, annual_saving_gbp=500.0)
    assert val < 0


def test_npv_25yr_finite_number():
    val = npv_25yr(capex_gbp=20000.0, annual_saving_gbp=2000.0)
    assert isinstance(val, float)
    assert val == val  # not NaN
    assert abs(val) < 1e9


# --- hash_recipient ---

def test_hash_recipient_deterministic():
    a = hash_recipient("user@example.com")
    b = hash_recipient("user@example.com")
    assert a == b
    assert len(a) == 64


def test_hash_recipient_normalises_case_and_whitespace():
    a = hash_recipient("User@Example.com")
    b = hash_recipient("  user@example.com  ")
    c = hash_recipient("user@example.com")
    assert a == b == c


def test_hash_recipient_distinguishes_different_emails():
    assert hash_recipient("a@example.com") != hash_recipient("b@example.com")


# --- is_live_outbound ---

def test_is_live_outbound_default_false(monkeypatch):
    monkeypatch.delenv("SOLARREACH_LIVE_OUTBOUND", raising=False)
    assert is_live_outbound() is False


def test_is_live_outbound_truthy(monkeypatch):
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("SOLARREACH_LIVE_OUTBOUND", truthy)
        assert is_live_outbound() is True


def test_is_live_outbound_falsy(monkeypatch):
    for falsy in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("SOLARREACH_LIVE_OUTBOUND", falsy)
        assert is_live_outbound() is False
