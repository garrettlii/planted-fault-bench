"""Two pipelines that emit the verdict schema an agent must produce.

naive      : 'common practice' denoising (motion params regressed), straight group test.
             This is what the fault is designed to mislead (gate G1).
reference  : same, plus the standard step a careful developmental-fMRI analyst applies:
             exclude subjects whose mean framewise displacement is at or above the
             threshold, then re-estimate. On clean variants nobody is excluded, so the
             reference equals the naive pipeline. This is the oracle; it must recover the
             truth on every accepted variant (gate G2).

Neither pipeline knows whether a variant is clean or faulty.

v0.2: the reference always applies the exclusion (v0.1 applied it only when a
Mann-Whitney test said group motion differed). Its concern is marked as affecting the
conclusion when the exclusion moves the estimate by more than 2 SE.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import group_effect, subject_table

FD_MATCH_MM = 0.2  # exclusion threshold on subject mean FD (mm)


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

    excluded = df[df.mean_fd >= fd_match]
    if excluded.empty:
        return _verdict(naive, []), df
    res = group_effect(df[df.mean_fd < fd_match], alpha=alpha)
    fd = df.groupby("group").mean_fd.mean()
    n_ex = excluded.group.value_counts().to_dict()
    concern = {
        "issue": (f"Head motion: excluded {len(excluded)} subjects with mean FD >= {fd_match} mm "
                  f"({n_ex.get('child', 0)} children, {n_ex.get('adult', 0)} adults); mean FD before "
                  f"exclusion child {fd.get('child', float('nan')):.3f} mm vs adult "
                  f"{fd.get('adult', float('nan')):.3f} mm. Group effect re-estimated on the rest."),
        "affects_conclusion": bool(abs(res["effect"] - naive["effect"]) > 2 * res["se"]),
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
