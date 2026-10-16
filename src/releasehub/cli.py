"""Command line interface:  releasehub bump 1.4.2 minor   |   releasehub latest 1.9.3 1.10.0"""
import argparse
import sys

from releasehub.version import InvalidVersionError, Version, latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="releasehub", description="Version helper")
    commands = parser.add_subparsers(dest="command", required=True)

    bump = commands.add_parser("bump", help="print the next version")
    bump.add_argument("version")
    bump.add_argument("part", choices=["major", "minor", "patch"])

    newest = commands.add_parser("latest", help="print the newest of several versions")
    newest.add_argument("versions", nargs="+")

    args = parser.parse_args(argv)
    try:
        if args.command == "bump":
            print(Version.parse(args.version).bump(args.part))
        else:
            print(latest(args.versions))
    except InvalidVersionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1          # non-zero exit code = failure (scripts and CI can detect it)
    return 0


if __name__ == "__main__":
    sys.exit(main())
