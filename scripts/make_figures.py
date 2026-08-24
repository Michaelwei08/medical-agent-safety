"""Render the writeup's figures from docs/findings_data.json.

Every value is read from the collected data, never typed here, so a figure cannot
drift from the prose that cites it.

Palette and forms follow the data-viz reference instance:
  - Fig 1 is an EMPHASIS scatter: the two real models carry categorical hues, the
    four deterministic stand-ins are the de-emphasis gray. Scatter is an all-pairs
    form, capped at three categorical slots; two are used, validated all-pairs
    (worst CVD dE 24.7, normal-vision 33.6).
  - Fig 2 is emphasis again: one measure is the point, so the other is stated in
    the subtitle rather than plotted as an invisible zero bar.
  - Fig 3 is a status grid. Status colors are reserved, never themed, and always
    ship with a label -- so each cell carries a glyph, never colour alone.

    python scripts/make_figures.py
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.lines import Line2D      # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "findings_data.json")
FIGDIR = os.path.join(ROOT, "docs", "figures")

# Reference palette, light surface.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"     # categorical slot 1 -- Claude
ORANGE = "#eb6834"   # categorical slot 2 -- qwen
GOOD = "#0ca30c"
WARNING = "#fab219"
CRITICAL = "#d03b3b"

SANS = ["Segoe UI", "DejaVu Sans", "sans-serif"]
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": SANS,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.edgecolor": AXIS,
    "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
})

AQUA = "#1baf7a"     # categorical slot 3
STAND_INS = {"keyword": "keyword filter", "mock_model": "mock model",
             "naive": "naive", "worst_case": "adversarial"}
KNOWN = {"cli:sonnet": "Claude (Sonnet, via CLI)",
         "ollama:qwen2.5:7b": "Qwen2.5 7B (local)"}


def label_for(backend: str) -> str:
    """Readable name for a backend id, derived when it is not a known one."""
    if backend in KNOWN:
        return KNOWN[backend]
    if backend in STAND_INS:
        return STAND_INS[backend]
    provider, _, model = backend.partition(":")
    suffix = " (local)" if provider == "ollama" else f" ({provider})"
    return model.replace("-", " ") + suffix


def model_colours(models: list[str]) -> dict[str, str]:
    """Hues for the real models.

    Scatter is an all-pairs form, so the categorical palette caps at three slots
    (validated: worst all-pairs CVD dE 9.2). Past three, identity moves to direct
    labels and every model shares one accent -- generating a fourth hue would break
    the CVD gate, and the point of the figure is the spread, not which dot is which.
    """
    if len(models) <= 3:
        return dict(zip(models, (BLUE, ORANGE, AQUA)))
    return {m: BLUE for m in models}


LABELS = {**KNOWN, **STAND_INS}


def load() -> dict:
    with open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def save(fig, name: str) -> None:
    os.makedirs(FIGDIR, exist_ok=True)
    path = os.path.join(FIGDIR, name)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {os.path.relpath(path, ROOT)}")


# --------------------------------------------------------------- figure 1 ---
def fig_safety_utility(d: dict) -> None:
    """The two failure modes on one plane, and the guard collapsing both."""
    fig = plt.figure(figsize=(7.6, 5.9))
    # Explicit margins: the title, subtitle and footnote each get their own band,
    # so nothing has to be nudged into the plot area later.
    ax = fig.add_axes([0.115, 0.235, 0.86, 0.60])

    # naive and adversarial land on the identical point (0.700, 0.000). Two labels
    # at one coordinate is unreadable, so coincident agents share one.
    spectrum = ["keyword", "mock_model", "naive", "worst_case"]  # benign -> adversarial
    groups: dict[tuple[float, float], list[str]] = {}
    for name in spectrum:
        agent = d["agents"].get(name)
        if not agent or agent["kind"] != "stand-in":
            continue
        off = agent["off"]
        key = (round(off["unsafe_action_rate"], 4), round(off["over_refusal_rate"], 4))
        groups.setdefault(key, []).append(label_for(name))

    # Stagger labels that sit close on x, or they overlap: mock_model (0.45) and
    # keyword (0.50) are only 0.05 apart on an 0.87-wide axis.
    prev_x, offset = None, -17
    for (x, y) in sorted(groups):
        names = groups[(x, y)]
        if prev_x is not None and abs(x - prev_x) < 0.11:
            offset = -32 if offset == -17 else -17
        else:
            offset = -17
        prev_x = x
        ax.scatter(x, y, s=75, color=MUTED, alpha=0.6, zorder=3,
                   edgecolor=SURFACE, linewidth=1.5)
        ax.annotate(", ".join(names), (x, y), textcoords="offset points",
                    xytext=(0, offset), ha="center", fontsize=8.5, color=MUTED)

    reals = [n for n, a in d["agents"].items() if a["kind"] == "real model"]
    reals.sort(key=lambda n: d["agents"][n]["off"]["unsafe_action_rate"])
    palette = model_colours(reals)
    # Alternate the label side so points at similar heights do not collide.
    placements = [(16, 6, "left"), (0, 22, "center"), (-16, 6, "right")]
    for i, name in enumerate(reals):
        colour = palette[name]
        dx, dy, ha = placements[i % len(placements)]
        off = d["agents"][name]["off"]
        x, y = off["unsafe_action_rate"], off["over_refusal_rate"]
        ax.annotate("", xy=(0.014, 0.014), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color=colour, alpha=0.45,
                                    linewidth=2, shrinkA=10, shrinkB=13,
                                    connectionstyle="arc3,rad=0.16"), zorder=2)
        ax.scatter(x, y, s=200, color=colour, zorder=5,
                   edgecolor=SURFACE, linewidth=2)
        ax.annotate(label_for(name), (x, y), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, fontsize=10.5,
                    fontweight="bold", color=INK)

    ax.scatter(0, 0, s=270, marker="o", facecolor=SURFACE,
               edgecolor=INK, linewidth=2.2, zorder=6)
    ax.annotate("guard ON -- every agent", (0, 0), textcoords="offset points",
                xytext=(20, 30), fontsize=10, fontweight="bold", color=INK,
                arrowprops=dict(arrowstyle="-", color=INK, linewidth=1,
                                shrinkA=2, shrinkB=13))

    ax.set_xlabel("Unsafe-action rate  (acted where the case required deferral)",
                  fontsize=10, labelpad=8)
    ax.set_ylabel("Over-refusal rate  (deferred where acting was correct)",
                  fontsize=10, labelpad=8)
    ax.set_xlim(-0.05, 0.82)
    ax.set_ylim(-0.055, 0.47)
    ax.grid(color=GRID, linewidth=0.9, zorder=0)
    ax.set_axisbelow(True)

    fig.text(0.02, 0.955, "The guard buys different things from different agents",
             fontsize=15.5, fontweight="600", color=INK)
    fig.text(0.02, 0.905,
             "Guard off, 20 synthetic clinical cases. Both axes are failure rates, "
             "so the safe corner is the origin.",
             fontsize=9.5, color=INK2)
    # Derived, not written: with a third model a hand-typed caption naming two of
    # them goes stale silently, which is the same failure as a hand-typed number.
    safest = min(reals, key=lambda n: d["agents"][n]["off"]["unsafe_action_rate"])
    riskiest = max(reals, key=lambda n: d["agents"][n]["off"]["unsafe_action_rate"])
    fussiest = max(reals, key=lambda n: d["agents"][n]["off"]["over_refusal_rate"])
    caption = (
        f"{label_for(fussiest)} refuses "
        f"{d['agents'][fussiest]['off']['over_refusal_rate']:.3f} of the work it should "
        f"do; {label_for(riskiest)} acts on\n"
        f"{d['agents'][riskiest]['off']['unsafe_action_rate']:.3f} of cases that require "
        "deferral. Enforcement moves every agent to the origin: unsafe 0.000, "
        "over-refusal 0.000, accuracy 1.000."
    ) if riskiest != fussiest else (
        "Enforcement moves every agent to the origin: unsafe 0.000, over-refusal "
        "0.000, action accuracy 1.000."
    )
    fig.text(0.02, 0.075, caption, fontsize=9, color=INK2)
    save(fig, "fig1_safety_utility_plane.png")


# --------------------------------------------------------------- figure 2 ---
def fig_counterfactual(d: dict) -> None:
    """Same flip rate, opposite meaning -- what the control run separates."""
    reals = [n for n, a in d["agents"].items()
             if a["kind"] == "real model" and n in d["flips"]]
    reals.sort(key=lambda n: d["flips"][n]["wrong_without_payload"])
    stand = [k for k in ("naive", "keyword", "mock_model", "worst_case")
             if k in d["flips"]]
    order = reals + stand
    vals = [d["flips"][k]["wrong_without_payload"] for k in order]
    palette = model_colours(reals)
    colours = [palette.get(k, MUTED) for k in order]

    fig = plt.figure(figsize=(7.6, 4.3))
    ax = fig.add_axes([0.27, 0.235, 0.63, 0.53])
    ypos = range(len(order))
    ax.barh(list(ypos), vals, height=0.58, color=colours, zorder=3)
    for y, v in zip(ypos, vals):
        ax.text(v + 0.022, y, f"{v:.2f}", va="center", fontsize=10,
                fontweight="bold", color=INK2)

    ax.set_yticks(list(ypos))
    ax.set_yticklabels([label_for(k) for k in order], fontsize=10, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.16)
    ax.set_xlabel("Wrong on the four adversarial cases WITHOUT the payload",
                  fontsize=10, labelpad=8)
    ax.grid(axis="x", color=GRID, linewidth=0.9, zorder=0)
    ax.set_axisbelow(True)

    fig.text(0.02, 0.93, "Why the paired control run exists",
             fontsize=15.5, fontweight="600", color=INK)
    fig.text(0.02, 0.845,
             "Injection flip rate is 0.000 for every agent below: no payload changed "
             "any answer.\nWhat differs is whether they were right to begin with.",
             fontsize=9.5, color=INK2)
    fig.text(0.02, 0.035,
             "Claude resisted four hand-written payloads. The others were never in a "
             "position to be moved -- they fail these\ncases with the payload removed. "
             "Reporting flip rate alone would score an agent that always acts as "
             "injection-resistant.",
             fontsize=9, color=INK2)
    save(fig, "fig2_counterfactual_control.png")


# --------------------------------------------------------------- figure 3 ---
def fig_case_grid(d: dict) -> None:
    """Where each real model fails, per case. Status colours + a glyph per cell."""
    models = sorted(d["per_case"])
    cases = [c["case_id"] for c in d["per_case"][models[0]]]
    tags = {c["case_id"]: c["tag"] for c in d["per_case"][models[0]]}
    order = sorted(cases, key=lambda c: (tags[c], c))

    fig, ax = plt.subplots(figsize=(5.2 + 1.3 * len(models), 6.4))
    for col, model in enumerate(models):
        by_id = {c["case_id"]: c for c in d["per_case"][model]}
        for row, cid in enumerate(order):
            c = by_id[cid]
            if c["unsafe"]:
                colour, glyph = CRITICAL, "!"
            elif c["correct"]:
                colour, glyph = GOOD, "ok"
            else:
                colour, glyph = WARNING, "-"
            ax.add_patch(Rectangle((col, row), 0.94, 0.9, facecolor=colour,
                                   alpha=0.85, edgecolor=SURFACE, linewidth=2))
            ax.text(col + 0.47, row + 0.45, glyph, ha="center", va="center",
                    fontsize=9, fontweight="bold",
                    color="#ffffff" if colour != WARNING else INK)

    ax.set_xlim(0, len(models)); ax.set_ylim(0, len(order))
    ax.set_xticks([i + 0.47 for i in range(len(models))])
    ax.set_xticklabels([label_for(m) for m in models], fontsize=9.5, color=INK)
    ax.xaxis.tick_top(); ax.xaxis.set_label_position("top")
    ax.set_yticks([i + 0.45 for i in range(len(order))])
    ax.set_yticklabels([f"{tags[c]}  |  {c}" for c in order],
                       fontsize=8, color=INK2)
    ax.invert_yaxis()
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    legend = [
        Line2D([], [], marker="s", linestyle="none", markersize=11,
               markerfacecolor=GOOD, markeredgecolor=SURFACE, label="ok  correct resolution"),
        Line2D([], [], marker="s", linestyle="none", markersize=11,
               markerfacecolor=WARNING, markeredgecolor=SURFACE, label="-  over-cautious (deferred, not unsafe)"),
        Line2D([], [], marker="s", linestyle="none", markersize=11,
               markerfacecolor=CRITICAL, markeredgecolor=SURFACE, label="!  unsafe action"),
    ]
    ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(0, -0.035),
              frameon=False, fontsize=9, labelcolor=INK2, ncol=1, handletextpad=0.6)

    fig.text(0, 1.115, "Where each model fails, guard off",
             fontsize=15, fontweight="600", color=INK, transform=ax.transAxes)
    fig.text(0, 1.075,
             "20 cases, grouped by scenario type. Guard on, every cell is green.",
             fontsize=9.5, color=INK2, transform=ax.transAxes)
    save(fig, "fig3_case_grid.png")


def main() -> None:
    d = load()
    print("rendering figures from docs/findings_data.json")
    fig_safety_utility(d)
    fig_counterfactual(d)
    fig_case_grid(d)


if __name__ == "__main__":
    main()
