"""Test document utilities."""

from pathlib import Path

from nclutils import ensure_lines_in_file, logger, replace_in_file


def create_test_file(parent_dir: Path) -> Path:
    """Create a test file."""
    path = parent_dir / "test.txt"
    path.write_text("""\
This is a test file.
Gallia est omnis divisa in partes tres, quarum. Curabitur blandit tempus ardua ridiculous sed magna. Quisque ut dolor gravida, placerat libero vel, euismod.

Nec dubitamus multa iter quae et nos invenerat. A communi observantia non est recedendum. Lorem ipsum dolor sit amet, consectetur adipisici elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua.
    """)
    return path


def test_fail_file_not_found(tmp_path, debug, clean_stderr) -> None:
    """Test replace_in_file."""
    logger.configure(log_level="DEBUG")
    path = tmp_path / "test.txt"
    assert not replace_in_file(path, {"no_match": "no_matches"})
    output = clean_stderr()
    assert "test.txt does not exist" in output
    assert not path.exists()


def test_replace_in_file_no_matches(tmp_path, debug) -> None:
    """Test replace_in_file."""
    path = create_test_file(tmp_path)

    replacements = {"no_match": "no_matches"}
    assert not replace_in_file(path, replacements)
    assert path.exists()


def test_replace_in_file(tmp_path, debug) -> None:
    """Test replace_in_file."""
    path = create_test_file(tmp_path)

    replacements = {"Gallia": "Foo", "this": "Bar"}
    assert replace_in_file(path, replacements)
    assert (
        path.read_text()
        == """\
This is a test file.
Foo est omnis divisa in partes tres, quarum. Curabitur blandit tempus ardua ridiculous sed magna. Quisque ut dolor gravida, placerat libero vel, euismod.

Nec dubitamus multa iter quae et nos invenerat. A communi observantia non est recedendum. Lorem ipsum dolor sit amet, consectetur adipisici elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua.
    """
    )


def test_replace_in_file_regex_no_matches(tmp_path, debug) -> None:
    """Test replace_in_file."""
    path = create_test_file(tmp_path)

    replacements = {"no_match": "no_matches"}
    assert not replace_in_file(path, replacements, use_regex=True)
    assert path.exists()


def test_replace_in_file_regex(tmp_path, debug) -> None:
    """Test replace_in_file."""
    path = create_test_file(tmp_path)

    replacements = {"^Gallia": "Foo", "[A-Za-z]est": "Bar"}
    assert replace_in_file(path, replacements, use_regex=True)
    assert (
        path.read_text()
        == """\
This is a Bar file.
Foo est omnis divisa in partes tres, quarum. Curabitur blandit tempus ardua ridiculous sed magna. Quisque ut dolor gravida, placerat libero vel, euismod.

Nec dubitamus multa iter quae et nos invenerat. A communi observantia non est recedendum. Lorem ipsum dolor sit amet, consectetur adipisici elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua.
    """
    )


def test_ensure_lines_in_file(tmp_path, debug) -> None:
    """Test ensure_lines_in_file."""
    path = create_test_file(tmp_path)
    path.write_text("some text")

    lines = ["This is a test file.", "Gallia est omnis divisa in partes tres, quarum."]
    assert ensure_lines_in_file(path, lines)

    assert (
        path.read_text()
        == """\
some text
This is a test file.
Gallia est omnis divisa in partes tres, quarum."""
    )


def test_ensure_lines_in_file_at_top(tmp_path, debug) -> None:
    """Test ensure_lines_in_file."""
    path = create_test_file(tmp_path)
    path.write_text("some text")

    lines = ["This is a test file.", "Gallia est omnis divisa in partes tres, quarum."]
    assert ensure_lines_in_file(path, lines, at_top=True)

    assert (
        path.read_text()
        == """\
Gallia est omnis divisa in partes tres, quarum.
This is a test file.
some text"""
    )


def test_ensure_lines_in_file_no_changes(tmp_path, debug) -> None:
    """Test ensure_lines_in_file."""
    path = create_test_file(tmp_path)
    path.write_text(
        "This is a test file.\nsome text\nGallia est omnis divisa in partes tres, quarum."
    )

    lines = ["This is a test file.", "Gallia est omnis divisa in partes tres, quarum."]
    assert not ensure_lines_in_file(path, lines)

    assert (
        path.read_text()
        == """\
This is a test file.\nsome text\nGallia est omnis divisa in partes tres, quarum."""
    )
