# ABOUTME: Chart generator for P(f) droop curve multimodal benchmark task.
# ABOUTME: Produces a professional matplotlib plot with deadband shading, operating point, and annotations.

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as ticker  # noqa: E402


OUTPUT_PATH = Path("/workspace/pf_droop.png")


def compute_curve(
    rated_power_mw: float,
    system_freq_hz: float,
    deadband_hz: float,
    droop_pct: float,
    pmin_mw: float,
    pmax_mw: float,
    pref_mw: float,
    slope_mw_per_hz: float,
) -> tuple[list[float], list[float]]:
    """Compute the full piecewise-linear P(f) droop curve data points."""
    f_db_lower = system_freq_hz - deadband_hz
    f_db_upper = system_freq_hz + deadband_hz

    freqs: list[float] = []
    powers: list[float] = []

    # Frequency range: 2 Hz below and above nominal
    f_min = system_freq_hz - 2.0
    f_max = system_freq_hz + 2.0
    num_points = 500

    for i in range(num_points + 1):
        f = f_min + (f_max - f_min) * i / num_points
        freqs.append(f)

        if f < f_db_lower:
            p = pref_mw + slope_mw_per_hz * (f_db_lower - f)
        elif f > f_db_upper:
            p = pref_mw - slope_mw_per_hz * (f - f_db_upper)
        else:
            p = pref_mw

        p = max(pmin_mw, min(pmax_mw, p))
        powers.append(p)

    return freqs, powers


def create_chart(data: dict) -> Path:
    """Generate a professional P(f) droop curve chart and save to disk."""
    rated_power_mw = float(data["rated_power_mw"])
    system_freq_hz = float(data["system_freq_hz"])
    deadband_hz = float(data["deadband_hz"])
    droop_pct = float(data["droop_pct"])
    pmin_mw = float(data["pmin_mw"])
    pmax_mw = float(data["pmax_mw"])
    pref_mw = float(data["pref_mw"])
    operating_freq_hz = float(data["operating_freq_hz"])
    slope_mw_per_hz = float(data["slope_mw_per_hz"])
    active_power_mw = float(data["active_power_mw"])
    delta_p_mw = float(data["delta_p_mw"])

    f_db_lower = system_freq_hz - deadband_hz
    f_db_upper = system_freq_hz + deadband_hz

    freqs, powers = compute_curve(
        rated_power_mw,
        system_freq_hz,
        deadband_hz,
        droop_pct,
        pmin_mw,
        pmax_mw,
        pref_mw,
        slope_mw_per_hz,
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    # Droop curve
    ax.plot(freqs, powers, color="#1f4e79", linewidth=2.0, label="P(f) droop curve")

    # Deadband shading
    ax.axvspan(f_db_lower, f_db_upper, alpha=0.15, color="#5b9bd5", label="Deadband region")

    # Pref reference line
    ax.axhline(
        y=pref_mw,
        color="#7f7f7f",
        linestyle="--",
        linewidth=1.0,
        label=f"Pref = {pref_mw:.1f} MW",
    )

    # Operating point
    ax.plot(
        operating_freq_hz,
        active_power_mw,
        marker="o",
        markersize=10,
        color="#2ca02c",
        zorder=5,
        label=f"Operating point ({operating_freq_hz:.1f} Hz, {active_power_mw:.1f} MW)",
    )

    # Delta-P annotation arrow from Pref down to operating point
    ax.annotate(
        f"\u0394P = {delta_p_mw:+.1f} MW",
        xy=(operating_freq_hz, active_power_mw),
        xytext=(operating_freq_hz + 0.3, pref_mw - 5),
        fontsize=10,
        fontweight="bold",
        color="#d62728",
        arrowprops=dict(arrowstyle="->", color="#d62728", linewidth=1.5),
        ha="left",
        va="top",
    )

    # Project parameters box
    param_text = (
        f"Rated power: {rated_power_mw:.0f} MW\n"
        f"Nominal freq: {system_freq_hz:.0f} Hz\n"
        f"Deadband: \u00b1{deadband_hz:.1f} Hz\n"
        f"Droop: {droop_pct:.0f}%\n"
        f"Slope: {slope_mw_per_hz:.1f} MW/Hz"
    )
    props = dict(boxstyle="round,pad=0.5", facecolor="#f2f2f2", edgecolor="#999999", alpha=0.9)
    ax.text(
        0.02,
        0.98,
        param_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=props,
        family="monospace",
    )

    # Axes and grid
    ax.set_xlabel("Frequency [Hz]", fontsize=12)
    ax.set_ylabel("Active Power [MW]", fontsize=12)
    ax.set_title("P(f) Droop Control Characteristic", fontsize=14, fontweight="bold")
    ax.set_xlim(system_freq_hz - 2.0, system_freq_hz + 2.0)
    ax.set_ylim(pmin_mw - 10, pmax_mw + 10)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(0.5))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(25))
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper right", fontsize=9)

    fig.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return OUTPUT_PATH


def main() -> None:
    """Entry point: parse JSON argument and generate chart."""
    if len(sys.argv) < 2:
        print("Usage: create_chart.py '<json_string>'", file=sys.stderr)
        sys.exit(1)

    data = json.loads(sys.argv[1])
    output_path = create_chart(data)

    print(f"P(f) droop curve chart saved to {output_path}")
    print(f"IMAGE:{output_path}")


if __name__ == "__main__":
    main()
