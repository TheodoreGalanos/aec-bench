# ABOUTME: Extracts allowlisted W1 hydraulic series through EPA SWMM's official output API.
# ABOUTME: Resolves elements by name and rejects version, units, inventory, period, length, or finiteness drift.

from __future__ import annotations

import ctypes
import math
from pathlib import Path
from typing import Any

SMO_NODE = 1
SMO_LINK = 2
SMO_REPORT_STEP = 0
SMO_NUM_PERIODS = 1
NODE_DEPTH = 0
NODE_HEAD = 1
NODE_VOLUME = 2
NODE_LATERAL_INFLOW = 3
NODE_FLOODING = 5
LINK_FLOW = 0


class OutputError(RuntimeError):
    """Raised when the official SWMM output boundary differs from W1."""


class SwmmOutput:
    """Minimal owner of one official SWMM output-library handle."""

    def __init__(self, output_path: Path, library_path: Path) -> None:
        if not output_path.is_file() or output_path.is_symlink():
            raise OutputError("binary output must be one regular file")
        if not library_path.is_file() or library_path.is_symlink():
            raise OutputError("output library must be one regular file")
        self._library = ctypes.CDLL(str(library_path.resolve()))
        self._configure()
        self._handle = ctypes.c_void_p()
        self._check(self._library.SMO_init(ctypes.byref(self._handle)), "SMO_init")
        self._check(
            self._library.SMO_open(
                self._handle,
                str(output_path.resolve()).encode(),
            ),
            "SMO_open",
        )
        self._closed = False

    def _configure(self) -> None:
        void_pointer_pointer = ctypes.POINTER(ctypes.c_void_p)
        self._library.SMO_init.argtypes = [void_pointer_pointer]
        self._library.SMO_init.restype = ctypes.c_int
        self._library.SMO_open.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._library.SMO_open.restype = ctypes.c_int
        self._library.SMO_close.argtypes = [void_pointer_pointer]
        self._library.SMO_close.restype = ctypes.c_int
        self._library.SMO_getVersion.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.SMO_getVersion.restype = ctypes.c_int
        self._library.SMO_getFlowUnits.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.SMO_getFlowUnits.restype = ctypes.c_int
        self._library.SMO_getProjectSize.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_int)),
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.SMO_getProjectSize.restype = ctypes.c_int
        self._library.SMO_getTimes.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.SMO_getTimes.restype = ctypes.c_int
        self._library.SMO_getElementName.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.SMO_getElementName.restype = ctypes.c_int
        for name in ("SMO_getNodeSeries", "SMO_getLinkSeries"):
            function = getattr(self._library, name)
            function.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
                ctypes.POINTER(ctypes.c_int),
            ]
            function.restype = ctypes.c_int
        self._library.SMO_free.argtypes = [void_pointer_pointer]
        self._library.SMO_free.restype = None

    def _check(self, code: int, operation: str) -> None:
        if code != 0:
            raise OutputError(f"{operation} failed with SWMM output API code {code}")

    def _free(self, pointer: Any) -> None:
        self._library.SMO_free(
            ctypes.cast(ctypes.byref(pointer), ctypes.POINTER(ctypes.c_void_p))
        )

    def _integer(self, function_name: str, *arguments: int) -> int:
        value = ctypes.c_int()
        function = getattr(self._library, function_name)
        self._check(
            function(self._handle, *arguments, ctypes.byref(value)),
            function_name,
        )
        return int(value.value)

    def project_size(self) -> list[int]:
        pointer = ctypes.POINTER(ctypes.c_int)()
        length = ctypes.c_int()
        self._check(
            self._library.SMO_getProjectSize(
                self._handle,
                ctypes.byref(pointer),
                ctypes.byref(length),
            ),
            "SMO_getProjectSize",
        )
        try:
            return [int(pointer[index]) for index in range(length.value)]
        finally:
            self._free(pointer)

    def element_names(self, element_type: int, count: int) -> list[str]:
        names: list[str] = []
        for index in range(count):
            pointer = ctypes.c_char_p()
            length = ctypes.c_int()
            self._check(
                self._library.SMO_getElementName(
                    self._handle,
                    element_type,
                    index,
                    ctypes.byref(pointer),
                    ctypes.byref(length),
                ),
                "SMO_getElementName",
            )
            try:
                names.append(pointer.value.decode("utf-8") if pointer.value else "")
            finally:
                self._free(pointer)
        return names

    def series(
        self,
        *,
        element_type: int,
        index: int,
        attribute: int,
        period_count: int,
    ) -> list[float]:
        pointer = ctypes.POINTER(ctypes.c_float)()
        length = ctypes.c_int()
        function_name = (
            "SMO_getNodeSeries" if element_type == SMO_NODE else "SMO_getLinkSeries"
        )
        function = getattr(self._library, function_name)
        self._check(
            function(
                self._handle,
                index,
                attribute,
                0,
                period_count,
                ctypes.byref(pointer),
                ctypes.byref(length),
            ),
            function_name,
        )
        try:
            values = [float(pointer[position]) for position in range(length.value)]
        finally:
            self._free(pointer)
        if len(values) != period_count or any(not math.isfinite(value) for value in values):
            raise OutputError(f"{function_name} returned invalid length or value")
        return values

    def close(self) -> None:
        if not self._closed:
            self._check(
                self._library.SMO_close(ctypes.byref(self._handle)),
                "SMO_close",
            )
            self._closed = True

    def __enter__(self) -> SwmmOutput:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _index(names: list[str], identity: str) -> int:
    try:
        return names.index(identity)
    except ValueError as error:
        raise OutputError(f"expected element {identity!r}; found {names!r}") from error


def extract_output(
    *,
    output_path: Path,
    output_library: Path,
    expected_periods: int,
    expected_report_step_s: int = 1,
) -> dict[str, Any]:
    """Extract the exact repaired-mapping W1 series and metadata by element name."""
    with SwmmOutput(output_path, output_library) as opened:
        version = opened._integer("SMO_getVersion")
        flow_units = opened._integer("SMO_getFlowUnits")
        report_step = opened._integer("SMO_getTimes", SMO_REPORT_STEP)
        period_count = opened._integer("SMO_getTimes", SMO_NUM_PERIODS)
        if version != 52004:
            raise OutputError(f"output API version is {version}, expected 52004")
        if flow_units != 4:
            raise OutputError(f"output flow unit is {flow_units}, expected LPS code 4")
        if (
            report_step != expected_report_step_s
            or period_count != expected_periods
        ):
            raise OutputError("output report step or period count differs")
        project_size = opened.project_size()
        if len(project_size) < 3:
            raise OutputError("output project-size vector is incomplete")
        node_names = opened.element_names(SMO_NODE, project_size[1])
        link_names = opened.element_names(SMO_LINK, project_size[2])
        if set(node_names) != {"O_HGL_A", "O_HGL_B", "WW_B4"} or len(node_names) != 3:
            raise OutputError(f"output node inventory differs: {node_names!r}")
        if set(link_names) != {"L_PA", "L_PB"} or len(link_names) != 2:
            raise OutputError(f"output link inventory differs: {link_names!r}")
        well = _index(node_names, "WW_B4")
        pump_a = _index(link_names, "L_PA")
        pump_b = _index(link_names, "L_PB")
        return {
            "flow_units_code": flow_units,
            "link_names": link_names,
            "node_names": node_names,
            "output_api_version": version,
            "period_count": period_count,
            "project_size": project_size,
            "report_step_seconds": report_step,
            "series": {
                "pump_a_flow_lps": opened.series(
                    element_type=SMO_LINK,
                    index=pump_a,
                    attribute=LINK_FLOW,
                    period_count=period_count,
                ),
                "pump_b_flow_lps": opened.series(
                    element_type=SMO_LINK,
                    index=pump_b,
                    attribute=LINK_FLOW,
                    period_count=period_count,
                ),
                "wet_well_depth_m": opened.series(
                    element_type=SMO_NODE,
                    index=well,
                    attribute=NODE_DEPTH,
                    period_count=period_count,
                ),
                "wet_well_head_m": opened.series(
                    element_type=SMO_NODE,
                    index=well,
                    attribute=NODE_HEAD,
                    period_count=period_count,
                ),
                "wet_well_inflow_lps": opened.series(
                    element_type=SMO_NODE,
                    index=well,
                    attribute=NODE_LATERAL_INFLOW,
                    period_count=period_count,
                ),
                "wet_well_overflow_lps": opened.series(
                    element_type=SMO_NODE,
                    index=well,
                    attribute=NODE_FLOODING,
                    period_count=period_count,
                ),
                "wet_well_volume_m3": opened.series(
                    element_type=SMO_NODE,
                    index=well,
                    attribute=NODE_VOLUME,
                    period_count=period_count,
                ),
            },
        }
