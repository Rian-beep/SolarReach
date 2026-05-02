"""Tests for decision-maker inference — priority logic is deterministic without Anthropic."""

import pytest


def test_role_priority_cfo_beats_md():
    from codex_brain.generators.org_chart import role_priority
    assert role_priority("CFO") < role_priority("Managing Director")
    assert role_priority("CFO") < role_priority("CEO")


def test_role_priority_full_hierarchy():
    from codex_brain.generators.org_chart import role_priority
    # CFO → Finance Dir → MD → CEO → Head of Sustainability → COO → Property Director → Estates Manager
    order = [
        "CFO",
        "Finance Director",
        "Managing Director",
        "CEO",
        "Head of Sustainability",
        "COO",
        "Property Director",
        "Estates Manager",
    ]
    priorities = [role_priority(r) for r in order]
    assert priorities == sorted(priorities), f"hierarchy not strictly increasing: {priorities}"


def test_role_priority_unknown_role_lower_priority():
    from codex_brain.generators.org_chart import role_priority
    assert role_priority("Receptionist") > role_priority("CFO")


def test_role_priority_case_insensitive():
    from codex_brain.generators.org_chart import role_priority
    assert role_priority("cfo") == role_priority("CFO")
    assert role_priority("Chief Financial Officer") == role_priority("CFO")


def test_pick_best_director_chooses_cfo_over_director():
    from codex_brain.generators.org_chart import pick_best_director
    directors = [
        {"name": "A One", "role": "Director"},
        {"name": "B Two", "role": "CFO"},
        {"name": "C Three", "role": "Estates Manager"},
    ]
    best = pick_best_director(directors)
    assert best["name"] == "B Two"


def test_pick_best_director_falls_back_to_first_when_all_generic():
    from codex_brain.generators.org_chart import pick_best_director
    directors = [
        {"name": "A One", "role": "Director"},
        {"name": "B Two", "role": "Director"},
    ]
    best = pick_best_director(directors)
    assert best is not None
    assert best["name"] in {"A One", "B Two"}


def test_confidence_for_specific_role_is_high():
    from codex_brain.generators.org_chart import confidence_for_role
    assert confidence_for_role("CFO") >= 0.85
    assert confidence_for_role("Finance Director") >= 0.8


def test_confidence_for_generic_director_below_07():
    from codex_brain.generators.org_chart import confidence_for_role
    # "Director" is too generic — confidence must be < 0.7
    assert confidence_for_role("Director") < 0.7


def test_pick_best_director_empty_list():
    from codex_brain.generators.org_chart import pick_best_director
    assert pick_best_director([]) is None
