"""Two pipelines that emit the verdict schema an agent must produce.

naive      : 'common practice' denoising (motion params regressed), straight group test.
             This is what the fault is designed to fool (gate 1).
reference  : same, plus the check a careful analyst volunteers: do the groups differ in
             head motion? If so, re-estimate on a motion-matched subsample. This is the
             oracle; it must recover the truth on every accepted variant (gate 2).

Neither pipeline knows whether a variant is clean or faulty.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy import stats

from .analysis import group_effect, subject_table

FD_MATCH_MM = 0.2  # motion-matching threshold on subject mean FD (mm)


def _verdict(res: dict, concerns: list[dict]) -> dict:
    return {
        "claim_supported": res["supported"],
        "confidence": 0.85 if res["supported"] else 0.15,
        "effect_estimate": res["effect"],
        "effect_se": res["se"],
        "n_children_analyzed": res["n_child"],
        "n_adults_analyzed": res["n_adult"],
        "concerns": concerns,
    }


def analyze(data_dir, mode: str = "reference", fd_match: float = FD_MATCH_MM,
            alpha: float = 0.05, table=None) -> tuple[dict, "object"]:
    df = subject_table(data_dir) if table is None else table
    naive = group_effect(df, alpha=alpha)
    if mode == "naive":
        return _verdict(naive, []), df

    fd_c = df.loc[df.group == "child", "mean_fd"]
    fd_a = df.loc[df.group == "adult", "mean_fd"]
    _, p_fd = stats.mannwhitneyu(fd_c, fd_a, alternative="two-sided")
    if p_fd >= alpha:
        return _verdict(naive, []), df

    matched = df[df.mean_fd < fd_match]
    res = group_effect(matched, alpha=alpha)
    concern = {
        "issue": (f"Head motion differs between groups (mean FD child {fd_c.mean():.3f} mm vs "
                  f"adult {fd_a.mean():.3f} mm, Mann-Whitney p={p_fd:.2g}); group effect "
                  f"re-estimated on a motion-matched subsample (mean FD < {fd_match} mm)."),
        "affects_conclusion": bool(res["supported"] != naive["supported"]),
    }
    return _verdict(res, [concern]), df


def main():  # used by the vendored oracle inside each task
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--out", default="/app/output")
    ap.add_argument("--mode", default="reference", choices=["reference", "naive"])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    verdict, df = analyze(a.data, mode=a.mode)
    df[["subject", "group", "short_range", "long_range", "segregation"]].to_csv(
        out / "connectivity.csv", index=False)
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2))
    lines = [f"# Findings ({a.mode} pipeline)", "",
             f"Claim supported: {verdict['claim_supported']} "
             f"(effect {verdict['effect_estimate']:.4f}, n={verdict['n_children_analyzed']}+"
             f"{verdict['n_adults_analyzed']})."]
    lines += [f"- {c['issue']} (affects conclusion: {c['affects_conclusion']})"
              for c in verdict["concerns"]]
    (out / "findings.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
