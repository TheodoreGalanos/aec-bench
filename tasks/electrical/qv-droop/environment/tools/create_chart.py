# ABOUTME: Chart generator for Q(V) droop curve multimodal benchmark task.
# ABOUTME: Produces a professional matplotlib plot with deadband shading, operating point, and annotations.

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as ticker  # noqa: E402


OUTPUT_PATH = Path("/workspace/qv_droop.png")


def compute_curve(
    rated_reactive_power_mvar: float,
    base_voltage_pu: float,
    deadband_pu: float,
    droop_pct: float,
    qmin_mvar: float,
    qmax_mvar: float,
    qnormal_mvar: float,
    vref_pu: float,
    slope_mvar_per_pu: float,
) -> tuple[list[float], list[float]]:
    """Compute the full piecewise-linear Q(V) droop curve data points."""
    v_db_lower = vref_pu - deadband_pu
    v_db_upper = vref_pu + deadband_pu

    voltages: list[float] = []
    reactive_powers: list[float] = []

    # Voltage range: 0.10 p.u. below and above nominal
    v_min = vref_pu - 0.10
    v_max = vref_pu + 0.10
    num_points = 500

    for i in range(num_points + 1):
        v = v_min + (v_max - v_min) * i / num_points
        voltages.append(v)

        if v < v_db_lower:
            # Low voltage: inject reactive power (positive Q)
            q = qnormal_mvar + slope_mvar_per_pu * (v_db_lower - v)
        elif v > v_db_upper:
            # High voltage: absorb reactive power (negative Q)
            q = qnormal_mvar - slope_mvar_per_pu * (v - v_db_upper)
        else:
            q = qnormal_mvar

        q = max(qmin_mvar, min(qmax_mvar, q))
        reactive_powers.append(q)

    return voltages, reactive_powers


def create_chart(data: dict) -> Path:
    """Generate a professional Q(V) droop curve chart and save to disk."""
    rated_reactive_power_mvar = float(data["rated_reactive_power_mvar"])
    base_voltage_pu = float(data["base_voltage_pu"])
    deadband_pu = float(data["deadband_pu"])
    droop_pct = float(data["droop_pct"])
    qmin_mvar = float(data["qmin_mvar"])
    qmax_mvar = float(data["qmax_mvar"])
    qnormal_mvar = float(data["qnormal_mvar"])
    vref_pu = float(data["vref_pu"])
    operating_voltage_pu = float(data["operating_voltage_pu"])
    slope_mvar_per_pu = float(data["slope_mvar_per_pu"])
    reactive_power_mvar = float(data["reactive_power_mvar"])
    delta_q_mvar = float(data["delta_q_mvar"])

    v_db_lower = vref_pu - deadband_pu
    v_db_upper = vref_pu + deadband_pu

    voltages, reactive_powers = compute_curve(
        rated_reactive_power_mvar,
        base_voltage_pu,
        deadband_pu,
        droop_pct,
        qmin_mvar,
        qmax_mvar,
        qnormal_mvar,
        vref_pu,
        slope_mvar_per_pu,
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    # Droop curve
    ax.plot(
        voltages,
        reactive_powers,
        color="#1f4e79",
        linewidth=2.0,
        label="Q(V) droop curve",
    )

    # Deadband shading
    ax.axvspan(
        v_db_lower,
        v_db_upper,
        alpha=0.15,
        color="#5b9bd5",
        label="Deadband region",
    )

    # Qnormal reference line
    ax.axhline(
        y=qnormal_mvar,
        color="#7f7f7f",
        linestyle="--",
        linewidth=1.0,
        label=f"Qnormal = {qnormal_mvar:.1f} MVAr",
    )

    # Vref reference line
    ax.axvline(
        x=vref_pu,
        color="#b0b0b0",
        linestyle="--",
        linewidth=1.0,
        label=f"Vref = {vref_pu:.3f} p.u.",
    )

    # Operating point
    ax.plot(
        operating_voltage_pu,
        reactive_power_mvar,
        marker="o",
        markersize=10,
        color="#2ca02c",
        zorder=5,
        label=f"Operating point ({operating_voltage_pu:.2f} p.u., {reactive_power_mvar:.2f} MVAr)",
    )

    # Delta-Q annotation arrow from Qnormal to operating point
    ax.annotate(
        f"\u0394Q = {delta_q_mvar:+.2f} MVAr",
        xy=(operating_voltage_pu, reactive_power_mvar),
        xytext=(operating_voltage_pu + 0.02, qnormal_mvar + 5),
        fontsize=10,
        fontweight="bold",
        color="#d62728",
        arrowprops=dict(arrowstyle="->", color="#d62728", linewidth=1.5),
        ha="left",
        va="bottom",
    )

    # Project parameters summary box
    param_text = (
        f"Rated Q: {rated_reactive_power_mvar:.1f} MVAr\n"
        f"Base V: {base_voltage_pu:.3f} p.u.\n"
        f"Deadband: \u00b1{deadband_pu:.3f} p.u.\n"
        f"Droop: {droop_pct:.0f}%\n"
        f"Slope: {slope_mvar_per_pu:.1f} MVAr/p.u."
    )
    props = dict(
        boxstyle="round,pad=0.5",
        facecolor="#f2f2f2",
        edgecolor="#999999",
        alpha=0.9,
    )
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
    ax.set_xlabel("Voltage [p.u.]", fontsize=12)
    ax.set_ylabel("Reactive Power [MVAr]", fontsize=12)
    ax.set_title(
        "Q(V) Droop Control Characteristic", fontsize=14, fontweight="bold"
    )
    ax.set_xlim(vref_pu - 0.10, vref_pu + 0.10)
    ax.set_ylim(qmin_mvar - 10, qmax_mvar + 10)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(0.02))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(10))
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

    print(f"Q(V) droop curve chart saved to {output_path}")
    print(f"IMAGE:{output_path}")


if __name__ == "__main__":
    main()
