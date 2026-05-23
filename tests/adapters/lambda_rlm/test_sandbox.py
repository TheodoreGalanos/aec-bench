# ABOUTME: Unit tests for the lambda-rlm DocumentSandbox + anchor extractors.
# ABOUTME: Tests anchor parsing, four extractors, and slice round-trip invariants.

from aec_bench.adapters.lambda_rlm.sandbox import (
    DocumentSandbox,
    extract_email_thread,
    extract_markdown_headings,
    extract_paragraph_index,
    extract_table_rows,
    parse_anchor_ref,
)


def test_parse_anchor_ref_bare_label():
    label, anchor = parse_anchor_ref("brief.md")
    assert label == "brief.md"
    assert anchor is None


def test_parse_anchor_ref_hash_slug():
    label, anchor = parse_anchor_ref("brief.md#scope")
    assert label == "brief.md"
    assert anchor == "#scope"


def test_parse_anchor_ref_at_id():
    label, anchor = parse_anchor_ref("thread.md@msg3")
    assert label == "thread.md"
    assert anchor == "@msg3"


def test_parse_anchor_ref_paragraph_index():
    label, anchor = parse_anchor_ref("doc.md:p7")
    assert label == "doc.md"
    assert anchor == ":p7"


def test_parse_anchor_ref_byte_range():
    label, anchor = parse_anchor_ref("doc.md#scope:bytes:0-100")
    assert label == "doc.md"
    assert anchor == "#scope:bytes:0-100"


def test_parse_anchor_ref_invalid_sigil_raises():
    import pytest

    with pytest.raises(ValueError, match="invalid anchor"):
        parse_anchor_ref("doc.md?query")


def test_markdown_headings_basic():
    text = "# Title\nintro\n\n## Scope\nscope body\n\n## Schedule\ndates"
    anchors = extract_markdown_headings(text)
    assert [a.canonical for a in anchors] == ["#title", "#scope", "#schedule"]
    assert all(a.scheme == "heading" for a in anchors)


def test_markdown_headings_collision_appends_index():
    text = "## Scope\nfirst\n\n## Scope\nsecond"
    anchors = extract_markdown_headings(text)
    assert [a.canonical for a in anchors] == ["#scope", "#scope-2"]


def test_markdown_headings_slug_strips_punctuation():
    text = "# Scope of Work (v2)\nbody"
    anchors = extract_markdown_headings(text)
    assert anchors[0].canonical == "#scope-of-work-v2"


def test_markdown_headings_empty_doc_returns_empty():
    anchors = extract_markdown_headings("plain text no headings")
    assert anchors == ()


def test_email_thread_three_messages():
    text = (
        "## Message 1 — From Mark Abbott (2026-01-10)\nbody one\n\n"
        "## Message 2 — From Phil Smith (2026-01-12)\nbody two\n\n"
        "## Message 3 — From Mark Abbott (2026-01-15)\nbody three"
    )
    anchors = extract_email_thread(text)
    assert [a.canonical for a in anchors] == ["@msg1", "@msg2", "@msg3"]
    assert all(a.scheme == "instance" for a in anchors)


def test_email_thread_no_messages_returns_empty():
    anchors = extract_email_thread("not an email thread")
    assert anchors == ()


def test_paragraph_index_blank_line_separation():
    text = "first paragraph\n\nsecond para\n\n  \n\nthird"
    anchors = extract_paragraph_index(text)
    assert [a.canonical for a in anchors] == [":p1", ":p2", ":p3"]
    assert all(a.scheme == "paragraph" for a in anchors)


def test_paragraph_index_single_paragraph():
    anchors = extract_paragraph_index("only one paragraph here")
    assert [a.canonical for a in anchors] == [":p1"]


def test_paragraph_index_empty_returns_empty():
    assert extract_paragraph_index("") == ()


def test_table_rows_csv_with_header():
    text = "id,topic,owner\nE001,scope,Mark\nE002,risk,Phil"
    anchors = extract_table_rows(text, key_column="id")
    assert [a.canonical for a in anchors] == ["@id=E001", "@id=E002"]
    assert all(a.scheme == "instance" for a in anchors)


def test_table_rows_no_key_column_falls_back_to_row_index():
    text = "a,b\n1,2\n3,4"
    anchors = extract_table_rows(text, key_column=None)
    assert [a.canonical for a in anchors] == ["@row1", "@row2"]


def test_table_rows_empty_table_returns_empty():
    assert extract_table_rows("a,b\n", key_column=None) == ()


def test_sandbox_labels_returns_inserted_labels():
    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# Title\n\n## Scope\nbody"},
        extractor_overrides={},
    )
    assert sandbox.labels() == ("brief.md",)


def test_sandbox_anchors_includes_primary_and_paragraph_secondary():
    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# Title\n\n## Scope\nbody"},
        extractor_overrides={},
    )
    canonicals = [a.canonical for a in sandbox.anchors("brief.md")]
    assert "#title" in canonicals
    assert "#scope" in canonicals
    assert ":p1" in canonicals  # universal secondary


def test_sandbox_slice_round_trips_text_and_offsets():
    text = "# Title\n\n## Scope\nbody text here"
    sandbox = DocumentSandbox.from_documents({"brief.md": text}, extractor_overrides={})
    sl = sandbox.slice("brief.md", "#scope")
    # invariant: original[start:end] == text
    assert text[sl.start : sl.end] == sl.text


def test_sandbox_bare_label_returns_whole_doc():
    text = "first\n\nsecond"
    sandbox = DocumentSandbox.from_documents({"a.txt": text}, extractor_overrides={})
    sl = sandbox.slice("a.txt", anchor=None)
    assert sl.text == text
    assert sl.start == 0 and sl.end == len(text)


def test_sandbox_extension_picks_email_extractor_for_eml():
    text = "## Message 1 — From X\nbody"
    sandbox = DocumentSandbox.from_documents({"thread.eml": text}, extractor_overrides={})
    canonicals = [a.canonical for a in sandbox.anchors("thread.eml")]
    assert "@msg1" in canonicals


def test_sandbox_override_picks_email_extractor_for_md():
    text = "## Message 1 — From X\nbody"
    sandbox = DocumentSandbox.from_documents(
        {"thread.md": text},
        extractor_overrides={"thread.md": "email_thread"},
    )
    canonicals = [a.canonical for a in sandbox.anchors("thread.md")]
    assert "@msg1" in canonicals


def test_sandbox_unknown_anchor_raises():
    import pytest

    sandbox = DocumentSandbox.from_documents({"a.md": "# T"}, extractor_overrides={})
    with pytest.raises(KeyError, match="anchor"):
        sandbox.slice("a.md", "#nope")
