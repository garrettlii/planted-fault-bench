"""The interface a fault class implements.

A fault class turns a real data pool into task variants. It decides:
  * which subset of the pool defines the ground truth (truth),
  * how a CLEAN variant is drawn (the negative control),
  * how a FAULTY variant at a given strength is drawn,
  * how variant data are written to disk (materialize; default = copy + rename subjects).

It does NOT decide whether a variant is accepted. That is gates.py's job, and a fault
class (or the agent that wrote it) must never edit gates.py or template/tests/.
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pandas as pd


class FaultClass(ABC):
    name: str = "base"
    # The documented real-world error this class replays. Required: realism comes from here.
    documented_source: str = ""
    # Regex (Python re, case-insensitive) that identifies an agent concern naming this fault.
    # Must be mirrored in template/tests/score.py (selftest checks they match).
    concern_regex: str = ""

    @abstractmethod
    def setup(self, table: pd.DataFrame) -> dict:
        """Precompute candidate pools from the per-subject table. Return a summary dict."""

    @abstractmethod
    def truth_subset(self, table: pd.DataFrame) -> pd.DataFrame:
        """Rows of the pool on which the reference answer defines ground truth."""

    @abstractmethod
    def sample(self, rng: np.random.Generator, variant: str, strength: float) -> dict:
        """Return {"subjects": [...pool subject ids...], "meta": {...}} for one variant."""

    def strength_axis(self, sub: pd.DataFrame) -> float:
        """Continuous fault-strength measure for psychometric fitting (default: 0)."""
        return 0.0

    def materialize(self, pool_dir: Path, out_data: Path, subjects: list[str],
                    table: pd.DataFrame, rng: np.random.Generator) -> dict[str, str]:
        """Write variant data with randomized subject tokens. Returns {pool_id: token}."""
        order = rng.permutation(len(subjects))
        tokens = {subjects[i]: f"s{j + 1:03d}" for j, i in enumerate(order)}
        (out_data / "timeseries").mkdir(parents=True, exist_ok=True)
        (out_data / "confounds").mkdir(parents=True, exist_ok=True)
        parts = pd.read_csv(pool_dir / "participants.tsv", sep="\t").set_index("subject")
        rows = []
        for pool_id, tok in sorted(tokens.items(), key=lambda kv: kv[1]):
            shutil.copy(pool_dir / "timeseries" / f"{pool_id}.npy",
                        out_data / "timeseries" / f"{tok}.npy")
            shutil.copy(pool_dir / "confounds" / f"{pool_id}.tsv",
                        out_data / "confounds" / f"{tok}.tsv")
            p = parts.loc[pool_id]
            rows.append({"subject": tok, "age": round(float(p.age), 2), "group": p.group})
        pd.DataFrame(rows).to_csv(out_data / "participants.tsv", sep="\t", index=False)
        shutil.copy(pool_dir / "roi_coords.csv", out_data / "roi_coords.csv")
        return tokens
