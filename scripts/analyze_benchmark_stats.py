#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = ROOT / "datasets"
OUT_DIR = ROOT / "analysis_outputs" / "benchmark_stats_report"
CHART_DIR = OUT_DIR / "charts"

# Canonical full-benchmark composition used for the data-composition report.
# The Inferential Privacy / HearSay block is included because it is part of the
# full benchmark accounting, while the project README notes it is sourced from
# the separate HearSay benchmark.
FULL_BENCHMARK_SUBGROUPS: list[dict[str, Any]] = [
    {
        "pillar": "Safety",
        "tier": "Tier 1",
        "subgroup": "No_jailbreak / Explicit Harm & Toxicity",
        "rows": 8708,
        "description": "Content-risk prompts without a jailbreak wrapper.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 1",
        "subgroup": "Singleturn_jailbreak",
        "rows": 2516,
        "description": "Single-turn attempts to bypass safety behavior.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 1",
        "subgroup": "Multiturn_jailbreak",
        "rows": 240,
        "description": "Multi-turn jailbreak conversations.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 1",
        "subgroup": "Agentic_Action_Risks",
        "rows": 873,
        "description": "Tool-use or agentic action risks.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Child_voice",
        "rows": 400,
        "description": "Foreground speaker sounds like a child.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Emotion",
        "rows": 160,
        "description": "Paralinguistic emotion changes the safe response.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Impaired_capacity",
        "rows": 293,
        "description": "Speaker sounds impaired, intoxicated, or low-capacity.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Child_presence",
        "rows": 400,
        "description": "A child is present in the background audio.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Symbolic_background",
        "rows": 320,
        "description": "Background sound carries symbolic or unsafe meaning.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Unsafe_ambient",
        "rows": 400,
        "description": "Ambient audio implies unsafe surrounding conditions.",
    },
    {
        "pillar": "Safety",
        "tier": "Tier 2",
        "subgroup": "Overlap_instruction_injection",
        "rows": 552,
        "description": "Overlapping speech attempts instruction injection.",
    },
    {
        "pillar": "Fairness",
        "tier": "Tier 1",
        "subgroup": "Fairness-tier1/test",
        "rows": 2312,
        "description": "Content-centric fairness and bias evaluation.",
    },
    {
        "pillar": "Fairness",
        "tier": "Tier 2",
        "subgroup": "Fairness-tier2/test",
        "rows": 2050,
        "description": "Audio-conditioned fairness evaluation.",
    },
    {
        "pillar": "Fairness",
        "tier": "Tier 2",
        "subgroup": "Bias_analysis",
        "rows": 2218,
        "description": "Bias analysis under voice or speaker-conditioned settings.",
    },
    {
        "pillar": "Privacy",
        "tier": "Tier 1",
        "subgroup": "Hard_privacy",
        "rows": 800,
        "description": "Direct privacy-sensitive requests.",
    },
    {
        "pillar": "Privacy",
        "tier": "Tier 1",
        "subgroup": "Soft_privacy",
        "rows": 800,
        "description": "Softer privacy leakage or boundary cases.",
    },
    {
        "pillar": "Privacy",
        "tier": "Tier 2",
        "subgroup": "Audio_conditioned_privacy",
        "rows": 400,
        "description": "Privacy risk depends on background or audio context.",
    },
    {
        "pillar": "Privacy",
        "tier": "Tier 2",
        "subgroup": "Interactional_privacy",
        "rows": 586,
        "description": "Privacy leakage across interaction turns.",
    },
    {
        "pillar": "Privacy",
        "tier": "Tier 2",
        "subgroup": "Inferential_privacy / HearSay",
        "rows": 2345,
        "description": "Inferential privacy benchmark referenced through HearSay.",
    },
]

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}
COLORS = {
    "Safety": "#A3BEFA",
    "Fairness": "#F390CA",
    "Privacy": "#A3D576",
    "Tier 1": "#A3BEFA",
    "Tier 2": "#F0986E",
    "edge": "#464C55",
}


def pct(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def summarize(rows: Sequence[dict[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    totals: dict[tuple[Any, ...], int] = defaultdict(int)
    for row in rows:
        totals[tuple(row[key] for key in keys)] += int(row["rows"])
    out = []
    total_rows = sum(int(row["rows"]) for row in rows)
    for key_values, count in sorted(totals.items()):
        item = {key: value for key, value in zip(keys, key_values)}
        item["rows"] = count
        item["share_pct"] = pct(count, total_rows)
        out.append(item)
    return out


def local_dataset_availability() -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for meta_path in sorted(DATASETS_DIR.glob("*/*/metadata.jsonl")):
        rel = meta_path.relative_to(DATASETS_DIR)
        task = "/".join(rel.parts[:-1])
        rows = read_jsonl(meta_path)
        language_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            language_counts[str(row.get("language") or row.get("Language") or row.get("lang") or "UNKNOWN")] += 1
        rows_out.append(
            {
                "task": task,
                "rows": len(rows),
                "en_rows": language_counts.get("EN", 0),
                "zh_rows": language_counts.get("ZH", 0),
                "note": "present in current local datasets directory",
            }
        )
    return rows_out


def add_chart_header(fig: Any, ax: Any, title: str, subtitle: str) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=0.82)
    left = ax.get_position().x0
    fig.text(left, 0.96, title, ha="left", va="top", fontsize=15, fontweight="bold", color=TOKENS["ink"])
    fig.text(left, 0.90, subtitle, ha="left", va="top", fontsize=10.5, color=TOKENS["muted"])


def style_axes(ax: Any, *, x_grid: bool = True, y_grid: bool = False) -> None:
    ax.set_facecolor(TOKENS["panel"])
    ax.tick_params(colors=TOKENS["muted"], labelsize=9)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(TOKENS["axis"])
    ax.spines["bottom"].set_color(TOKENS["axis"])
    if x_grid:
        ax.grid(True, axis="x", color=TOKENS["grid"], linewidth=0.8)
    else:
        ax.grid(False, axis="x")
    if y_grid:
        ax.grid(True, axis="y", color=TOKENS["grid"], linewidth=0.8)
    else:
        ax.grid(False, axis="y")


def save_pillar_tier_chart(rows: Sequence[dict[str, Any]]) -> Path:
    df = pd.DataFrame(summarize(rows, ["pillar", "tier"]))
    pivot = df.pivot(index="pillar", columns="tier", values="rows").fillna(0)
    pivot = pivot.loc[["Safety", "Fairness", "Privacy"], ["Tier 1", "Tier 2"]]

    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor=TOKENS["surface"])
    bottom = None
    for tier in ["Tier 1", "Tier 2"]:
        values = pivot[tier].to_numpy()
        ax.bar(
            pivot.index,
            values,
            bottom=bottom,
            label=tier,
            color=COLORS[tier],
            edgecolor=COLORS["edge"],
            linewidth=0.6,
        )
        for idx, value in enumerate(values):
            y = value / 2 if bottom is None else bottom[idx] + value / 2
            ax.text(idx, y, f"{int(value):,}", ha="center", va="center", fontsize=9, color=TOKENS["ink"])
        bottom = values if bottom is None else bottom + values

    style_axes(ax, x_grid=False, y_grid=True)
    ax.set_xlabel("")
    ax.set_ylabel("Rows", color=TOKENS["muted"])
    ax.legend(title="", frameon=False, ncol=2, loc="upper right")
    add_chart_header(
        fig,
        ax,
        "Full benchmark distribution by pillar and tier",
        "Rows grouped by Safety, Fairness, and Privacy; Tier 1 is content-centric, Tier 2 is audio-conditioned.",
    )

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out = CHART_DIR / "pillar_tier_distribution.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    fig.savefig(CHART_DIR / "pillar_tier_distribution.svg", bbox_inches="tight")
    plt.close(fig)
    return out


def save_subgroup_chart(rows: Sequence[dict[str, Any]]) -> Path:
    df = pd.DataFrame(rows).sort_values("rows", ascending=True)
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    fig, ax = plt.subplots(figsize=(11, 9.5), facecolor=TOKENS["surface"])
    palette = [COLORS[pillar] for pillar in df["pillar"]]
    ax.barh(df["subgroup"], df["rows"], color=palette, edgecolor=COLORS["edge"], linewidth=0.5)
    style_axes(ax)
    ax.set_xlabel("Rows", color=TOKENS["muted"])
    ax.set_ylabel("")
    for y, value in enumerate(df["rows"]):
        ax.text(value + 90, y, f"{int(value):,}", va="center", ha="left", fontsize=8.5, color=TOKENS["ink"])
    add_chart_header(
        fig,
        ax,
        "Full benchmark rows by top-level subgroup",
        "Top-level tasks/subgroups; some groups contain finer internal categories or dimensions.",
    )

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out = CHART_DIR / "subgroup_distribution.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    fig.savefig(CHART_DIR / "subgroup_distribution.svg", bbox_inches="tight")
    plt.close(fig)
    return out


def html_table(rows: Sequence[Dict[str, Any]], columns: Sequence[str], labels: Dict[str, str] | None = None) -> str:
    labels = labels or {}
    out = ["<table>", "<thead><tr>"]
    for col in columns:
        out.append(f"<th>{html.escape(labels.get(col, col))}</th>")
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, float):
                value = f"{value:.2f}"
            out.append(f"<td>{html.escape(str(value))}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def build_report(
    subgroup_rows: Sequence[dict[str, Any]],
    pillar_rows: Sequence[dict[str, Any]],
    tier_rows: Sequence[dict[str, Any]],
    pillar_tier_rows: Sequence[dict[str, Any]],
    local_rows: Sequence[dict[str, Any]],
    pillar_tier_chart: Path,
    subgroup_chart: Path,
) -> Path:
    total = sum(int(row["rows"]) for row in subgroup_rows)
    hf_release_total = total - 2345
    subgroup_count = len(subgroup_rows)
    tier1_total = next(row["rows"] for row in tier_rows if row["tier"] == "Tier 1")
    tier2_total = next(row["rows"] for row in tier_rows if row["tier"] == "Tier 2")

    pillar_table = html_table(
        pillar_rows,
        ["pillar", "rows", "share_pct"],
        {"pillar": "Pillar", "rows": "Rows", "share_pct": "Share %"},
    )
    tier_table = html_table(
        tier_rows,
        ["tier", "rows", "share_pct"],
        {"tier": "Tier", "rows": "Rows", "share_pct": "Share %"},
    )
    pillar_tier_table = html_table(
        pillar_tier_rows,
        ["pillar", "tier", "rows", "share_pct"],
        {"pillar": "Pillar", "tier": "Tier", "rows": "Rows", "share_pct": "Share %"},
    )
    subgroup_table = html_table(
        sorted(subgroup_rows, key=lambda row: (row["pillar"], row["tier"], -int(row["rows"]))),
        ["pillar", "tier", "subgroup", "rows", "share_pct", "description"],
        {
            "pillar": "Pillar",
            "tier": "Tier",
            "subgroup": "Subgroup / task",
            "rows": "Rows",
            "share_pct": "Share %",
            "description": "Plain-language meaning",
        },
    )
    local_table = html_table(
        local_rows,
        ["task", "rows", "en_rows", "zh_rows", "note"],
        {"task": "Local task", "rows": "Rows", "en_rows": "EN", "zh_rows": "ZH", "note": "Note"},
    )

    css = """
    body { margin: 0; background: #FCFCFD; color: #1F2430; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 1080px; margin: 0 auto; padding: 44px 24px 72px; }
    header, section { margin-bottom: 34px; }
    h1 { font-size: 34px; line-height: 1.12; margin: 0; letter-spacing: 0; }
    h2 { font-size: 22px; line-height: 1.2; margin: 0 0 12px; letter-spacing: 0; }
    p, li { line-height: 1.6; font-size: 15.5px; }
    .executive-summary-box { border: 1px solid #D7DBE7; background: #FFFFFF; border-radius: 8px; padding: 18px 22px; }
    .executive-summary-box ul { margin: 0; padding-left: 20px; }
    .executive-summary-box li + li { margin-top: 10px; }
    .callout { border-left: 4px solid #F0986E; background: #F4F5F7; padding: 12px 16px; }
    figure { margin: 18px 0 20px; }
    figure img { width: 100%; max-width: 100%; height: auto; display: block; border: 1px solid #E6E8F0; border-radius: 8px; background: #FFFFFF; }
    figcaption { color: #6F768A; font-size: 13px; margin-top: 8px; }
    table { border-collapse: collapse; width: 100%; margin: 14px 0 20px; font-size: 13.5px; }
    th, td { border-bottom: 1px solid #E6E8F0; padding: 9px 8px; text-align: left; vertical-align: top; }
    th { color: #464C55; background: #F4F5F7; font-weight: 650; }
    .note { color: #6F768A; font-size: 14px; }
    .twocol { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
    @media (max-width: 760px) { .twocol { grid-template-columns: 1fr; } }
    """

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VoxSafeBench Data Composition Report</title>
  <style>{css}</style>
</head>
<body>
<main data-report-audience="product stakeholders">
  <header data-contract-section="title">
    <h1>VoxSafeBench Data Composition Report</h1>
    <p class="note">Focus: benchmark data composition only. Result-run summaries are intentionally excluded.</p>
  </header>

  <section class="executive-summary-box" data-contract-section="executive-summary">
    <h2>Executive Summary</h2>
    <ul>
      <li><strong>The full benchmark accounting contains {total:,} instances across {subgroup_count} top-level subgroup/task blocks.</strong> These top-level blocks contain finer internal categories and dimensions, which is why the benchmark is often described as having 20+ subgroups. The main Hugging Face release accounts for about {hf_release_total:,} rows; adding Inferential Privacy / HearSay brings the full benchmark accounting to {total:,}.</li>
      <li><strong>The benchmark is organized by three pillars and two tiers.</strong> Safety is the largest pillar, while Tier 1 has {tier1_total:,} content-centric rows and Tier 2 has {tier2_total:,} audio-conditioned rows.</li>
      <li><strong>Tier 1 asks whether the model handles risky content in the transcript; Tier 2 asks whether the model uses voice and acoustic context.</strong> Tier 2 includes child voice, child presence, impaired speech, emotion, ambient sounds, overlap injection, and audio-conditioned privacy.</li>
    </ul>
  </section>

  <section data-contract-section="key-findings">
    <h2>Data is first split into Safety, Fairness, and Privacy, then into Tier 1 and Tier 2</h2>
    <p><strong>Safety dominates the benchmark volume, but all three pillars have both text/content-centric and audio-conditioned coverage.</strong> Tier 1 is larger overall because it includes high-volume content-risk and jailbreak data. Tier 2 is smaller but more specific to speech-language models because the correct response depends on who is speaking, how they speak, or what can be heard around them.</p>
    <figure>
      <img src="{html.escape(pillar_tier_chart.relative_to(OUT_DIR).as_posix())}" alt="Full benchmark distribution by pillar and tier">
      <figcaption>Full benchmark row counts grouped by pillar and tier.</figcaption>
    </figure>
    <div class="twocol">
      <div>{pillar_table}</div>
      <div>{tier_table}</div>
    </div>
    {pillar_tier_table}
  </section>

  <section data-contract-section="key-findings">
    <h2>Subgroups are uneven by design because they test different risk surfaces</h2>
    <p><strong>The biggest blocks are content-centric Safety and Fairness tasks; the audio-conditioned subgroups are smaller, targeted stress tests.</strong> That is expected: Tier 2 scenarios require controlled audio conditions, such as child voice, impaired speech, background children, or overlapping speech, so they are more granular and intentionally scenario-specific.</p>
    <figure>
      <img src="{html.escape(subgroup_chart.relative_to(OUT_DIR).as_posix())}" alt="Full benchmark rows by top-level subgroup">
      <figcaption>Top-level subgroup/task counts. Some task blocks contain finer internal categories or dimensions.</figcaption>
    </figure>
    {subgroup_table}
  </section>

  <section data-contract-section="key-findings">
    <h2>Current local checkout is only a subset of the full benchmark</h2>
    <p><strong>The local <code>datasets/</code> directory currently contains four Tier 2 subgroups, not the full 20K+ benchmark.</strong> This section is included only to avoid confusing local files with the complete benchmark accounting above. It is not a pilot-test or mitigation-result summary.</p>
    {local_table}
  </section>

  <section data-contract-section="recommended-next-steps">
    <h2>Recommended Next Steps</h2>
    <ol>
      <li>Use the full subgroup distribution table as the source for paper/report dataset-composition language.</li>
      <li>When reporting model results, always state whether results cover the full benchmark, the local Tier 2 subset, or a smaller smoke/pilot subset.</li>
      <li>If you want subgroup-level result analysis later, generate that as a separate results report so it does not mix with dataset composition.</li>
    </ol>
  </section>

  <section data-contract-section="caveats-and-assumptions">
    <h2>Caveats and Assumptions</h2>
    <div class="callout">
      <p>This report treats the table in the script as the canonical full-benchmark composition. Inferential Privacy / HearSay is included in the full benchmark accounting but is separate from the current local <code>datasets/</code> checkout.</p>
    </div>
  </section>
</main>
</body>
</html>
"""
    out = OUT_DIR / "report.html"
    out.write_text(body, encoding="utf-8")
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    total = sum(int(row["rows"]) for row in FULL_BENCHMARK_SUBGROUPS)
    subgroup_rows = [
        {
            **row,
            "share_pct": pct(int(row["rows"]), total),
        }
        for row in FULL_BENCHMARK_SUBGROUPS
    ]
    pillar_rows = summarize(subgroup_rows, ["pillar"])
    tier_rows = summarize(subgroup_rows, ["tier"])
    pillar_tier_rows = summarize(subgroup_rows, ["pillar", "tier"])
    local_rows = local_dataset_availability()

    write_csv(
        OUT_DIR / "full_benchmark_subgroup_distribution.csv",
        subgroup_rows,
        ["pillar", "tier", "subgroup", "rows", "share_pct", "description"],
    )
    write_csv(OUT_DIR / "full_benchmark_pillar_summary.csv", pillar_rows, ["pillar", "rows", "share_pct"])
    write_csv(OUT_DIR / "full_benchmark_tier_summary.csv", tier_rows, ["tier", "rows", "share_pct"])
    write_csv(OUT_DIR / "full_benchmark_pillar_tier_summary.csv", pillar_tier_rows, ["pillar", "tier", "rows", "share_pct"])
    write_csv(OUT_DIR / "current_local_dataset_availability.csv", local_rows, ["task", "rows", "en_rows", "zh_rows", "note"])

    pillar_tier_chart = save_pillar_tier_chart(subgroup_rows)
    subgroup_chart = save_subgroup_chart(subgroup_rows)
    report_path = build_report(
        subgroup_rows,
        pillar_rows,
        tier_rows,
        pillar_tier_rows,
        local_rows,
        pillar_tier_chart,
        subgroup_chart,
    )

    print(f"Wrote {report_path.relative_to(ROOT)}")
    print(f"Wrote full benchmark composition tables under {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
