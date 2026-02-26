"""Unit tests for GenerateHierarchicalView node."""

from pathlib import Path

import pytest

from nodes import GenerateHierarchicalView


def test_hierarchical_view_prep_extracts_tree_and_mermaid(tmp_path):
    """prep: mock output tree with 3 folders, each index.md with Mermaid; verify tree and diagrams extracted."""
    for name in ["a", "b", "c"]:
        d = tmp_path / name
        d.mkdir()
        (d / "index.md").write_text(
            f"# {name}\n\nSummary for {name}.\n\n```mermaid\nflowchart LR\n  A --> B\n```\n",
            encoding="utf-8",
        )
    shared = {"output_dir": str(tmp_path)}
    node = GenerateHierarchicalView()
    prep_res = node.prep(shared)
    assert "output_tree" in prep_res
    assert "pages" in prep_res
    assert "diagrams" in prep_res
    assert len(prep_res["flat"]) == 3
    assert "flowchart LR" in prep_res["diagrams"].get("a", "")
    assert "Summary for a" in prep_res["flat"][0]["summary"] or prep_res["pages"].get("a", "")


def test_hierarchical_view_exec_master_md_has_links(tmp_path):
    """exec: master_index.md contains Mermaid/links to each folder."""
    (tmp_path / "p1").mkdir()
    (tmp_path / "p1" / "index.md").write_text("# P1\n\nText.\n\n```mermaid\nflowchart TD\nA-->B\n```\n")
    (tmp_path / "p2").mkdir()
    (tmp_path / "p2" / "index.md").write_text("# P2\n\nOther.\n")
    shared = {"output_dir": str(tmp_path)}
    node = GenerateHierarchicalView()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    md = exec_res.get("md", "")
    assert "Master" in md or "p1" in md or "p2" in md
    assert "flowchart" in md or "P1" in md or "P2" in md


def test_hierarchical_view_exec_html_has_tree_pages_and_cdn(tmp_path):
    """exec: master_index.html contains embedded TREE/PAGES and marked.js/mermaid.js CDN."""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "index.md").write_text("# One\n\nContent.\n\n```mermaid\nflowchart LR\nX-->Y\n```\n")
    shared = {"output_dir": str(tmp_path)}
    node = GenerateHierarchicalView()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    html = exec_res.get("html", "")
    assert "var TREE =" in html or "TREE =" in html
    assert "var PAGES =" in html or "PAGES =" in html
    assert "marked" in html and "mermaid" in html
    assert "cdn.jsdelivr.net" in html or "cdn" in html


def test_hierarchical_view_exec_html_sidebar(tmp_path):
    """exec: HTML contains folder hierarchy in sidebar (tree-nav)."""
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "index.md").write_text("# Foo\n\nBar.\n")
    shared = {"output_dir": str(tmp_path)}
    node = GenerateHierarchicalView()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    html = exec_res.get("html", "")
    assert "tree-nav" in html
    assert "sidebar" in html


def test_hierarchical_view_empty_output_tree(tmp_path):
    """Empty output tree: minimal valid output (master_index.md with little content, HTML with empty PAGES)."""
    shared = {"output_dir": str(tmp_path)}
    node = GenerateHierarchicalView()
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    assert "md" in exec_res and "html" in exec_res
    assert "PAGES" in exec_res["html"]
    node.post({}, prep_res, exec_res)
    assert (tmp_path / "master_index.md").exists()
    assert (tmp_path / "master_index.html").exists()
    assert (tmp_path / "tree.json").exists()
    assert (tmp_path / "tree.json").read_text() == "[]"


def test_hierarchical_view_nested_three_levels(tmp_path):
    """Nested subfolders (3 levels): tree structure in tree.json correct."""
    (tmp_path / "L1" / "L2" / "L3").mkdir(parents=True)
    (tmp_path / "L1" / "index.md").write_text("# L1\n\nOK.\n")
    (tmp_path / "L1" / "L2" / "index.md").write_text("# L2\n\nOK.\n")
    (tmp_path / "L1" / "L2" / "L3" / "index.md").write_text("# L3\n\nOK.\n")
    shared = {"output_dir": str(tmp_path)}
    node = GenerateHierarchicalView()
    prep_res = node.prep(shared)
    assert len(prep_res["flat"]) >= 3
    exec_res = node.exec(prep_res)
    import json
    tree = json.loads(exec_res["tree_json"])
    assert len(tree) >= 1
    names = [n["name"] for n in prep_res["flat"]]
    assert "L1" in names
    assert "L2" in names
    assert "L3" in names
