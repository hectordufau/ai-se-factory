"""Tests for the TaskDag topological scheduler."""
import pytest

from factory.task_dag import TaskDag, CycleError


def test_topological_ready():
    dag = TaskDag()
    dag.add("impl", deps=["arch"])
    dag.add("arch", deps=["plan"])
    dag.add("plan", deps=[])
    assert dag.ready() == {"plan"}
    dag.mark_done("plan")
    assert dag.ready() == {"arch"}
    dag.mark_done("arch")
    assert dag.ready() == {"impl"}


def test_parallel_ready():
    dag = TaskDag()
    dag.add("backend", deps=["arch"])
    dag.add("frontend", deps=["arch"])
    dag.add("db", deps=["arch"])
    dag.add("arch", deps=[])
    dag.mark_done("arch")
    assert dag.ready() == {"backend", "frontend", "db"}


def test_is_complete_only_when_all_done():
    dag = TaskDag()
    dag.add("a", deps=[])
    dag.add("b", deps=["a"])
    assert not dag.is_complete()
    dag.mark_done("a")
    assert not dag.is_complete()
    dag.mark_done("b")
    assert dag.is_complete()


def test_ready_excludes_running():
    dag = TaskDag()
    dag.add("a", deps=[])
    dag.add("b", deps=["a"])
    dag.mark_done("a")
    dag.mark_running("b")
    assert dag.ready() == set()


def test_cycle_detection():
    dag = TaskDag()
    dag.add("a", deps=["b"])
    dag.add("b", deps=["a"])
    with pytest.raises(CycleError):
        dag.ready()


def test_mark_done_unknown_raises():
    dag = TaskDag()
    with pytest.raises(KeyError):
        dag.mark_done("nope")
