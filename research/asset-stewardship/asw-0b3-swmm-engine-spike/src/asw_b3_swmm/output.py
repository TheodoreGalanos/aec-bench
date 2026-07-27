# ABOUTME: Extracts an allowlisted semantic result through the official SWMM output API.
# ABOUTME: Computes expected periods and replay hashes independently from engine-reported metadata.

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path

from asw_b3_swmm.constants import SWMM_FLOW_UNIT_LPS, SWMM_OUTPUT_VERSION
from asw_b3_swmm.specification import Probe, Specification


class OutputContractError(RuntimeError):
    """Raised when SWMM output violates the B3 semantic extraction boundary."""


def expected_period_count(horizon_seconds: int, report_step_seconds: int) -> int:
    """Calculate period count without consulting the engine output file."""
    if horizon_seconds <= 0 or report_step_seconds <= 0:
        raise OutputContractError("horizon and report step must be positive")
    periods, remainder = divmod(horizon_seconds, report_step_seconds)
    if remainder:
        raise OutputContractError("report step must divide the horizon exactly")
    return periods


def canonical_semantic_hash(payload: dict[str, object]) -> str:
    """Hash canonical JSON while rejecting NaN and path-dependent formatting."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class OutputApi:
    """Minimal ctypes boundary around the pinned official SWMM output library."""

    _ELEMENT_NODE = 1
    _ELEMENT_LINK = 2
    _TIME_REPORT_STEP = 0
    _TIME_NUM_PERIODS = 1
    _NODE_DEPTH = 0
    _NODE_VOLUME = 2
    _NODE_FLOODING = 5
    _LINK_FLOW = 0

    def __init__(self, library_path: Path) -> None:
        try:
            self._library = ctypes.CDLL(str(library_path))
        except OSError as exc:
            raise OutputContractError(f"cannot load pinned output library: {exc}") from exc
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        library = self._library
        handle = ctypes.c_void_p
        void_pointer = ctypes.c_void_p
        library.SMO_init.argtypes = [ctypes.POINTER(handle)]
        library.SMO_init.restype = ctypes.c_int
        library.SMO_open.argtypes = [handle, ctypes.c_char_p]
        library.SMO_open.restype = ctypes.c_int
        library.SMO_close.argtypes = [ctypes.POINTER(handle)]
        library.SMO_close.restype = ctypes.c_int
        library.SMO_getVersion.argtypes = [handle, ctypes.POINTER(ctypes.c_int)]
        library.SMO_getVersion.restype = ctypes.c_int
        library.SMO_getProjectSize.argtypes = [
            handle,
            ctypes.POINTER(void_pointer),
            ctypes.POINTER(ctypes.c_int),
        ]
        library.SMO_getProjectSize.restype = ctypes.c_int
        library.SMO_getFlowUnits.argtypes = [handle, ctypes.POINTER(ctypes.c_int)]
        library.SMO_getFlowUnits.restype = ctypes.c_int
        library.SMO_getTimes.argtypes = [handle, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        library.SMO_getTimes.restype = ctypes.c_int
        library.SMO_getElementName.argtypes = [
            handle,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(void_pointer),
            ctypes.POINTER(ctypes.c_int),
        ]
        library.SMO_getElementName.restype = ctypes.c_int
        series_arguments = [
            handle,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(void_pointer),
            ctypes.POINTER(ctypes.c_int),
        ]
        library.SMO_getNodeSeries.argtypes = series_arguments
        library.SMO_getNodeSeries.restype = ctypes.c_int
        library.SMO_getLinkSeries.argtypes = series_arguments
        library.SMO_getLinkSeries.restype = ctypes.c_int
        library.SMO_free.argtypes = [ctypes.POINTER(void_pointer)]
        library.SMO_free.restype = None

    @staticmethod
    def _check(code: int, operation: str) -> None:
        if code != 0:
            raise OutputContractError(f"{operation} failed with SWMM output API code {code}")

    def _integer(self, function_name: str, handle: ctypes.c_void_p, code: int | None = None) -> int:
        output = ctypes.c_int()
        function = getattr(self._library, function_name)
        if code is None:
            result = function(handle, ctypes.byref(output))
        else:
            result = function(handle, code, ctypes.byref(output))
        self._check(result, function_name)
        return output.value

    def _project_size(self, handle: ctypes.c_void_p) -> tuple[int, ...]:
        pointer = ctypes.c_void_p()
        length = ctypes.c_int()
        self._check(
            self._library.SMO_getProjectSize(handle, ctypes.byref(pointer), ctypes.byref(length)),
            "SMO_getProjectSize",
        )
        try:
            values = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int))
            return tuple(values[index] for index in range(length.value))
        finally:
            self._library.SMO_free(ctypes.byref(pointer))

    def _element_names(self, handle: ctypes.c_void_p, element_type: int, count: int) -> tuple[str, ...]:
        names: list[str] = []
        for index in range(count):
            pointer = ctypes.c_void_p()
            length = ctypes.c_int()
            self._check(
                self._library.SMO_getElementName(
                    handle,
                    element_type,
                    index,
                    ctypes.byref(pointer),
                    ctypes.byref(length),
                ),
                "SMO_getElementName",
            )
            try:
                names.append(ctypes.string_at(pointer, length.value).decode("utf-8"))
            finally:
                self._library.SMO_free(ctypes.byref(pointer))
        return tuple(names)

    def _series(
        self,
        function_name: str,
        handle: ctypes.c_void_p,
        element_index: int,
        attribute: int,
        periods: int,
    ) -> list[float]:
        pointer = ctypes.c_void_p()
        length = ctypes.c_int()
        function = getattr(self._library, function_name)
        self._check(
            function(
                handle,
                element_index,
                attribute,
                0,
                periods,
                ctypes.byref(pointer),
                ctypes.byref(length),
            ),
            function_name,
        )
        try:
            if length.value != periods:
                raise OutputContractError(f"{function_name} returned {length.value} values for {periods} periods")
            values = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_float))
            return [float(values[index]) for index in range(length.value)]
        finally:
            self._library.SMO_free(ctypes.byref(pointer))

    def extract(self, output_path: Path, specification: Specification, probe: Probe) -> dict[str, object]:
        """Extract only semantic series required for the B3 role decision."""
        if not output_path.is_file():
            raise OutputContractError(f"SWMM output does not exist: {output_path}")
        handle = ctypes.c_void_p()
        self._check(self._library.SMO_init(ctypes.byref(handle)), "SMO_init")
        opened = False
        try:
            open_code = self._library.SMO_open(handle, os.fsencode(output_path))
            if open_code != 0:
                raise OutputContractError(f"SMO_open failed with SWMM output API code {open_code}")
            opened = True
            engine_version = self._integer("SMO_getVersion", handle)
            flow_units = self._integer("SMO_getFlowUnits", handle)
            report_step = self._integer("SMO_getTimes", handle, self._TIME_REPORT_STEP)
            period_count = self._integer("SMO_getTimes", handle, self._TIME_NUM_PERIODS)
            expected = expected_period_count(
                specification.simulation.horizon_seconds,
                specification.simulation.report_step_seconds,
            )
            if engine_version != SWMM_OUTPUT_VERSION:
                raise OutputContractError(f"output version is {engine_version}, expected {SWMM_OUTPUT_VERSION}")
            if flow_units != SWMM_FLOW_UNIT_LPS:
                raise OutputContractError(f"output flow-unit code is {flow_units}, expected LPS")
            if report_step != specification.simulation.report_step_seconds:
                raise OutputContractError(
                    f"output report step is {report_step}, expected {specification.simulation.report_step_seconds}"
                )
            if period_count != expected:
                raise OutputContractError(f"output contains {period_count} periods, independently expected {expected}")

            project_size = self._project_size(handle)
            if len(project_size) < 3:
                raise OutputContractError(f"unexpected project-size vector: {project_size!r}")
            node_names = self._element_names(handle, self._ELEMENT_NODE, project_size[1])
            link_names = self._element_names(handle, self._ELEMENT_LINK, project_size[2])
            expected_nodes = {"DISCHARGE", "OUTFALL", "WET_WELL"}
            expected_links = {"FORCE_MAIN", "PUMP_A", "PUMP_B"}
            if set(node_names) != expected_nodes or set(link_names) != expected_links:
                raise OutputContractError(f"unexpected model elements: nodes={node_names!r}, links={link_names!r}")
            node_index = {name: index for index, name in enumerate(node_names)}
            link_index = {name: index for index, name in enumerate(link_names)}
            series = {
                "wet_well_depth_m": self._series(
                    "SMO_getNodeSeries",
                    handle,
                    node_index["WET_WELL"],
                    self._NODE_DEPTH,
                    period_count,
                ),
                "wet_well_volume_m3": self._series(
                    "SMO_getNodeSeries",
                    handle,
                    node_index["WET_WELL"],
                    self._NODE_VOLUME,
                    period_count,
                ),
                "wet_well_flooding_lps": self._series(
                    "SMO_getNodeSeries",
                    handle,
                    node_index["WET_WELL"],
                    self._NODE_FLOODING,
                    period_count,
                ),
                "pump_a_flow_lps": self._series(
                    "SMO_getLinkSeries",
                    handle,
                    link_index["PUMP_A"],
                    self._LINK_FLOW,
                    period_count,
                ),
                "pump_b_flow_lps": self._series(
                    "SMO_getLinkSeries",
                    handle,
                    link_index["PUMP_B"],
                    self._LINK_FLOW,
                    period_count,
                ),
                "force_main_flow_lps": self._series(
                    "SMO_getLinkSeries",
                    handle,
                    link_index["FORCE_MAIN"],
                    self._LINK_FLOW,
                    period_count,
                ),
            }
            return {
                "probe_id": probe.probe_id,
                "active_pump": probe.active_pump,
                "inactive_pump": probe.inactive_pump,
                "engine_version": engine_version,
                "flow_units": "LPS",
                "report_step_seconds": report_step,
                "period_count": period_count,
                "expected_period_count": expected,
                "elements": {
                    "nodes": list(node_names),
                    "links": list(link_names),
                },
                "series": series,
            }
        finally:
            if opened:
                self._check(self._library.SMO_close(ctypes.byref(handle)), "SMO_close")
