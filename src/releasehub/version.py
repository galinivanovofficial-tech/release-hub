"""Semantic versioning: MAJOR.MINOR.PATCH (https://semver.org).

MAJOR: breaking change       1.4.2 -> 2.0.0
MINOR: new feature            1.4.2 -> 1.5.0
PATCH: bug fix                1.4.2 -> 1.4.3
"""
import re
from dataclasses import dataclass

SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class InvalidVersionError(ValueError):
    """Raised when a string is not a valid MAJOR.MINOR.PATCH version."""


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> "Version":
        """'1.4.2' or 'v1.4.2' -> Version(1, 4, 2)."""
        match = SEMVER.fullmatch(text.strip().removeprefix("v"))
        if not match:
            raise InvalidVersionError(f"Not a valid version: {text!r}")
        major, minor, patch = (int(part) for part in match.groups())
        return cls(major, minor, patch)

    def bump(self, part: str) -> "Version":
        """Return the NEXT version. The original is never changed (frozen = immutable)."""
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, 0)
        if part == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"part must be major, minor or patch, not {part!r}")

    def is_compatible_with(self, other: "Version") -> bool:
        """Same MAJOR version = no breaking changes between them."""
        return self.major == other.major

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def latest(versions: list[str]) -> Version:
    """Newest version. Compares NUMBERS, so 1.10.0 is newer than 1.9.3."""
    if not versions:
        raise ValueError("no versions given")
    return max(Version.parse(v) for v in versions)
