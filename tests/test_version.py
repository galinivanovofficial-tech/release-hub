import pytest

from releasehub import InvalidVersionError, Version, latest


def test_parse():
    assert Version.parse("1.4.2") == Version(1, 4, 2)


def test_parse_accepts_v_prefix_and_spaces():
    assert Version.parse(" v2.0.10 ") == Version(2, 0, 10)


@pytest.mark.parametrize("bad", ["1.4", "1.4.2.7", "abc", "", "1.x.0", "-1.0.0"])
def test_parse_rejects_invalid(bad):
    with pytest.raises(InvalidVersionError):
        Version.parse(bad)


@pytest.mark.parametrize("part, expected", [
    ("patch", "1.4.3"),
    ("minor", "1.5.0"),
    ("major", "2.0.0"),
])
def test_bump(part, expected):
    assert str(Version.parse("1.4.2").bump(part)) == expected


def test_bump_does_not_change_original():
    v = Version(1, 4, 2)
    v.bump("major")
    assert v == Version(1, 4, 2)


def test_bump_rejects_unknown_part():
    with pytest.raises(ValueError):
        Version(1, 0, 0).bump("huge")


def test_numeric_ordering_not_text():
    # As TEXT "1.10.0" < "1.9.3" (because '1' < '9'). As VERSIONS 1.10.0 is newer.
    assert "1.10.0" < "1.9.3"
    assert Version.parse("1.10.0") > Version.parse("1.9.3")


def test_latest():
    assert str(latest(["1.2.0", "1.10.0", "1.9.3"])) == "1.10.0"


def test_latest_empty():
    with pytest.raises(ValueError):
        latest([])


def test_compatibility():
    assert Version(1, 2, 0).is_compatible_with(Version(1, 9, 9))
    assert not Version(1, 9, 9).is_compatible_with(Version(2, 0, 0))
