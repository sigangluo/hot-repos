import pytest

from hot_repos import cli


def test_fetch_requires_board_size(capsys):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["fetch"])


@pytest.mark.parametrize("bad", ["0", "-3", "x"])
def test_fetch_rejects_invalid_board_size(bad):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["fetch", "--top", bad])


def test_validate_command_reports_problems(tmp_path, capsys):
    assert cli.main(["validate", "--data-dir", str(tmp_path)]) == 1
    assert "文件不存在" in capsys.readouterr().err


def test_validate_command_passes_on_valid_data(dataset, capsys):
    assert cli.main(["validate", "--data-dir", str(dataset)]) == 0
    assert "通过" in capsys.readouterr().out
