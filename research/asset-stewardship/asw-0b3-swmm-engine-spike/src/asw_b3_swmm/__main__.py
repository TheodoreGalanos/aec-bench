# ABOUTME: Runs the isolated ASW-0B3 research CLI as a Python module.
# ABOUTME: Delegates all path and authority checks to the narrow CLI implementation.

from asw_b3_swmm.cli import main

raise SystemExit(main())
