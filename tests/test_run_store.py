import os

from agentic_bi.core.agent import collect_sources
from agentic_bi.core.checkpoint import create_checkpoint
from agentic_bi.core.observability import create_trace
from agentic_bi.core.persistence import prune_oldest, read_json, write_json
from agentic_bi.core.run_store import FileRunStore, MemoryRunStore, default_run_store
from agentic_bi.core.state import AgentState


def test_write_and_read_json_round_trip(tmp_path):
    path = write_json(tmp_path / "nested" / "data.json", {"answer": "Café"})

    assert read_json(path) == {"answer": "Café"}


def test_prune_keeps_the_newest_entries(tmp_path):
    for index in range(5):
        entry = tmp_path / f"run_{index}"
        entry.mkdir()
        os.utime(entry, (1_000 + index, 1_000 + index))

    removed = prune_oldest(tmp_path, keep=2)

    assert removed == 3
    assert sorted(p.name for p in tmp_path.iterdir()) == ["run_3", "run_4"]


def test_file_store_caps_saved_runs(tmp_path):
    store = FileRunStore(
        checkpoint_dir=tmp_path / "checkpoints", trace_dir=tmp_path / "traces", keep=2
    )

    for index in range(4):
        trace = create_trace(f"question {index}")
        store.save_checkpoint(
            create_checkpoint(trace.run_id, "final", AgentState(goal="q"))
        )
        path = store.save_trace(trace)

        # The run that just finished is always kept.
        assert path.exists()
        assert (tmp_path / "checkpoints" / trace.run_id).is_dir()

    assert len(list((tmp_path / "traces").iterdir())) == 2
    assert len(list((tmp_path / "checkpoints").iterdir())) == 2


def test_persistence_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("PERSIST_RUNS", "false")
    assert isinstance(default_run_store(), MemoryRunStore)

    monkeypatch.setenv("PERSIST_RUNS", "true")
    monkeypatch.setenv("MAX_SAVED_RUNS", "7")
    store = default_run_store()
    assert isinstance(store, FileRunStore)
    assert store.keep == 7


def test_collect_sources_lists_each_page_and_url_once():
    observations = [
        {
            "tool": "search_private_knowledge",
            "result": {
                "results": [
                    {"source": "contract.pdf", "page_number": 15},
                    {"source": "contract.pdf", "page_number": 15},
                    {"source": "contract.pdf", "page_number": 16},
                ]
            },
        },
        {
            "tool": "search_official_web",
            "result": {
                "results": [
                    {"title": "Refunds", "url": "https://transportation.gov/refunds"},
                    {"title": "Refunds", "url": "https://transportation.gov/refunds"},
                ]
            },
        },
    ]

    sources = collect_sources("knowledge-analysis", observations)

    assert [(s["source_type"], s["page_number"]) for s in sources] == [
        ("private_document", 15),
        ("private_document", 16),
        ("live_official_web", None),
    ]
    assert collect_sources("data-analysis", [])[0]["source_type"] == "dataset"
    assert collect_sources(None, observations) == []
