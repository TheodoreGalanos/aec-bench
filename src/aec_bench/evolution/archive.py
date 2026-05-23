# ABOUTME: CVT-MAP-Elites archive for quality-diversity harness evolution.
# ABOUTME: Maintains diverse high-performing workspaces indexed by behaviour descriptors.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ribs.archives import CVTArchive

from aec_bench.contracts.evolution import BehaviourDescriptor, WorkspaceSnapshot


@dataclass(frozen=True)
class ArchiveEntry:
    """A single elite stored in the QD archive with provenance metadata."""

    snapshot: WorkspaceSnapshot
    bd: BehaviourDescriptor
    task_ids: tuple[str, ...] = ()
    discipline: str = ""
    run_id: str = ""


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
    ) -> bool:
        """Add a workspace snapshot to the archive.

        Returns True if the entry was accepted (new cell) or improved an existing
        cell's objective. Returns False when the cell already holds a better elite.
        Task metadata (task_ids, discipline, run_id) is stored alongside the entry
        for filtering and provenance.
        """
        measures = _bd_to_array(bd).reshape(1, -1)
        result = self._archive.add(
            solution=np.array([[0.0]]),
            objective=np.array([bd.reward]),
            measures=measures,
        )
        status = int(result["status"][0])
        # status 0 = not added, 1 = improved, 2 = new cell
        if status in (1, 2):
            index = int(self._archive.index_of(measures)[0])
            self._entries[index] = ArchiveEntry(
                snapshot=snapshot,
                bd=bd,
                task_ids=task_ids,
                discipline=discipline,
                run_id=run_id,
            )
            return True
        return False

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

    def project_2d(self) -> list[dict]:
        """PCA-project all archive entries to 2D for visualisation.

        Returns an empty list for an empty archive. Returns a single point at the
        origin when only one entry exists (PCA is undefined for a single sample).
        Each dict contains: x, y, reward, version, token_cost, verification_depth,
        tool_density, exploration_ratio, deliberation_ratio.
        """
        if self.size == 0:
            return []

        entries = list(self._entries.values())

        def _entry_to_point(e: ArchiveEntry, x: float = 0.0, y: float = 0.0) -> dict:
            return {
                "x": x,
                "y": y,
                "reward": e.bd.reward,
                "version": e.snapshot.workspace_version,
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
    ) -> list[dict]:
        """PCA-project all CVT centroids (occupied + empty) to 2D for Voronoi visualisation.

        Unlike project_2d(), this returns all n_centroids cells so that empty cells can be
        rendered as faint outlines alongside occupied cells in the Voronoi territory map.

        Parameters
        ----------
        agent_map:
            Optional mapping of workspace_version -> agent_id, used to tag
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

        result = []
        for i in range(n):
            entry = self._entries.get(i)
            if entry is not None:
                version = entry.snapshot.workspace_version
                result.append(
                    {
                        "x": float(proj[i, 0]),
                        "y": float(proj[i, 1]),
                        "occupied": True,
                        "reward": entry.bd.reward,
                        "version": version,
                        "agent_id": agent_map.get(version),
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

    def to_summary(self) -> dict:
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

    def coverage_report(self) -> dict:
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

    def get_entry_by_version(self, version: str) -> ArchiveEntry | None:
        """Return the entry whose snapshot.workspace_version matches version, or None."""
        for entry in self._entries.values():
            if entry.snapshot.workspace_version == version:
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
                    "bd": entry.bd.model_dump(),
                    "snapshot": entry.snapshot.model_dump(),
                    "objective": entry.bd.reward,
                    "task_ids": list(entry.task_ids),
                    "discipline": entry.discipline,
                    "run_id": entry.run_id,
                }
            )
        payload = {"n_centroids": self._n_centroids, "entries": entries}
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
        archive = cls(n_centroids=data["n_centroids"])
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
