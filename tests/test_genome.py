from core.genome import default_genome, diff_genomes, merge_genomes, versioned_update


def test_default_genome_keys_present():
    g = default_genome()
    for key in [
        "version",
        "created",
        "last_modified",
        "hue_strategy",
        "contrast_philosophy",
        "saturation_profile",
        "lightness_profile",
    ]:
        assert key in g


def test_diff_genomes_detects_change():
    old = {"a": 1, "b": {"c": 2}}
    new = {"a": 1, "b": {"c": 3}}
    diffs = diff_genomes(old, new)
    assert len(diffs) == 1
    assert diffs[0]["path"] == "b.c"


def test_merge_genomes_collects_conflicts():
    base = {"hue_strategy": {"interval_method": "golden_ratio"}}
    incoming = {"hue_strategy": {"interval_method": "fibonacci"}}
    merged, conflicts = merge_genomes(base, incoming)
    assert merged["hue_strategy"]["interval_method"] == "fibonacci"
    assert len(conflicts) == 1


def test_versioned_update_bumps_patch():
    current = default_genome()
    current["version"] = "1.2.3"
    updated = versioned_update(current, {"emotional_register": {"primary": "calm"}})
    assert updated["version"] == "1.2.4"
