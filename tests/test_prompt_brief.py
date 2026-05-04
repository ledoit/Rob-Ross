from core.prompt_brief import genome_patch_from_prompt


def test_black_and_yellow_sets_accent_and_dark():
    p = genome_patch_from_prompt("black and yellow")
    assert p["prompt_session"]["accent_hue_center"] == 52.0
    assert p["lightness_profile"]["background_range"] == [3, 12]
    assert p["prompt_session"]["prefer_dark_theme_archetypes"] is True
    assert p["prompt_session"]["chromatic_variety"] == 0.22
    assert p["prompt_session"]["prompt_adherence"] == 0.9


def test_no_false_red_in_substring():
    # "red" must not match inside "redesigned"
    p = genome_patch_from_prompt("completely redesigned layout")
    assert "accent_hue_center" not in p["prompt_session"]


def test_two_accents_secondary_hue():
    p = genome_patch_from_prompt("black yellow orange")
    assert p["prompt_session"]["accent_secondary_hue"] == 28.0
