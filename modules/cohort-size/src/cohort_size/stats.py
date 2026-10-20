"""Small-sample statistics for a size-bucket by success table, in the standard library only.

Purpose    Wilson intervals, Pearson chi-square with its p value, a Monte Carlo exact test with a
           permutation null for V, bias-corrected Cramer's V, Cochran-Armitage trend, Holm.
Boundary   Works on an r x 2 table given as (successes, totals) per row. No other table shapes.
Invariant  Every random step takes an explicit random.Random. Same seed, same numbers.
           If a caller passes the global random module instead, reports stop being reproducible.
Failure    A table with no successes, no failures or fewer than two non-empty rows has no test.
           Those functions return None and the caller must say why, never print zero.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes out of n. (0, 0) when n is 0."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def _gamma_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x): series below a+1, continued fraction above."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        ap, total, delta = a, 1.0 / a, 1.0 / a
        for _ in range(10000):
            ap += 1
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(-x + a * math.log(x) - gln))
    tiny = 1e-300
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        step = d * c
        h *= step
        if abs(step - 1) < 1e-15:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - gln) * h)


def chi2_sf(x: float, df: int) -> float:
    """Survival function of the chi-square distribution."""
    if df <= 0:
        raise ValueError("df must be positive")
    return _gamma_q(df / 2, x / 2)


Table = Sequence[tuple[int, int]]  # (successes, total) per row


def _rows(table: Table) -> list[tuple[int, int]]:
    return [(k, n) for k, n in table if n > 0]


def testable(table: Table) -> str | None:
    """None when the table can be tested, else a short reason in Korean for the screen."""
    rows = _rows(table)
    if len(rows) < 2:
        return "인원 구간이 둘 미만"
    big_k = sum(k for k, _ in rows)
    big_n = sum(n for _, n in rows)
    if big_k == 0:
        return "성공한 팀 0"
    if big_k == big_n:
        return "전원 성공"
    return None


def chi_square(table: Table) -> tuple[float, int, list[float]] | None:
    """Pearson chi-square statistic, degrees of freedom, and the expected counts (both columns, row order)."""
    if testable(table):
        return None
    rows = _rows(table)
    big_k = sum(k for k, _ in rows)
    big_n = sum(n for _, n in rows)
    stat = 0.0
    expected: list[float] = []
    for k, n in rows:
        e1 = n * big_k / big_n
        e0 = n - e1
        expected += [e1, e0]
        stat += (k - e1) ** 2 / e1 + ((n - k) - e0) ** 2 / e0
    return stat, len(rows) - 1, expected


def cramers_v(table: Table) -> float | None:
    """For an r x 2 table, V = sqrt(chi2 / N)."""
    cs = chi_square(table)
    if cs is None:
        return None
    big_n = sum(n for _, n in _rows(table))
    return math.sqrt(cs[0] / big_n)


def _log_weight(rows: list[tuple[int, int]], lg: list[float]) -> float:
    # Larger value = less probable table under fixed margins (sum of log n_ij!).
    return sum(lg[k] + lg[n - k] for k, n in rows)


def cramers_v_bc(table: Table) -> float | None:
    """Bias-corrected Cramer's V (Bergsma 2013) for an r x 2 table.

    Plain V is positive even with no association, and more so when N is small and r is large.
    The correction subtracts the expected chi2 / N under independence and shrinks r and c.
    """
    cs = chi_square(table)
    if cs is None:
        return None
    rows = _rows(table)
    big_n = sum(n for _, n in rows)
    r, c = len(rows), 2
    phi2 = max(0.0, cs[0] / big_n - (r - 1) * (c - 1) / (big_n - 1))
    r_t = r - (r - 1) ** 2 / (big_n - 1)
    c_t = c - (c - 1) ** 2 / (big_n - 1)
    den = min(r_t - 1, c_t - 1)
    return math.sqrt(phi2 / den) if den > 0 else None


def exact_mc(table: Table, rng: random.Random, b: int, level: float = 0.95) -> tuple[float, float, float] | None:
    """Fisher-Freeman-Halton exact test by Monte Carlo permutation, plus a null reference for V.

    Margins are fixed: the successes are dealt at random among all groups b times. A table is at
    least as extreme as the observed one when its hypergeometric probability is not larger.
    Returns (p, Monte Carlo standard error, the `level` quantile of bias-corrected V under the
    permutation null). p uses the (1 + hits) / (b + 1) form so it is never 0.
    """
    if testable(table):
        return None
    rows = _rows(table)
    big_k = sum(k for k, _ in rows)
    big_n = sum(n for _, n in rows)
    lg = [math.lgamma(i + 1) for i in range(big_n + 1)]
    obs = _log_weight(rows, lg)
    labels = [i for i, (_, n) in enumerate(rows) for _ in range(n)]
    sizes = [n for _, n in rows]
    hits = 0
    eps = 1e-9 * max(1.0, abs(obs))
    null_v: list[float] = []
    for _ in range(b):
        c = Counter(rng.sample(labels, big_k))
        w = sum(lg[c[i]] + lg[sizes[i] - c[i]] for i in range(len(rows)))
        if w >= obs - eps:
            hits += 1
        v = cramers_v_bc([(c[i], sizes[i]) for i in range(len(rows))])
        null_v.append(0.0 if v is None else v)
    null_v.sort()
    p = (1 + hits) / (b + 1)
    return p, math.sqrt(p * (1 - p) / b), null_v[min(b - 1, math.ceil(level * b) - 1)]


def cochran_armitage(table: Table, scores: Sequence[float]) -> tuple[float, float] | None:
    """Two-sided Cochran-Armitage trend test. Returns (z, p). Variance uses N, not N - 1.

    With two rows this z squared equals the Pearson chi-square of the 2 x 2 table.
    """
    if testable(table):
        return None
    pairs = [(k, n, t) for (k, n), t in zip(table, scores, strict=True) if n > 0]
    big_k = sum(k for k, _, _ in pairs)
    big_n = sum(n for _, n, _ in pairs)
    p = big_k / big_n
    t_stat = sum(t * (k - n * p) for k, n, t in pairs)
    s1 = sum(n * t for _, n, t in pairs)
    s2 = sum(n * t * t for _, n, t in pairs)
    var = p * (1 - p) * (s2 - s1 * s1 / big_n)
    if var <= 0:
        return None
    z = t_stat / math.sqrt(var)
    return z, math.erfc(abs(z) / math.sqrt(2))


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for [[a, b], [c, d]] by hypergeometric enumeration. Used to check exact_mc."""
    r1, c1, n = a + b, a + c, a + b + c + d

    def logp(x: int) -> float:
        return (
            math.lgamma(r1 + 1) - math.lgamma(x + 1) - math.lgamma(r1 - x + 1)
            + math.lgamma(n - r1 + 1) - math.lgamma(c1 - x + 1) - math.lgamma(n - r1 - c1 + x + 1)
            - math.lgamma(n + 1) + math.lgamma(c1 + 1) + math.lgamma(n - c1 + 1)
        )

    obs = logp(a)
    lo, hi = max(0, r1 + c1 - n), min(r1, c1)
    return min(1.0, sum(math.exp(logp(x)) for x in range(lo, hi + 1) if logp(x) <= obs + 1e-9))


def holm(pvals: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p values, same order as the input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    out = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        out[i] = running
    return out
