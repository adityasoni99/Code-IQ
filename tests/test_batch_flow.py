"""Unit tests for SubfolderBatchFlow."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pocketflow import Flow, Node

from flow import SubfolderBatchFlow
from shared_schema import default_shared_store


class MockPipelineNode(Node):
    """Single node that writes final_output_dir and creates a dummy index.md from params."""

    def prep(self, shared):
        return {
            "local_dir": self.params.get("local_dir"),
            "output_dir": self.params.get("output_dir"),
            "project_name": self.params.get("project_name"),
        }

    def exec(self, prep_res):
        out_dir = Path(prep_res["output_dir"]) / prep_res["project_name"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.md").write_text("# Mock")
        return str(out_dir)

    def post(self, shared, prep_res, exec_res):
        shared["final_output_dir"] = exec_res
        return "default"


def test_batch_flow_three_leaf_folders_runs_three_times(tmp_path):
    """With 3 leaf folders, inner pipeline runs 3 times, each gets correct self.params."""
    leaf_folders = [
        {"local_dir": str(tmp_path / "a"), "output_dir": str(tmp_path / "out"), "project_name": "a"},
        {"local_dir": str(tmp_path / "b"), "output_dir": str(tmp_path / "out"), "project_name": "b"},
        {"local_dir": str(tmp_path / "c"), "output_dir": str(tmp_path / "out"), "project_name": "c"},
    ]
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    mock_node = MockPipelineNode()
    inner_flow = Flow(start=mock_node)
    batch = SubfolderBatchFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = leaf_folders
    batch.run(shared)
    assert shared["completed_count"] == 3
    assert (tmp_path / "out" / "a" / "index.md").exists()
    assert (tmp_path / "out" / "b" / "index.md").exists()
    assert (tmp_path / "out" / "c" / "index.md").exists()


def test_batch_flow_empty_leaf_folders_no_errors():
    """With empty leaf_folders, no errors; batch completes; completed_count is 0."""
    inner_flow = Flow(start=MockPipelineNode())
    batch = SubfolderBatchFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = []
    batch.run(shared)
    assert shared["completed_count"] == 0


def test_batch_flow_params_propagated_to_inner_node(tmp_path):
    """self.params from each leaf_folders entry is propagated to inner nodes."""
    (tmp_path / "only").mkdir()
    leaf_folders = [
        {"local_dir": str(tmp_path / "only"), "output_dir": str(tmp_path / "out"), "project_name": "only"},
    ]
    mock_node = MockPipelineNode()
    inner_flow = Flow(start=mock_node)
    batch = SubfolderBatchFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = leaf_folders
    batch.run(shared)
    assert (tmp_path / "out" / "only" / "index.md").read_text() == "# Mock"
    assert shared["completed_count"] == 1
