"""文档与代码一致性：docs/data-model.md 的字段表必须与 schema.py 一致。"""

import re

from hot_repos import config, schema

DOC = (config.ROOT / "docs" / "data-model.md").read_text(encoding="utf-8")


def documented_fields(heading: str) -> list[str]:
    section = DOC.split(f"### {heading}\n", 1)[1].split("\n#", 1)[0]
    return re.findall(r"^\| `(\w+)` \|", section, flags=re.M)


def test_parquet_field_tables_match_schema():
    for name, table_schema in schema.TABLES.items():
        assert documented_fields(f"{name}.parquet") == table_schema.names, name


def test_trending_field_table_matches_schema():
    assert documented_fields("trending/YYYY-MM-DD.parquet") == schema.TRENDING.names


def test_classification_field_table_matches_schema():
    assert documented_fields("classification.parquet") == schema.CLASSIFICATION.names


def test_manifest_field_table_matches_schema():
    assert documented_fields("manifest.json") == list(schema.MANIFEST_FIELDS)


def test_files_listed_in_overview_exist_in_config():
    for filename in (
        config.REPOS_FILE,
        config.STAR_WEEKS_FILE,
        config.RANK_HISTORY_FILE,
        config.MANIFEST_FILE,
        config.CLASSIFICATION_FILE,
        config.TAXONOMY_FILE,
    ):
        assert f"`{filename}`" in DOC


def _markdown_files():
    return [config.ROOT / "README.md", *sorted((config.ROOT / "docs").glob("*.md"))]


def test_relative_markdown_links_resolve():
    link = re.compile(r"\]\((?!https?:|mailto:|#)([^)#\s]+)(?:#[^)]*)?\)")
    broken = []
    for path in _markdown_files():
        for target in link.findall(path.read_text(encoding="utf-8")):
            if not (path.parent / target).resolve().exists():
                broken.append(f"{path.name}: {target}")
    assert not broken


def test_documented_cli_flags_exist():
    from hot_repos import cli

    parser = cli.build_parser()
    subparsers = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    real = {
        opt for sub in subparsers.choices.values() for a in sub._actions for opt in a.option_strings
    }
    text = (config.ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`(--[a-z][a-z-]*)", text))
    assert documented, "操作手册应当列出命令行参数"
    assert documented <= real, documented - real


def test_documented_commands_are_known():
    from hot_repos import cli

    parser = cli.build_parser()
    subparsers = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    text = "".join(p.read_text(encoding="utf-8") for p in _markdown_files())
    for command in set(re.findall(r"hot-repos (\w+)", text)):
        assert command in subparsers.choices, command
