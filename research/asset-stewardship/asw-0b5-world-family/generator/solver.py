# ABOUTME: Drives the pinned SWMM solver lifecycle and captures exact pump settings at report instants.
# ABOUTME: Uses the real C API, saves hydraulic output, and rejects lifecycle, alignment, or setting failures.

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

SWMM_LINK = 3
SWMM_LINK_SETTING = 407
ERROR_BUFFER_SIZE = 512


class SolverError(RuntimeError):
    """Raised when the pinned SWMM solver lifecycle or setting trace fails."""


@dataclass(frozen=True)
class SolverRun:
    """Path-free solver lifecycle facts and exact setting arrays."""

    lifecycle_return_codes: dict[str, int]
    pump_a_settings: tuple[int, ...]
    pump_b_settings: tuple[int, ...]
    warning_count: int


def _configure(library: ctypes.CDLL) -> None:
    library.swmm_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    library.swmm_open.restype = ctypes.c_int
    library.swmm_start.argtypes = [ctypes.c_int]
    library.swmm_start.restype = ctypes.c_int
    library.swmm_step.argtypes = [ctypes.POINTER(ctypes.c_double)]
    library.swmm_step.restype = ctypes.c_int
    library.swmm_end.argtypes = []
    library.swmm_end.restype = ctypes.c_int
    library.swmm_report.argtypes = []
    library.swmm_report.restype = ctypes.c_int
    library.swmm_close.argtypes = []
    library.swmm_close.restype = ctypes.c_int
    library.swmm_getError.argtypes = [ctypes.c_char_p, ctypes.c_int]
    library.swmm_getError.restype = ctypes.c_int
    library.swmm_getWarnings.argtypes = []
    library.swmm_getWarnings.restype = ctypes.c_int
    library.swmm_getIndex.argtypes = [ctypes.c_int, ctypes.c_char_p]
    library.swmm_getIndex.restype = ctypes.c_int
    library.swmm_getValue.argtypes = [ctypes.c_int, ctypes.c_int]
    library.swmm_getValue.restype = ctypes.c_double


def _error_text(library: ctypes.CDLL) -> str:
    buffer = ctypes.create_string_buffer(ERROR_BUFFER_SIZE)
    library.swmm_getError(buffer, ERROR_BUFFER_SIZE)
    return buffer.value.decode("utf-8", errors="replace").strip()


def _check(library: ctypes.CDLL, code: int, operation: str) -> None:
    if code != 0:
        detail = _error_text(library)
        raise SolverError(f"{operation} failed with SWMM code {code}: {detail}")


def _setting(library: ctypes.CDLL, link_index: int, link_name: str) -> int:
    value = float(library.swmm_getValue(SWMM_LINK_SETTING, link_index))
    if value not in {0.0, 1.0}:
        raise SolverError(f"{link_name} setting must be exact 0 or 1, received {value!r}")
    return int(value)


def run_lifecycle(
    *,
    input_path: Path,
    report_path: Path,
    output_path: Path,
    solver_library: Path,
    expected_periods: int,
) -> SolverRun:
    """Run one real SWMM segment and record settings after every one-second step."""
    for role, path in (
        ("input", input_path),
        ("solver library", solver_library),
    ):
        if not path.is_file() or path.is_symlink():
            raise SolverError(f"{role} must be one regular file")
    for role, path in (("report", report_path), ("output", output_path)):
        if path.exists() or path.is_symlink():
            raise SolverError(f"{role} path must be absent")
    if expected_periods <= 0:
        raise SolverError("expected period count must be positive")

    library = ctypes.CDLL(str(solver_library.resolve()))
    _configure(library)
    codes: dict[str, int] = {}
    opened = False
    started = False
    ended = False
    pump_a: list[int] = []
    pump_b: list[int] = []
    try:
        codes["open"] = int(
            library.swmm_open(
                str(input_path.resolve()).encode(),
                str(report_path.resolve()).encode(),
                str(output_path.resolve()).encode(),
            )
        )
        _check(library, codes["open"], "swmm_open")
        opened = True
        pump_a_index = int(library.swmm_getIndex(SWMM_LINK, b"L_PA"))
        pump_b_index = int(library.swmm_getIndex(SWMM_LINK, b"L_PB"))
        if pump_a_index < 0 or pump_b_index < 0 or pump_a_index == pump_b_index:
            raise SolverError("exact Pump A and Pump B link identities are absent")
        codes["start"] = int(library.swmm_start(1))
        _check(library, codes["start"], "swmm_start")
        started = True
        while True:
            elapsed_days = ctypes.c_double()
            code = int(library.swmm_step(ctypes.byref(elapsed_days)))
            codes["step"] = code
            _check(library, code, "swmm_step")
            pump_a.append(_setting(library, pump_a_index, "L_PA"))
            pump_b.append(_setting(library, pump_b_index, "L_PB"))
            if len(pump_a) > expected_periods:
                raise SolverError("solver produced more setting instants than expected")
            if elapsed_days.value <= 0.0:
                break
        if len(pump_a) != expected_periods:
            raise SolverError(
                f"solver setting trace has {len(pump_a)} periods, expected {expected_periods}"
            )
        codes["end"] = int(library.swmm_end())
        _check(library, codes["end"], "swmm_end")
        ended = True
        codes["report"] = int(library.swmm_report())
        _check(library, codes["report"], "swmm_report")
        warning_count = int(library.swmm_getWarnings())
    finally:
        if started and not ended:
            library.swmm_end()
        if opened:
            codes["close"] = int(library.swmm_close())
    if codes.get("close") != 0:
        raise SolverError(f"swmm_close failed with SWMM code {codes.get('close')}")
    if warning_count != 0:
        raise SolverError(f"solver reported {warning_count} warning(s)")
    if not report_path.is_file() or not output_path.is_file():
        raise SolverError("solver did not create both report and binary output")
    return SolverRun(
        lifecycle_return_codes=codes,
        pump_a_settings=tuple(pump_a),
        pump_b_settings=tuple(pump_b),
        warning_count=warning_count,
    )
