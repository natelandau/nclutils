"""Tests for pp.kv() and Emitter.kv() key/value block rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.table import Table
from rich.text import Text

from nclutils import pp
from nclutils.pp.emitter import set_default

if TYPE_CHECKING:
    from pathlib import Path

    from .conftest import RecordingEmitterFactory


class TestKvAlignment:
    """Keys are padded to the longest key's width before the separator."""

    def test_dict_aligns_keys(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify dict input renders with keys padded to widest-key width."""
        # Given an emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When kv is called with a dict
        e.kv({"Branch": "main", "Commit": "abc1234", "Duration": "3.2s"})

        # Then every key appears followed by separator and its value
        text = out.export_text()
        assert "Branch:   main" in text
        assert "Commit:   abc1234" in text
        assert "Duration: 3.2s" in text

    def test_list_of_tuples_preserves_order_and_duplicates(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify list-of-tuples input preserves order and allows duplicate keys."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When kv is called with a list of tuples (with a duplicate key)
        e.kv([("Step", "init"), ("Step", "build"), ("Step", "deploy")])

        # Then all three rows render in order
        text = out.export_text()
        assert text.count("Step:") == 3
        init_idx = text.index("init")
        build_idx = text.index("build")
        deploy_idx = text.index("deploy")
        assert init_idx < build_idx < deploy_idx

    def test_non_string_value_passes_through_str(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify non-string non-renderable values are coerced via str()."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When kv is called with int and bool values
        e.kv({"Count": 42, "Ready": True})

        # Then the values appear coerced to their str() representation
        text = out.export_text()
        assert "Count: 42" in text
        assert "Ready: True" in text

    def test_multiline_value_aligns_continuation(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify multi-line string values align continuation lines under the value column."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When kv is called with a multi-line string value
        e.kv({"Notes": "first\nsecond\nthird"})

        # Then continuation lines are indented to the value column
        text = out.export_text()
        # The value column starts at indent (2) + len("Notes") + len(": ") = 9
        cont_prefix = " " * 9
        assert f"{cont_prefix}second" in text
        assert f"{cont_prefix}third" in text

    def test_rich_renderable_value_renders_indented(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify Rich renderables render below the key, indented to the value column."""
        # Given an emitter and a Rich Table value
        e, out, _ = make_recording_emitter()
        table = Table(show_header=False)
        table.add_row("first")
        table.add_row("second")

        # When kv is called with the renderable as a value
        e.kv({"Output": table})

        # Then the key appears alone on the first line and the table content is
        # indented under the value column on subsequent lines.
        text = out.export_text()
        lines = text.splitlines()
        # The first non-empty line should contain the key and the separator.
        assert any("Output:" in line for line in lines)
        # The table rows should appear indented at the value column or beyond.
        cont_prefix = " " * (2 + len("Output") + len(": "))
        assert any(line.startswith(cont_prefix) and "first" in line for line in lines)
        assert any(line.startswith(cont_prefix) and "second" in line for line in lines)


class TestKvQuiet:
    """`quiet=True` suppresses kv output."""

    def test_quiet_suppresses_kv(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify kv() emits nothing to console when quiet=True is set."""
        # Given a quiet emitter
        e, out, _ = make_recording_emitter(quiet=True)

        # When kv is called
        e.kv({"a": "1"})

        # Then no kv content appears on the console
        text = out.export_text()
        assert "a:" not in text


class TestKvLogfile:
    """Each kv pair is recorded as an INFO record with column alignment."""

    def test_logfile_records_each_pair(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify the logfile contains one INFO record per kv pair with aligned values."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When kv is called with mismatched-width keys so the alignment math is exercised
        e.kv({"A": "short", "LongerKey": "longer_value"})

        # Then both pairs are recorded and the value column lines up across rows.
        # cell_width = len("LongerKey") + len(": ") == 11, so the short key is padded
        # with 9 spaces between "A:" and its value.
        contents = logfile.read_text()
        assert "A:         short" in contents
        assert "LongerKey: longer_value" in contents

        # And the value column begins at the same string offset on each line.
        a_line = next(line for line in contents.splitlines() if "A:" in line)
        long_line = next(line for line in contents.splitlines() if "LongerKey:" in line)
        assert a_line.index("short") == long_line.index("longer_value")

    def test_logfile_records_under_quiet(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify kv pairs are recorded to the logfile even when quiet=True suppresses console."""
        # Given a quiet emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(quiet=True, logfile=logfile)

        # When kv is called
        e.kv({"Branch": "main"})

        # Then the audit trail still records the pair
        contents = logfile.read_text()
        assert "Branch: main" in contents

    def test_logfile_multiline_value_records_each_line(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify multi-line values emit one logfile record per visual line."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When kv is called with a multi-line value
        e.kv({"Notes": "first\nsecond"})

        # Then each line appears in the log
        contents = logfile.read_text()
        assert "Notes: first" in contents
        assert "second" in contents


class TestKvEmpty:
    """Empty input is a no-op."""

    @pytest.mark.parametrize("items", [{}, []])
    def test_empty_input_is_noop(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
        items: dict | list,
    ) -> None:
        """Verify empty dict and empty list input emit nothing to console or logfile."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, out, _ = make_recording_emitter(logfile=logfile)

        # When kv is called with empty input
        e.kv(items)

        # Then no console output is produced and no logfile record is written
        text = out.export_text()
        assert text.strip() == ""
        assert not logfile.exists() or logfile.read_text() == ""


class TestKvMarkup:
    """`markup=True` parses Rich markup in values; keys are always escaped."""

    def test_markup_true_parses_value_markup(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify markup=True parses Rich markup in values."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When kv is called with markup=True and a markup-containing value
        e.kv({"Status": "[bold]ok[/]"}, markup=True)

        # Then the literal markup tags are NOT in the rendered text
        text = out.export_text()
        assert "Status:" in text
        assert "ok" in text
        assert "[bold]" not in text

    def test_markup_default_escapes_value(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify default markup=False escapes Rich markup in values."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When kv is called without markup and a value containing brackets
        e.kv({"Path": "[user]/file.txt"})

        # Then the literal brackets appear in the output
        text = out.export_text()
        assert "[user]/file.txt" in text

    def test_markup_in_key_is_always_escaped(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify keys are always rendered as literal text even with markup=True."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When kv is called with a key containing markup-like brackets and markup=True
        e.kv({"[bold]key[/]": "value"}, markup=True)

        # Then the literal key text appears verbatim
        text = out.export_text()
        assert "[bold]key[/]" in text


class TestKvWithTextValue:
    """`Text` instances pass through as values with their styling preserved."""

    def test_text_value_renders_in_console(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a rich.text.Text value renders its content in console output."""
        # Given an emitter wired to a recording stdout console
        e, out, _ = make_recording_emitter()

        # When kv is called with a Text value
        e.kv({"Status": Text("ok", style="bold green")})

        # Then the plain content appears in the rendered output
        text = out.export_text()
        assert "Status:" in text
        assert "ok" in text

    def test_text_value_recorded_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify a rich.text.Text value is recorded as plain text in the logfile."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When kv is called with a Text value
        e.kv({"Status": Text("ok", style="bold green")})

        # Then the plain content appears in the logfile
        contents = logfile.read_text()
        assert "Status: ok" in contents


class TestModuleLevelKv:
    """pp.kv() forwards to the default emitter."""

    @pytest.mark.usefixtures("isolated_default")
    def test_module_level_kv_renders(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify pp.kv() routes through the default emitter."""
        # Given an isolated default emitter
        e, out, _ = make_recording_emitter()
        set_default(e)

        # When pp.kv is called
        pp.kv({"a": "1"})

        # Then the pair appears in the recorded output
        text = out.export_text()
        assert "a: 1" in text
