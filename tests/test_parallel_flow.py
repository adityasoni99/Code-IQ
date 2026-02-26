"""Unit tests for ParallelSubfolderFlow."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pocketflow import Flow, Node

from flow import ParallelSubfolderFlow
from shared_schema import default_shared_store


class MockPipelineNode(Node):
    """Writes project_name to shared and creates index.md in output_dir/project_name."""

    def prep(self, shared):
        return {"project_name": self.params.get("project_name")}

    def exec(self, prep_res):
        return prep_res["project_name"]

    def post(self, shared, prep_res, exec_res):
        shared["project_name"] = exec_res
        out_dir = Path(self.params["output_dir"]) / self.params["project_name"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.md").write_text("# Mock")
        shared["final_output_dir"] = str(out_dir)
        return "default"


def test_parallel_flow_three_folders_two_workers(tmp_path):
    """With 3 folders and parallel_workers=2, all 3 complete successfully."""
    for name in ["a", "b", "c"]:
        (tmp_path / name).mkdir()
    leaf_folders = [
        {"local_dir": str(tmp_path / "a"), "output_dir": str(tmp_path / "out"), "project_name": "a"},
        {"local_dir": str(tmp_path / "b"), "output_dir": str(tmp_path / "out"), "project_name": "b"},
        {"local_dir": str(tmp_path / "c"), "output_dir": str(tmp_path / "out"), "project_name": "c"},
    ]
    inner_flow = Flow(start=MockPipelineNode())
    parallel = ParallelSubfolderFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = leaf_folders
    shared["parallel_workers"] = 2
    parallel.run(shared)
    assert len(shared["completed_folders"]) == 3
    assert (tmp_path / "out" / "a" / "index.md").exists()
    assert (tmp_path / "out" / "b" / "index.md").exists()
    assert (tmp_path / "out" / "c" / "index.md").exists()


def test_parallel_flow_shared_store_isolation(tmp_path):
    """Two folders run concurrently; each gets correct project_name in isolated shared."""
    (tmp_path / "p1").mkdir()
    (tmp_path / "p2").mkdir()
    leaf_folders = [
        {"local_dir": str(tmp_path / "p1"), "output_dir": str(tmp_path / "out"), "project_name": "p1"},
        {"local_dir": str(tmp_path / "p2"), "output_dir": str(tmp_path / "out"), "project_name": "p2"},
    ]
    inner_flow = Flow(start=MockPipelineNode())
    parallel = ParallelSubfolderFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = leaf_folders
    shared["parallel_workers"] = 2
    parallel.run(shared)
    assert set(shared["completed_folders"]) == {str(tmp_path / "out" / "p1"), str(tmp_path / "out" / "p2")}
    assert (tmp_path / "out" / "p1" / "index.md").exists()
    assert (tmp_path / "out" / "p2" / "index.md").exists()


def test_parallel_flow_failure_handling(tmp_path):
    """One folder's pipeline raises; the other 2 succeed; completed_folders has 2 entries."""
    (tmp_path / "ok1").mkdir()
    (tmp_path / "fail").mkdir()
    (tmp_path / "ok2").mkdir()

    call_count = [0]

    class FailingNode(Node):
        def prep(self, shared):
            return {"project_name": self.params.get("project_name")}

        def exec(self, prep_res):
            call_count[0] += 1
            if prep_res["project_name"] == "fail":
                raise RuntimeError("mock failure")
            return prep_res["project_name"]

        def post(self, shared, prep_res, exec_res):
            shared["final_output_dir"] = str(Path(self.params["output_dir"]) / self.params["project_name"])
            return "default"

    leaf_folders = [
        {"local_dir": str(tmp_path / "ok1"), "output_dir": str(tmp_path / "out"), "project_name": "ok1"},
        {"local_dir": str(tmp_path / "fail"), "output_dir": str(tmp_path / "out"), "project_name": "fail"},
        {"local_dir": str(tmp_path / "ok2"), "output_dir": str(tmp_path / "out"), "project_name": "ok2"},
    ]
    inner_flow = Flow(start=FailingNode())
    parallel = ParallelSubfolderFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = leaf_folders
    shared["parallel_workers"] = 2
    parallel.run(shared)
    assert len(shared["completed_folders"]) == 2
    assert "ok1" in [Path(p).name for p in shared["completed_folders"]]
    assert "ok2" in [Path(p).name for p in shared["completed_folders"]]


def test_parallel_flow_one_worker_sequential(tmp_path):
    """parallel_workers=1: all 3 folders still complete (sequential)."""
    for name in ["a", "b", "c"]:
        (tmp_path / name).mkdir()
    leaf_folders = [
        {"local_dir": str(tmp_path / "a"), "output_dir": str(tmp_path / "out"), "project_name": "a"},
        {"local_dir": str(tmp_path / "b"), "output_dir": str(tmp_path / "out"), "project_name": "b"},
        {"local_dir": str(tmp_path / "c"), "output_dir": str(tmp_path / "out"), "project_name": "c"},
    ]
    inner_flow = Flow(start=MockPipelineNode())
    parallel = ParallelSubfolderFlow(start=inner_flow)
    shared = default_shared_store()
    shared["leaf_folders"] = leaf_folders
    shared["parallel_workers"] = 1
    parallel.run(shared)
    assert len(shared["completed_folders"]) == 3
