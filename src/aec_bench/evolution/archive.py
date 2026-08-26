# ABOUTME: CVT-MAP-Elites archive for quality-diversity harness evolution.
# ABOUTME: Maintains diverse high-performing workspaces indexed by behaviour descriptors.

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

import numpy as np
from ribs.archives import CVTArchive

from aec_bench.contracts.evolution import BehaviourDescriptor, WorkspaceSnapshot


class ArchiveInsertionStatus(StrEnum):
    """Outcome of inserting one descriptor and candidate into the archive."""

    NOT_ADDED = "not_added"
    IMPROVED = "improved"
    NEW_CELL = "new_cell"


_PYRIBS_STATUS_MAP: dict[int, ArchiveInsertionStatus] = {
    0: ArchiveInsertionStatus.NOT_ADDED,
    1: ArchiveInsertionStatus.IMPROVED,
    2: ArchiveInsertionStatus.NEW_CELL,
}


@dataclass(frozen=True)
class ArchiveInsertionResult:
    """Immutable result for one archive insertion operation."""

    status: ArchiveInsertionStatus
    candidate_id: str
    cell_index: int | None
    displaced_candidate_id: str | None

    @property
    def added(self) -> bool:
        """Whether this insertion occupied or improved an archive cell."""
        return self.status is not ArchiveInsertionStatus.NOT_ADDED

    def __post_init__(self) -> None:
        try:
            status = ArchiveInsertionStatus(self.status)
        except ValueError as exc:
            raise ValueError(f"unsupported archive insertion status: {self.status!r}") from exc
        object.__setattr__(self, "status", status)
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("candidate_id must not be blank")
        if self.cell_index is not None and (isinstance(self.cell_index, bool) or self.cell_index < 0):
            raise ValueError("cell_index must be a non-negative integer or None")
        if self.cell_index is not None and not isinstance(self.cell_index, int):
            raise ValueError("cell_index must be a non-negative integer or None")
        if self.displaced_candidate_id is not None:
            if not isinstance(self.displaced_candidate_id, str) or not self.displaced_candidate_id.strip():
                raise ValueError("displaced_candidate_id must not be blank when provided")


@dataclass(frozen=True)
class ArchiveBatchOutcome:
    """Immutable outcomes for inserting one candidate's descriptors."""

    candidate_id: str
    insertions: tuple[ArchiveInsertionResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("candidate_id must not be blank")
        insertions = tuple(self.insertions)
        if any(result.candidate_id != self.candidate_id for result in insertions):
            raise ValueError("archive insertion candidate_id must match the batch candidate_id")
        object.__setattr__(self, "insertions", insertions)

    @property
    def added(self) -> bool:
        """Whether at least one descriptor entered or improved an archive cell."""
        return any(
            result.status in (ArchiveInsertionStatus.IMPROVED, ArchiveInsertionStatus.NEW_CELL)
            for result in self.insertions
        )


@dataclass(frozen=True)
class ArchiveEntry:
    """A single elite stored in the QD archive with provenance metadata."""

    snapshot: WorkspaceSnapshot
    bd: BehaviourDescriptor
    cell_index: int
    task_ids: tuple[str, ...] = ()
    discipline: str = ""
    run_id: str = ""


@dataclass(frozen=True)
class ArchiveView:
    """Exact immutable projection of the occupied archive cells for search."""

    entries: tuple[ArchiveEntry, ...]
    n_centroids: int

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        if self.n_centroids < 0:
            raise ValueError("archive view n_centroids must be non-negative")
        if len({entry.cell_index for entry in entries}) != len(entries):
            raise ValueError("archive view entries must have unique cell indices")
        if any(entry.cell_index >= self.n_centroids for entry in entries):
            raise ValueError("archive view entry cell_index must be within n_centroids")
        object.__setattr__(self, "entries", entries)

    @property
    def size(self) -> int:
        """Number of occupied cells in this view."""
        return len(self.entries)

    def top_k(self, k: int = 5) -> tuple[ArchiveEntry, ...]:
        """Return entries sorted by reward without touching archive state."""
        return tuple(sorted(self.entries, key=lambda entry: entry.bd.reward, reverse=True)[:k])

    def frontier(self, k: int = 5) -> tuple[ArchiveEntry, ...]:
        """Return diverse high-performing entries without touching archive state."""
        entries = self.top_k(len(self.entries))
        if not entries:
            return ()
        selected = [entries[0]]
        remaining = list(entries[1:])
        while len(selected) < min(k, len(entries)) and remaining:
            selected_vectors = np.array([_bd_to_normalised(entry.bd) for entry in selected])
            best = max(
                remaining,
                key=lambda entry: float(np.linalg.norm(selected_vectors - _bd_to_normalised(entry.bd), axis=1).min()),
            )
            selected.append(best)
            remaining.remove(best)
        return tuple(selected)

    def get_entry_by_candidate_id(self, candidate_id: str) -> ArchiveEntry | None:
        """Return an entry by candidate identity."""
        return next((entry for entry in self.entries if entry.snapshot.candidate_id == candidate_id), None)

    def coverage_report(self) -> ArchiveCoverage:
        """Return occupancy statistics for this immutable view."""
        occupied = self.size
        return {
            "occupied": occupied,
            "empty": self.n_centroids - occupied,
            "coverage": occupied / self.n_centroids if self.n_centroids else 0.0,
            "total_centroids": self.n_centroids,
        }


class ArchiveCoverage(TypedDict):
    """Archive occupancy values consumed by reports and swarm prompts."""

    occupied: int
    empty: int
    coverage: float
    total_centroids: int


# The ranges for each BD dimension passed to the CVTArchive.
# pyribs uses these to bound the Voronoi cells — measures must be within these ranges.
_BD_RANGES: list[tuple[float, float]] = [
    (0.0, 500_000.0),  # token_cost
    (0.0, 1.0),  # verification_depth
    (0.0, 2.0),  # tool_density
    (0.0, 1.0),  # exploration_ratio
    (0.0, 1.0),  # deliberation_ratio
    (0.0, 1.0),  # reward
]


def _bd_to_array(bd: BehaviourDescriptor) -> np.ndarray:
    """Convert a BehaviourDescriptor to a raw measures array clipped to _BD_RANGES.

    Returns values in the same space as _BD_RANGES (not normalised to [0,1]).
    pyribs handles its own internal mapping; we only need to clip out-of-range values.
    """
    raw = [
        bd.token_cost,
        bd.verification_depth,
        bd.tool_density,
        bd.exploration_ratio,
        bd.deliberation_ratio,
        bd.reward,
    ]
    clipped = [float(np.clip(value, lo, hi)) for value, (lo, hi) in zip(raw, _BD_RANGES, strict=False)]
    return np.array(clipped, dtype=float)


def _bd_to_normalised(bd: BehaviourDescriptor) -> np.ndarray:
    """Convert a BehaviourDescriptor to a [0, 1]^6 normalised array for PCA projection."""
    raw = [
        bd.token_cost,
        bd.verification_depth,
        bd.tool_density,
        bd.exploration_ratio,
        bd.deliberation_ratio,
        bd.reward,
    ]
    normalised = []
    for value, (lo, hi) in zip(raw, _BD_RANGES, strict=False):
        span = hi - lo
        if span == 0.0:
            normalised.append(0.0)
        else:
            normalised.append(float(np.clip((value - lo) / span, 0.0, 1.0)))
    return np.array(normalised, dtype=float)


class QDArchive:
    """CVT-MAP-Elites archive storing diverse high-performing workspace snapshots.

    Uses a 6-dimensional behaviour space derived from BehaviourDescriptor fields.
    Snapshots are stored in a sidecar dict keyed by the CVT centroid index so we
    can retrieve full WorkspaceSnapshot objects without serialising them into the
    archive's solution array.
    """

    def __init__(self, n_centroids: int = 200, seed: int = 42) -> None:
        self._n_centroids = n_centroids
        self._seed = seed
        self._archive = CVTArchive(
            solution_dim=1,
            centroids=n_centroids,
            ranges=_BD_RANGES,
            seed=seed,
        )
        # Maps centroid index → ArchiveEntry for the currently occupying elite.
        self._entries: dict[int, ArchiveEntry] = {}

    @property
    def size(self) -> int:
        """Number of occupied cells in the archive."""
        return len(self._archive)

    def insert(
        self,
        bd: BehaviourDescriptor,
        snapshot: WorkspaceSnapshot,
        *,
        task_ids: tuple[str, ...] = (),
        discipline: str = "",
        run_id: str = "",
    ) -> ArchiveInsertionResult:
        """Add a workspace snapshot to the archive.

        The returned value preserves whether this was a new cell, an improvement,
        or a rejection. The snapshot is stored directly as the candidate material;
        the archive does not create a second candidate representation.

        Task metadata (task_ids, discipline, run_id) is stored alongside the entry
        for filtering and provenance.
        """
        measures = _bd_to_array(bd).reshape(1, -1)
        cell_index = int(self._archive.index_of(measures)[0])
        previous = self._entries.get(cell_index)
        result = self._archive.add(
            solution=np.array([[0.0]]),
            objective=np.array([bd.reward]),
            measures=measures,
        )
        status = int(result["status"][0])
        # status 0 = not added, 1 = improved, 2 = new cell
        if status in (1, 2):
            self._entries[cell_index] = ArchiveEntry(
                snapshot=snapshot,
                bd=bd,
                cell_index=cell_index,
                task_ids=task_ids,
                discipline=discipline,
                run_id=run_id,
            )
        try:
            insertion_status = _PYRIBS_STATUS_MAP[status]
        except KeyError as exc:
            raise RuntimeError(f"unsupported pyribs archive insertion status: {status}") from exc
        displaced_candidate_id = (
            previous.snapshot.candidate_id
            if insertion_status is ArchiveInsertionStatus.IMPROVED and previous is not None
            else None
        )
        return ArchiveInsertionResult(
            status=insertion_status,
            candidate_id=snapshot.candidate_id,
            cell_index=cell_index,
            displaced_candidate_id=displaced_candidate_id,
        )

    def view(self) -> ArchiveView:
        """Return an exact immutable projection for pure search functions."""
        return ArchiveView(
            entries=tuple(self._entries[index] for index in sorted(self._entries)),
            n_centroids=self._n_centroids,
        )

    def query_nearest(self, bd: BehaviourDescriptor) -> WorkspaceSnapshot | None:
        """Retrieve the snapshot at the cell nearest to the given BD.

        Returns None if the archive is empty or the nearest cell is unoccupied.
        """
        if self.size == 0:
            return None
        measures = _bd_to_array(bd).reshape(1, -1)
        occupied, _ = self._archive.retrieve(measures=measures)
        if not occupied[0]:
            return None
        index = int(self._archive.index_of(measures)[0])
        entry = self._entries.get(index)
        if entry is None:
            return None
        return entry.snapshot

    def project_2d(self) -> list[dict[str, object]]:
        """PCA-project all archive entries to 2D for visualisation.

        Returns an empty list for an empty archive. Returns a single point at the
        origin when only one entry exists (PCA is undefined for a single sample).
        Each dict contains: x, y, reward, candidate_id, token_cost, verification_depth,
        tool_density, exploration_ratio, deliberation_ratio.
        """
        if self.size == 0:
            return []

        entries = list(self._entries.values())

        def _entry_to_point(
            e: ArchiveEntry,
            x: float = 0.0,
            y: float = 0.0,
        ) -> dict[str, object]:
            return {
                "x": x,
                "y": y,
                "reward": e.bd.reward,
                "candidate_id": e.snapshot.candidate_id,
                "token_cost": e.bd.token_cost,
                "verification_depth": e.bd.verification_depth,
                "tool_density": e.bd.tool_density,
                "exploration_ratio": e.bd.exploration_ratio,
                "deliberation_ratio": e.bd.deliberation_ratio,
                "task_ids": list(e.task_ids),
                "discipline": e.discipline,
                "run_id": e.run_id,
            }

        if len(entries) == 1:
            return [_entry_to_point(entries[0])]

        # Build matrix of normalised BDs for PCA (scale-invariant projection).
        matrix = np.array([_bd_to_normalised(e.bd) for e in entries])  # (n, 6)

        # Mean-centred PCA — keep first 2 principal components.
        centred = matrix - matrix.mean(axis=0)
        _, _, vt = np.linalg.svd(centred, full_matrices=False)
        components = vt[:2]  # (2, 6)
        projected = centred @ components.T  # (n, 2)

        return [_entry_to_point(e, x=float(projected[i, 0]), y=float(projected[i, 1])) for i, e in enumerate(entries)]

    def project_2d_with_centroids(
        self,
        agent_map: dict[str, str] | None = None,
    ) -> list[dict[str, object]]:
        """PCA-project all CVT centroids (occupied + empty) to 2D for Voronoi visualisation.

        Unlike project_2d(), this returns all n_centroids cells so that empty cells can be
        rendered as faint outlines alongside occupied cells in the Voronoi territory map.

        Parameters
        ----------
        agent_map:
            Optional mapping of candidate_id -> agent_id, used to tag
            occupied centroids with the agent that produced them.
        """
        if agent_map is None:
            agent_map = {}

        centroids = self._archive.centroids  # shape (n_centroids, 6)
        n = len(centroids)

        # Normalise each dimension to [0, 1] before PCA so that token_cost
        # (0–500 000) does not dominate the projection.
        normalised = np.zeros_like(centroids, dtype=float)
        for dim_idx, (lo, hi) in enumerate(_BD_RANGES):
            span = hi - lo
            if span > 0.0:
                normalised[:, dim_idx] = np.clip((centroids[:, dim_idx] - lo) / span, 0.0, 1.0)

        mean = normalised.mean(axis=0)
        centred = normalised - mean

        if n < 2:
            proj = centred[:, :2] if centred.shape[1] >= 2 else np.zeros((n, 2))
        else:
            _, _, vt = np.linalg.svd(centred, full_matrices=False)
            proj = centred @ vt[:2].T  # (n, 2)

        result: list[dict[str, object]] = []
        for i in range(n):
            entry = self._entries.get(i)
            if entry is not None:
                candidate_id = entry.snapshot.candidate_id
                result.append(
                    {
                        "x": float(proj[i, 0]),
                        "y": float(proj[i, 1]),
                        "occupied": True,
                        "reward": entry.bd.reward,
                        "candidate_id": candidate_id,
                        "agent_id": agent_map.get(candidate_id),
                        "token_cost": entry.bd.token_cost,
                        "verification_depth": entry.bd.verification_depth,
                        "tool_density": entry.bd.tool_density,
                        "exploration_ratio": entry.bd.exploration_ratio,
                        "deliberation_ratio": entry.bd.deliberation_ratio,
                    }
                )
            else:
                result.append(
                    {
                        "x": float(proj[i, 0]),
                        "y": float(proj[i, 1]),
                        "occupied": False,
                    }
                )

        return result

    def to_summary(self) -> dict[str, object]:
        """Return a summary dict describing archive state and statistics."""
        objectives = [e.bd.reward for e in self._entries.values()]
        disciplines = sorted({e.discipline for e in self._entries.values() if e.discipline})
        task_ids = sorted({tid for e in self._entries.values() for tid in e.task_ids})
        return {
            "size": self.size,
            "n_centroids": self._n_centroids,
            "coverage": self.size / self._n_centroids if self._n_centroids > 0 else 0.0,
            "best_reward": max(objectives) if objectives else 0.0,
            "mean_reward": float(np.mean(objectives)) if objectives else 0.0,
            "disciplines": disciplines,
            "task_ids": task_ids,
            "bd_dimensions": [
                "token_cost",
                "verification_depth",
                "tool_density",
                "exploration_ratio",
                "deliberation_ratio",
                "reward",
            ],
        }

    def top_k(self, k: int = 5) -> list[ArchiveEntry]:
        """Return the top-k entries sorted by reward descending."""
        entries = list(self._entries.values())
        entries.sort(key=lambda e: e.bd.reward, reverse=True)
        return entries[:k]

    def frontier(self, k: int = 5) -> list[ArchiveEntry]:
        """Return k diverse high-performing entries using greedy BD-space selection.

        Starts with the highest-reward entry, then greedily adds entries that are
        maximally distant (in normalised BD space) from all already-selected entries.
        """
        entries = list(self._entries.values())
        if not entries:
            return []
        k = min(k, len(entries))

        entries_sorted = sorted(entries, key=lambda e: e.bd.reward, reverse=True)
        selected = [entries_sorted[0]]
        remaining = entries_sorted[1:]

        while len(selected) < k and remaining:
            selected_vecs = np.array([_bd_to_normalised(e.bd) for e in selected])
            best_entry = None
            best_min_dist = -1.0
            for candidate in remaining:
                candidate_vec = _bd_to_normalised(candidate.bd)
                # Minimum distance from this candidate to any already-selected entry.
                dists = np.linalg.norm(selected_vecs - candidate_vec, axis=1)
                min_dist = float(dists.min())
                if min_dist > best_min_dist:
                    best_min_dist = min_dist
                    best_entry = candidate
            if best_entry is None:
                break
            selected.append(best_entry)
            remaining = [e for e in remaining if e is not best_entry]

        return selected

    def coverage_report(self) -> ArchiveCoverage:
        """Return archive occupancy statistics.

        Returns a dict with keys: occupied, empty, coverage, total_centroids.
        """
        occupied = self.size
        return {
            "occupied": occupied,
            "empty": self._n_centroids - occupied,
            "coverage": occupied / self._n_centroids if self._n_centroids > 0 else 0.0,
            "total_centroids": self._n_centroids,
        }

    def get_entry_by_candidate_id(self, candidate_id: str) -> ArchiveEntry | None:
        """Return the archive entry for one candidate ID."""
        for entry in self._entries.values():
            if entry.snapshot.candidate_id == candidate_id:
                return entry
        return None

    def save(self, path: Path) -> None:
        """Serialise the archive to JSON at the given path.

        Each occupied cell is written as an entry containing the behaviour
        descriptor, workspace snapshot, and objective value so the archive can
        be fully reconstructed via load().
        """
        entries = []
        for entry in self._entries.values():
            entries.append(
                {
                    "cell_index": entry.cell_index,
                    "bd": entry.bd.model_dump(),
                    "snapshot": entry.snapshot.model_dump(),
                    "objective": entry.bd.reward,
                    "task_ids": list(entry.task_ids),
                    "discipline": entry.discipline,
                    "run_id": entry.run_id,
                }
            )
        payload = {"n_centroids": self._n_centroids, "seed": self._seed, "entries": entries}
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> QDArchive:
        """Load an archive from a JSON file previously written by save().

        Returns a fresh empty archive when the file does not exist so callers
        do not need to guard against missing files on first run.
        """
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        archive = cls(n_centroids=data["n_centroids"], seed=data.get("seed", 42))
        for entry in data["entries"]:
            bd = BehaviourDescriptor(**entry["bd"])
            snapshot = WorkspaceSnapshot(**entry["snapshot"])
            archive.insert(
                bd,
                snapshot,
                task_ids=tuple(entry.get("task_ids", ())),
                discipline=entry.get("discipline", ""),
                run_id=entry.get("run_id", ""),
            )
        return archive
