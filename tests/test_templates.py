from utils.templates import (
    get_active_set,
    get_template_data,
)


def test_get_template_data_standard():
    """Test loading and mapping keys for the 'standard' icon set."""
    tmpl = get_template_data("standard")
    assert tmpl is not None
    assert tmpl["buttons_per_row"] == 5
    assert tmpl["show_mgmt"] is True
    assert len(tmpl["options"]) == 3

    # Check key mappings
    opts = {o["id"]: o for o in tmpl["options"]}
    assert "i_m_coming" in opts
    assert opts["i_m_coming"]["label_key"] == "BTN_ACCEPT"
    assert opts["i_m_coming"]["list_label_key"] == "RSVP_ACCEPTED"
    assert opts["i_m_coming"]["positive"] is True

    assert "maybe" in opts
    assert opts["maybe"]["label_key"] == "BTN_TENTATIVE"
    assert opts["maybe"]["positive"] is False

    assert "not_coming" in opts
    assert opts["not_coming"]["label_key"] == "BTN_DECLINE"
    assert opts["not_coming"]["positive"] is False

def test_get_template_data_mmo():
    """Test loading and option properties for the 'mmo' raid template."""
    tmpl = get_template_data("mmo")
    assert tmpl is not None
    assert tmpl["show_mgmt"] is False
    assert tmpl["positive_count"] == 3
    assert len(tmpl["options"]) == 5

    opts = {o["id"]: o for o in tmpl["options"]}
    assert opts["tank"]["list_label_key"] == "RSVP_TANK"
    assert opts["heal"]["list_label_key"] == "RSVP_HEAL"
    assert opts["dps"]["list_label_key"] == "RSVP_DPS"

def test_get_template_data_survey_and_teams():
    """Test 'survey' and 'teams' templates."""
    survey = get_template_data("survey")
    assert survey is not None
    assert len(survey["options"]) == 2
    assert survey["positive_count"] == 2

    teams = get_template_data("teams")
    assert teams is not None
    assert teams["buttons_per_row"] == 3
    assert len(teams["options"]) == 5

def test_get_template_data_nonexistent():
    """Test requesting a non-existent template returns None."""
    assert get_template_data("unknown_template_xyz") is None

def test_get_active_set_fallback():
    """Test get_active_set returns fallback empty structure for unknown keys."""
    res = get_active_set("non_existent_key_999")
    assert isinstance(res, dict)
    assert res == {"options": []}
