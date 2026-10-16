from releasehub.cli import main


def test_cli_bump(capsys):
    assert main(["bump", "1.4.2", "minor"]) == 0
    assert capsys.readouterr().out.strip() == "1.5.0"


def test_cli_latest(capsys):
    assert main(["latest", "1.9.3", "1.10.0"]) == 0
    assert capsys.readouterr().out.strip() == "1.10.0"


def test_cli_invalid_version_exits_with_1(capsys):
    assert main(["bump", "banana", "patch"]) == 1
    assert "Not a valid version" in capsys.readouterr().err
