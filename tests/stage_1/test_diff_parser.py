"""Tests for the unified-diff parser.

Pins down the contract before implementation per the TDD workflow in
v1_plan.md §9.3.
"""

from __future__ import annotations

import pytest

from ai_code_review.diff.parser import parse_unified_diff
from ai_code_review.models.diff import FileChange

SIMPLE_DIFF = """\
diff --git a/foo/bar.py b/foo/bar.py
index 0000001..0000002 100644
--- a/foo/bar.py
+++ b/foo/bar.py
@@ -1,3 +1,4 @@
 line one
 line two
+inserted line
 line three
"""

MULTI_FILE_DIFF = """\
diff --git a/a.py b/a.py
index 0000001..0000002 100644
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
-removed
+added
 ctx
diff --git a/b.go b/b.go
index 0000003..0000004 100644
--- a/b.go
+++ b/b.go
@@ -1,1 +1,2 @@
 line one
+line two
"""

NEW_FILE_DIFF = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..0000001
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+first line
+second line
"""

DELETED_FILE_DIFF = """\
diff --git a/old.py b/old.py
deleted file mode 100644
index 0000001..0000000
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-line one
-line two
"""


class TestBasicParse:
    def test_returns_one_filechange_for_one_file(self) -> None:
        changes = parse_unified_diff(SIMPLE_DIFF)
        assert len(changes) == 1
        assert isinstance(changes[0], FileChange)
        assert changes[0].path == "foo/bar.py"

    def test_multi_file_returns_one_filechange_each(self) -> None:
        changes = parse_unified_diff(MULTI_FILE_DIFF)
        assert [c.path for c in changes] == ["a.py", "b.go"]

    def test_empty_diff_returns_empty_list(self) -> None:
        assert parse_unified_diff("") == []


class TestHunks:
    def test_hunk_header_and_counts(self) -> None:
        change = parse_unified_diff(SIMPLE_DIFF)[0]
        assert len(change.hunks) == 1
        h = change.hunks[0]
        assert h.old_start == 1
        assert h.old_count == 3
        assert h.new_start == 1
        assert h.new_count == 4

    def test_hunk_lines_kinds(self) -> None:
        change = parse_unified_diff(SIMPLE_DIFF)[0]
        lines = change.hunks[0].lines
        kinds = [line.kind for line in lines]
        assert kinds == ["context", "context", "added", "context"]

    def test_added_line_has_no_old_lineno(self) -> None:
        change = parse_unified_diff(SIMPLE_DIFF)[0]
        added = [line for line in change.hunks[0].lines if line.kind == "added"]
        assert len(added) == 1
        assert added[0].old_line is None
        assert added[0].new_line == 3
        assert added[0].text == "inserted line"


class TestFileLevelCounts:
    def test_additions_and_deletions(self) -> None:
        change = parse_unified_diff(SIMPLE_DIFF)[0]
        assert change.additions == 1
        assert change.deletions == 0

    def test_multi_file_each_has_its_own_counts(self) -> None:
        changes = parse_unified_diff(MULTI_FILE_DIFF)
        a, b = changes
        assert (a.additions, a.deletions) == (1, 1)
        assert (b.additions, b.deletions) == (1, 0)


class TestLanguageDetection:
    @pytest.mark.parametrize(
        "path,lang",
        [
            ("foo/bar.py", "python"),
            ("a.go", "go"),
            ("x.kt", "kotlin"),
            ("y.java", "java"),
            ("z.ts", "typescript"),
            ("z.tsx", "typescript"),
            ("z.jsx", "javascript"),
            ("z.js", "javascript"),
            ("unknown.xyz", None),
            ("Makefile", None),
        ],
    )
    def test_detected_from_extension(self, path: str, lang: str | None) -> None:
        diff = (
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            f"@@ -1 +1,2 @@\n existing\n+new\n"
        )
        change = parse_unified_diff(diff)[0]
        assert change.language == lang


class TestNewAndDeletedFiles:
    def test_new_file_flag(self) -> None:
        change = parse_unified_diff(NEW_FILE_DIFF)[0]
        assert change.is_new_file is True
        assert change.is_deleted_file is False
        assert change.path == "new.py"
        assert change.additions == 2

    def test_deleted_file_flag(self) -> None:
        change = parse_unified_diff(DELETED_FILE_DIFF)[0]
        assert change.is_deleted_file is True
        assert change.is_new_file is False
        # For deleted files unidiff reports source_file; we keep the deleted path.
        assert change.path == "old.py"
        assert change.deletions == 2


class TestRobustness:
    def test_crlf_endings_normalized(self) -> None:
        diff = SIMPLE_DIFF.replace("\n", "\r\n")
        changes = parse_unified_diff(diff)
        assert len(changes) == 1
        assert changes[0].additions == 1

    def test_path_quoted_with_ab_prefix_stripped(self) -> None:
        # Ensure 'a/' / 'b/' prefixes are stripped (default git diff style)
        change = parse_unified_diff(SIMPLE_DIFF)[0]
        assert not change.path.startswith("a/")
        assert not change.path.startswith("b/")
