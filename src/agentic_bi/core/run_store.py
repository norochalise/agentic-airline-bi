"""Where an agent run's checkpoints and trace are kept."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from agentic_bi.config import CHECKPOINTS_DIR, TRACES_DIR, max_saved_runs, persist_runs
from agentic_bi.core.checkpoint import AgentCheckpoint, save_checkpoint
from agentic_bi.core.observability import AgentTrace, save_trace
from agentic_bi.core.persistence import prune_oldest


class RunStore(Protocol):
    """Receives a run's checkpoints and, at the end, its trace."""

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> Path | None: ...

    def save_trace(self, trace: AgentTrace) -> Path | None: ...


@dataclass
class FileRunStore:
    """Write runs to disk and keep only the newest `keep` runs."""

    checkpoint_dir: Path = CHECKPOINTS_DIR
    trace_dir: Path = TRACES_DIR
    keep: int = 500

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> Path:
        return save_checkpoint(checkpoint, checkpoint_dir=self.checkpoint_dir)

    def save_trace(self, trace: AgentTrace) -> Path:
        path = save_trace(trace, trace_dir=self.trace_dir)

        # The trace is the last file a run writes; prune once per run and
        # never remove the run that is finishing.
        prune_oldest(self.trace_dir, keep=self.keep, protect=(path.name,))
        prune_oldest(self.checkpoint_dir, keep=self.keep, protect=(trace.run_id,))

        return path


@dataclass
class MemoryRunStore:
    """Keep runs in memory; for tests and PERSIST_RUNS=false."""

    checkpoints: list[AgentCheckpoint] = field(default_factory=list)
    traces: list[AgentTrace] = field(default_factory=list)

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> None:
        self.checkpoints.append(checkpoint)

    def save_trace(self, trace: AgentTrace) -> None:
        self.traces.append(trace)


def default_run_store() -> RunStore:
    """Disk storage unless PERSIST_RUNS turns it off."""

    if not persist_runs():
        return MemoryRunStore()

    return FileRunStore(keep=max_saved_runs())
