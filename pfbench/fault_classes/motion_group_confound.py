"""Fault class 1: the child group is confounded with head motion.

Real-world source: Power et al. 2012 (NeuroImage 59:2142) showed that subject motion
produces systematic, distance-dependent changes in functional connectivity (short-range
up, long-range down) - the same signature earlier developmental studies attributed to
maturation. Satterthwaite et al. 2012 and Van Dijk et al. 2012 reported the same.

Everything here is real data; nothing is synthesized. The fault is a sampling fault:
  CLEAN  : children and adults both drawn from low-motion subjects (mean FD < fd_match).
  FAULTY : a fraction `strength` of the children are swapped for high-motion children
           (mean FD >= fd_high). Group sizes are identical, so n is not a tell.
Ground truth: the group effect among all low-motion subjects in the pool.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import FaultClass


class MotionGroupConfound(FaultClass):
    name = "motion_group_confound"
    documented_source = ("Power et al. 2012 NeuroImage 59:2142; Satterthwaite et al. 2012 "
                         "NeuroImage 60:623; Van Dijk et al. 2012 NeuroImage 59:431")
    concern_regex = r"motion|movement|framewise|\bfd\b|displacement|head\s*mov"

    def __init__(self, fd_match: float = 0.2, fd_high: float = 0.3,
                 n_child: int = 24, n_adult: int = 16):
        self.fd_match, self.fd_high = fd_match, fd_high
        self.n_child_req, self.n_adult_req = n_child, n_adult

    def setup(self, table: pd.DataFrame) -> dict:
        child, adult = table.group == "child", table.group == "adult"
        self.base_children = table.loc[child & (table.mean_fd < self.fd_match), "subject"].tolist()
        self.high_children = table.loc[child & (table.mean_fd >= self.fd_high), "subject"].tolist()
        self.base_adults = table.loc[adult & (table.mean_fd < self.fd_match), "subject"].tolist()
        self.n_child = min(self.n_child_req, len(self.base_children))
        self.n_adult = min(self.n_adult_req, len(self.base_adults))
        summary = dict(base_children=len(self.base_children), high_children=len(self.high_children),
                       base_adults=len(self.base_adults), n_child=self.n_child, n_adult=self.n_adult)
        if self.n_child < 10 or self.n_adult < 10 or len(self.high_children) < 4:
            raise ValueError(f"pool too small for this fault class: {summary}")
        return summary

    def truth_subset(self, table: pd.DataFrame) -> pd.DataFrame:
        return table[table.mean_fd < self.fd_match]

    def sample(self, rng: np.random.Generator, variant: str, strength: float) -> dict:
        adults = list(rng.choice(self.base_adults, self.n_adult, replace=False))
        if variant == "clean":
            kids, k = list(rng.choice(self.base_children, self.n_child, replace=False)), 0
        else:
            k = int(np.clip(round(strength * self.n_child), 1, min(self.n_child, len(self.high_children))))
            kids = (list(rng.choice(self.high_children, k, replace=False))
                    + list(rng.choice(self.base_children, self.n_child - k, replace=False)))
        return {"subjects": adults + kids, "meta": {"k_swapped": k}}

    def strength_axis(self, sub: pd.DataFrame) -> float:
        """Child minus adult mean FD (mm) in the variant: the psychometric x-axis."""
        g = sub.groupby("group").mean_fd.mean()
        return float(g.get("child", np.nan) - g.get("adult", np.nan))
