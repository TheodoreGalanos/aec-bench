# ABOUTME: Acquires source and realized runtime provenance for lifecycle invocations.
# ABOUTME: Hashes repository state and the exact installed dependency closure used by an adapter.

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
from collections import deque
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from aec_bench.model_routing import resolve_pydantic_provider

_REALIZED_FILE_DIGESTS: dict[Path, tuple[tuple[int, int, int, int, int], str]] = {}
_REQUIREMENT_PATTERN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([^]]+)\])?")
_EXTRA_MARKER_PATTERN = re.compile(r"\bextra\s*==\s*(['\"])([^'\"]+)\1")
_OPENAI_COMPATIBLE_PROVIDERS = {
    "alibaba",
    "azure",
    "cerebras",
    "deepseek",
    "fireworks",
    "github",
    "grok",
    "heroku",
    "litellm",
    "moonshotai",
    "nebius",
    "ollama",
    "openai",
    "openai-chat",
    "openai-responses",
    "ovhcloud",
    "sambanova",
    "together",
    "vercel",
}


def callable_provenance(value: Any) -> dict[str, Any]:
    """Identify one callable and the exact source file that implements it."""
    source_path = inspect.getsourcefile(value)
    path = Path(source_path) if source_path is not None else None
    return {
        "qualified_name": f"{getattr(value, '__module__', '')}.{getattr(value, '__qualname__', repr(value))}",
        "source_path": source_path,
        "source_sha256": _realized_file_sha256(path) if path is not None and path.is_file() else None,
    }


def runtime_dependency_provenance(
    *,
    adapter_kind: str,
    model_name: str,
    search_paths: tuple[Path, ...] | None = None,
) -> dict[str, Any]:
    """Hash the realized runtime distributions used by one lifecycle condition."""
    if adapter_kind not in {"deepseek_harness", "in_process", "tool_loop", "pydantic_ai"}:
        raise ValueError(f"unsupported lifecycle runtime adapter: {adapter_kind}")

    provider = _resolve_runtime_provider(adapter_kind, model_name)
    roots = tuple(Path(path).resolve() for path in (search_paths or _runtime_distribution_search_paths()))
    if not roots:
        raise ValueError("lifecycle runtime distribution search path is unavailable")
    distributions: dict[str, importlib_metadata.Distribution] = {}
    for root in roots:
        for candidate_distribution in importlib_metadata.distributions(path=[str(root)]):
            raw_name = candidate_distribution.metadata.get("Name")
            if raw_name:
                distributions.setdefault(_canonicalize_distribution_name(str(raw_name)), candidate_distribution)
    selected = _runtime_distribution_closure(distributions, adapter_kind, provider)
    digest = hashlib.sha256()
    identities: list[str] = []
    for name in sorted(selected):
        distribution = distributions.get(name)
        if distribution is None:
            identity = f"{name}==missing"
            identities.append(identity)
            _update_inventory_digest(digest, f"distribution/{name}", identity.encode("utf-8"))
            continue
        identity = f"{name}=={distribution.version}"
        identities.append(identity)
        _update_inventory_digest(digest, f"distribution/{name}", identity.encode("utf-8"))
        entries = _realized_distribution_entries(name, distribution)
        if not entries:
            raise ValueError(f"runtime distribution has no hashable realized files: {identity}")
        for relative, file_sha256 in entries:
            _update_inventory_digest(
                digest,
                f"distribution/{name}/{relative}",
                bytes.fromhex(file_sha256),
            )
    return {
        "adapter": adapter_kind,
        "provider": provider,
        "distributions": sorted(identities),
        "dependency_inventory_sha256": digest.hexdigest(),
    }


def _runtime_distribution_search_paths() -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw_path in sys.path:
        candidate = Path(raw_path or os.getcwd()).resolve()
        if not candidate.is_dir() or not any(candidate.glob("*.dist-info")):
            continue
        if candidate not in roots:
            roots.append(candidate)
    return tuple(roots)


def _runtime_distribution_closure(
    distributions: dict[str, importlib_metadata.Distribution],
    adapter_kind: str,
    provider: str,
) -> dict[str, set[str]]:
    if adapter_kind == "in_process":
        seeds: dict[str, set[str]] = {"pydantic": set(), "pyyaml": set()}
    elif adapter_kind == "deepseek_harness":
        seeds = {
            "deepseek-harness-runtime-bin": set(),
            "deepseek-harness-sdk": set(),
        }
    else:
        provider_extras, provider_distributions = _runtime_provider_dependencies(provider)
        seeds = {
            "httpx": set(),
            "pydantic": set(),
            "pydantic-ai": set(),
            "pydantic-ai-slim": provider_extras,
            "pyyaml": set(),
        }
        seeds.update({name: set() for name in provider_distributions})
    queue = deque((_canonicalize_distribution_name(name), extras) for name, extras in seeds.items())
    selected: dict[str, set[str]] = {}
    while queue:
        name, requested_extras = queue.popleft()
        if name in selected and requested_extras <= selected[name]:
            continue
        active_extras = selected.setdefault(name, set())
        active_extras.update(requested_extras)
        distribution = distributions.get(name)
        if distribution is None or name == "pydantic-ai":
            continue
        for raw_requirement in distribution.requires or ():
            parsed = _parse_distribution_requirement(raw_requirement, active_extras)
            if parsed is None:
                continue
            requirement_name, requirement_extras = parsed
            queue.append((requirement_name, requirement_extras))
    return selected


def _resolve_runtime_provider(adapter_kind: str, model_name: str) -> str:
    if adapter_kind == "in_process":
        return "in_process"
    if adapter_kind == "deepseek_harness":
        provider = model_name.partition(":")[0].strip().lower()
        if provider not in {"azure", "deepseek"}:
            raise ValueError(f"unsupported DeepSeek lifecycle provider: {provider or model_name}")
        return provider
    provider = resolve_pydantic_provider(model_name)
    if provider == "auto" and ":" in model_name:
        provider = model_name.split(":", maxsplit=1)[0]
    return "google-vertex" if provider == "vertexai" else provider


def _runtime_provider_dependencies(provider: str) -> tuple[set[str], set[str]]:
    selected = provider.removeprefix("gateway/")
    selected = {
        "chat": "openai",
        "converse": "bedrock",
        "gemini": "google-gla",
        "responses": "openai",
    }.get(selected, selected)
    if selected == "auto":
        return set(), set()
    if selected in _OPENAI_COMPATIBLE_PROVIDERS:
        return {"openai"}, {"openai"}
    mapping: dict[str, tuple[set[str], set[str]]] = {
        "anthropic": ({"anthropic"}, {"anthropic"}),
        "bedrock": ({"bedrock"}, {"boto3", "botocore"}),
        "cohere": ({"cohere"}, {"cohere"}),
        "google-gla": ({"google"}, {"google-genai"}),
        "google-vertex": ({"google", "vertexai"}, {"google-auth", "google-genai"}),
        "groq": ({"groq"}, {"groq"}),
        "huggingface": ({"huggingface"}, {"huggingface-hub"}),
        "mistral": ({"mistral"}, {"mistralai"}),
        "openrouter": ({"openrouter"}, {"openai"}),
        "sentence-transformers": ({"sentence-transformers"}, {"sentence-transformers"}),
        "voyageai": ({"voyageai"}, {"voyageai"}),
        "xai": ({"xai"}, {"xai-sdk"}),
    }
    try:
        return mapping[selected]
    except KeyError as exc:
        raise ValueError(f"unsupported lifecycle runtime provider dependency mapping: {provider}") from exc


def _canonicalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_distribution_requirement(raw_requirement: str, active_extras: set[str]) -> tuple[str, set[str]] | None:
    requirement, separator, marker = raw_requirement.partition(";")
    match = _REQUIREMENT_PATTERN.match(requirement)
    if match is None:
        raise ValueError(f"runtime distribution requirement is malformed: {raw_requirement}")
    if separator and "extra" in marker:
        marker_extras = {match.group(2) for match in _EXTRA_MARKER_PATTERN.finditer(marker)}
        if not marker_extras:
            raise ValueError(f"runtime distribution extra marker is unsupported: {raw_requirement}")
        if not active_extras.intersection(marker_extras):
            return None
    extras = {extra.strip() for extra in (match.group(2) or "").split(",") if extra.strip()}
    return _canonicalize_distribution_name(match.group(1)), extras


def _realized_distribution_entries(
    name: str,
    distribution: importlib_metadata.Distribution,
) -> list[tuple[str, str]]:
    entries: dict[str, str] = {}
    for package_path in distribution.files or ():
        relative = package_path.as_posix()
        if "__pycache__" in package_path.parts or package_path.suffix == ".pyc":
            continue
        path = Path(str(distribution.locate_file(package_path)))
        if path.is_file():
            entries[relative] = _realized_file_sha256(path)
        else:
            entries[relative] = hashlib.sha256(b"missing-realized-file").hexdigest()
    if not entries:
        for metadata_name in ("METADATA", "WHEEL", "entry_points.txt", "direct_url.json", "RECORD"):
            content = distribution.read_text(metadata_name)
            if content is not None:
                entries[f"metadata/{metadata_name}"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        root = Path(str(distribution.locate_file("")))
        candidates = _distribution_top_level_names(name, distribution)
        for candidate in candidates:
            package = root / candidate
            if package.is_file():
                entries[f"package/{candidate}"] = _realized_file_sha256(package)
            elif package.is_dir():
                for path in _runtime_source_files(package):
                    relative = path.relative_to(package).as_posix()
                    entries[f"package/{candidate}/{relative}"] = _realized_file_sha256(path)
    direct_url = distribution.read_text("direct_url.json")
    if direct_url is not None:
        entries.update(_editable_distribution_entries(name, direct_url))
    return sorted(entries.items())


def _distribution_top_level_names(
    name: str,
    distribution: importlib_metadata.Distribution,
) -> tuple[str, ...]:
    declared = distribution.read_text("top_level.txt") or ""
    names = {line.strip() for line in declared.splitlines() if line.strip()}
    names.add(name.replace("-", "_"))
    return tuple(sorted(names))


def _editable_distribution_entries(name: str, direct_url: str) -> dict[str, str]:
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError as exc:
        raise ValueError(f"runtime distribution direct_url.json is malformed: {name}") from exc
    if not isinstance(payload, dict) or not bool(payload.get("dir_info", {}).get("editable")):
        return {}
    parsed = urlparse(str(payload.get("url") or ""))
    if parsed.scheme != "file":
        raise ValueError(f"editable runtime distribution has unsupported source URL: {name}")
    source = Path(unquote(parsed.path)).resolve()
    if not source.is_dir():
        raise ValueError(f"editable runtime distribution source is unavailable: {name}")
    return {
        f"editable/{path.relative_to(source).as_posix()}": _realized_file_sha256(path)
        for path in _runtime_source_files(source)
    }


def _runtime_source_files(root: Path) -> list[Path]:
    excluded = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "build", "dist"}
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in excluded for part in path.relative_to(root).parts)
        and path.suffix != ".pyc"
    ]


def _realized_file_sha256(path: Path) -> str:
    stat = path.stat()
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    cached = _REALIZED_FILE_DIGESTS.get(path)
    if cached is not None and cached[0] == signature:
        return cached[1]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _REALIZED_FILE_DIGESTS[path] = (signature, digest)
    return digest


def _update_inventory_digest(digest: Any, label: str, payload: bytes) -> None:
    encoded_label = label.encode("utf-8")
    digest.update(len(encoded_label).to_bytes(8, "big"))
    digest.update(encoded_label)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def repository_provenance(repository_dir: Path) -> dict[str, Any]:
    """Bind one lifecycle invocation to its exact repository or source-tree bytes."""
    source_root = _source_inventory_root(repository_dir)
    source_package = _source_package_dir(source_root)
    try:
        root = _git(repository_dir, "rev-parse", "--show-toplevel").decode().strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _source_tree_provenance(source_root, source_package)
    root_path = Path(root)
    if not _source_package_is_tracked(root_path, source_package):
        return _source_tree_provenance(source_root, source_package)
    commit = _git(root_path, "rev-parse", "HEAD").decode().strip()
    status = _git(root_path, "status", "--porcelain=v1", "--untracked-files=all")
    diff = _git(root_path, "diff", "--binary", "HEAD")
    untracked = _git(root_path, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    digest = hashlib.sha256()
    digest.update(status)
    digest.update(diff)
    for raw_path in sorted(path for path in untracked if path):
        path = root_path / raw_path.decode()
        digest.update(raw_path)
        if path.is_file():
            digest.update(path.read_bytes())
    return {
        "root": str(root_path),
        "commit": commit,
        "dirty": bool(status.strip()),
        "dirty_digest": digest.hexdigest(),
        "source_inventory_sha256": _source_inventory_sha256(root_path, source_package),
        "repository_kind": "git",
    }


def _source_inventory_sha256(root: Path, source_package: Path | None = None) -> str:
    selected = [root / "pyproject.toml", root / "uv.lock"]
    source_root = source_package or _source_package_dir(root)
    if source_root.is_dir():
        selected.extend(
            path
            for path in source_root.rglob("*")
            if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    for pattern in ("*.dist-info/METADATA", "*.dist-info/direct_url.json"):
        selected.extend(path for path in root.glob(pattern) if path.is_file() and not path.is_symlink())
    digest = hashlib.sha256()
    for path in sorted(path for path in selected if path.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _source_tree_provenance(root: Path, source_package: Path) -> dict[str, Any]:
    inventory = _source_inventory_sha256(root, source_package)
    return {
        "root": str(root),
        "commit": f"source-sha256:{inventory}",
        "dirty": False,
        "dirty_digest": hashlib.sha256(b"").hexdigest(),
        "source_inventory_sha256": inventory,
        "repository_kind": "source_tree",
    }


def _source_package_dir(root: Path) -> Path:
    source = root / "src" / "aec_bench"
    return source if source.is_dir() else root / "aec_bench"


def _source_package_is_tracked(repository_root: Path, package_dir: Path) -> bool:
    try:
        relative = (package_dir / "__init__.py").resolve().relative_to(repository_root.resolve())
        _git(repository_root, "ls-files", "--error-unmatch", "--", relative.as_posix())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return False
    return True


def _source_inventory_root(repository_dir: Path) -> Path:
    candidate = Path(repository_dir).resolve()
    for parent in (candidate, *candidate.parents):
        if (parent / "src" / "aec_bench").is_dir() or (parent / "aec_bench").is_dir():
            return parent
        if parent.name == "aec_bench" and parent.is_dir():
            return parent.parent
    raise ValueError(f"aec_bench source inventory is unavailable from {repository_dir}")


def _git(cwd: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )
    return completed.stdout


__all__ = ("callable_provenance", "repository_provenance", "runtime_dependency_provenance")
