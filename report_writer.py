"""
Karpathy Autoresearch — Report Writer
Human-readable nightly report for trading 1 /MES contract.
Clear: expected move, adverse move, stop, target, net expectancy, confidence, skip.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List

import config as _cfg
from config import (
    MES_POINT_VALUE, TICK_SIZE, TICK_VALUE,
    ROUND_TRIP_COST_USD, SLIPPAGE_USD, SLIPPAGE_TICKS_RT,
    spy_pct_to_mes_points, spy_pct_to_mes_dollars,
)
from evaluator import RuleScore


def _pts_to_ticks(pts: float) -> int:
    """Convert /MES points to ticks."""
    return int(round(pts / TICK_SIZE))


def _confidence_label(score: RuleScore, preliminary: bool) -> str:
    """Human-readable confidence level."""
    if preliminary:
        return "PRELIMINARY (insufficient days)"
    if score.wf_stability >= 0.80 and score.neighbor_robust and score.distinct_days >= 3:
        return "HIGH"
    elif score.wf_stability >= 0.60 and score.neighbor_robust:
        return "MODERATE"
    elif score.wf_stability >= 0.40:
        return "LOW"
    return "SPECULATIVE"


def write_nightly_report(
    promoted: List[RuleScore],
    n_rows: int,
    n_days: int,
    n_features: int,
    n_candidates: int,
    preliminary: bool,
    output_dir: Path,
    maturity_tier: dict = None,
):
    """Write nightly_report.md and nightly_report.json."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    tier_label = maturity_tier.get('label', 'UNKNOWN') if maturity_tier else 'UNKNOWN'
    tier_mode = maturity_tier.get('mode', 'unknown') if maturity_tier else 'unknown'

    # ── Markdown Report ──────────────────────────────────────────────────
    md = []
    md.append(f"# Karpathy Autoresearch — Nightly Report")
    md.append(f"**Generated:** {now}")
    md.append(f"**Trading instrument:** 1 /MES contract")
    md.append(f"**Maturity tier:** {tier_label}")
    md.append("")

    md.append("## Data Summary")
    md.append(f"- Snapshots: {n_rows:,}")
    md.append(f"- Trading days: {n_days}")
    md.append(f"- Features: {n_features:,}")
    md.append(f"- Candidates evaluated: {n_candidates:,}")
    md.append(f"- Rules promoted: {len(promoted)}")
    md.append("")

    if tier_mode == 'features_only':
        md.append("> **DATA COLLECTION PHASE**")
        md.append(f"> Only {n_days} trading day(s). Need ≥3 days before any patterns can be evaluated.")
        md.append("> The pipeline built features and diagnostics only. No rules were searched.")
        md.append("> Keep collecting data daily. Rule search begins at 3 days.")
        md.append("")
    elif preliminary:
        md.append(f"> **{tier_label.upper()}**")
        md.append(f"> {n_days} trading day(s) available.")
        if tier_mode == 'research':
            md.append("> These are **watchlist candidates only**, not live-tradable rules.")
            md.append("> Patterns need multi-day confirmation. Do NOT trade with real money.")
        elif tier_mode == 'preliminary':
            md.append("> Walk-forward validation has begun but is not yet conclusive.")
            md.append("> Treat these as preliminary signals. Live trading not recommended until 10+ days.")
        md.append("")

    md.append("## Assumptions")
    md.append(f"- /MES reference price: {_cfg.MES_REFERENCE_PRICE:.0f} ({_cfg.MES_REFERENCE_SOURCE})")
    md.append(f"- Point value: ${MES_POINT_VALUE:.2f}")
    md.append(f"- Tick size: {TICK_SIZE} pts = ${TICK_VALUE:.2f}")
    md.append(f"- Round-trip cost: ${ROUND_TRIP_COST_USD:.2f}")
    md.append(f"- Slippage: {SLIPPAGE_TICKS_RT} ticks RT = ${SLIPPAGE_USD:.2f}")
    md.append(f"- All dollar figures are **estimated** based on these assumptions.")
    md.append("")

    # ── Promoted Rules ───────────────────────────────────────────────────
    if not promoted:
        md.append("## No Rules Promoted")
        md.append("No patterns survived all filters. Collect more data and retry.")
    else:
        # Separate by direction
        longs = [s for s in promoted if s.rule.direction == 'LONG']
        shorts = [s for s in promoted if s.rule.direction == 'SHORT']
        skips = [s for s in promoted if s.rule.direction == 'SKIP']

        if longs:
            md.append(f"## LONG Patterns ({len(longs)})")
            md.append("")
            for score in longs:
                md.extend(_format_rule(score, preliminary))
                md.append("")

        if shorts:
            md.append(f"## SHORT Patterns ({len(shorts)})")
            md.append("")
            for score in shorts:
                md.extend(_format_rule(score, preliminary))
                md.append("")

        if skips:
            md.append(f"## SKIP Conditions ({len(skips)})")
            md.append("*When these conditions are active, avoid new entries.*")
            md.append("")
            for score in skips:
                md.extend(_format_skip_rule(score, preliminary))
                md.append("")

    # ── Footer ───────────────────────────────────────────────────────────
    md.append("---")
    md.append("*All figures are historically observed medians, not guarantees.*")
    md.append("*Past patterns may not repeat. Use position sizing and risk management.*")

    # Write markdown
    (output_dir / 'nightly_report.md').write_text('\n'.join(md), encoding='utf-8')

    # ── JSON Report ──────────────────────────────────────────────────────
    json_report = {
        'generated': now,
        'instrument': '/MES x1',
        'data': {
            'snapshots': n_rows,
            'days': n_days,
            'features': n_features,
            'candidates': n_candidates,
            'promoted': len(promoted),
            'preliminary': preliminary,
        },
        'assumptions': {
            'mes_reference_price': _cfg.MES_REFERENCE_PRICE,
            'mes_reference_source': _cfg.MES_REFERENCE_SOURCE,
            'point_value': MES_POINT_VALUE,
            'round_trip_cost': ROUND_TRIP_COST_USD,
            'slippage_usd': SLIPPAGE_USD,
        },
        'rules': [_rule_to_json(s, preliminary) for s in promoted],
    }
    with open(output_dir / 'nightly_report.json', 'w') as f:
        json.dump(json_report, f, indent=2, default=str)


def _format_rule(score: RuleScore, preliminary: bool) -> List[str]:
    """Format a single LONG/SHORT rule for the markdown report."""
    rule = score.rule
    lines = []

    lines.append(f"### {rule.name}")
    lines.append(f"**Direction:** {rule.direction} | "
                 f"**Horizon:** {rule.horizon_min}m | "
                 f"**Confidence:** {_confidence_label(score, preliminary)}")
    lines.append("")

    # Conditions
    lines.append("**Conditions:**")
    for pred in rule.predicates:
        lines.append(f"- {pred.to_english()}")
    lines.append("")

    # Stats
    mfe_pts = score.mes_median_mfe_pts
    mae_pts = score.mes_median_mae_pts
    mfe_usd = mfe_pts * MES_POINT_VALUE
    mae_usd = mae_pts * MES_POINT_VALUE

    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Sample size | {score.support} snapshots across {score.distinct_days} day(s) |")
    lines.append(f"| Win rate | {score.win_rate*100:.1f}% |")
    lines.append(f"| Historically median favorable move | {mfe_pts:.1f} pts (${mfe_usd:.0f}) |")
    lines.append(f"| Typical adverse excursion | {mae_pts:.1f} pts (${mae_usd:.0f}) |")
    lines.append(f"| Estimated net expectancy (1 /MES) | **${score.mes_net_expectancy:.2f}** per trade |")
    lines.append(f"| Walk-forward stability | {score.wf_stability*100:.0f}% "
                 f"({score.wf_profitable_folds}/{score.wf_folds} folds) |")

    # Suggested stop/target
    suggested_stop = mae_pts * 1.5
    suggested_target_lo = mfe_pts * 0.6
    suggested_target_hi = mfe_pts * 1.0

    lines.append("")
    lines.append(f"**Suggested stop:** {suggested_stop:.1f} pts "
                 f"({_pts_to_ticks(suggested_stop)} ticks, "
                 f"${suggested_stop * MES_POINT_VALUE:.0f})")
    lines.append(f"**Suggested target range:** "
                 f"{suggested_target_lo:.1f}–{suggested_target_hi:.1f} pts "
                 f"(${suggested_target_lo * MES_POINT_VALUE:.0f}–"
                 f"${suggested_target_hi * MES_POINT_VALUE:.0f})")

    return lines


def _format_skip_rule(score: RuleScore, preliminary: bool) -> List[str]:
    """Format a SKIP rule."""
    rule = score.rule
    lines = []

    lines.append(f"### {rule.name}")
    lines.append("**When active:** Avoid new entries")
    lines.append("")
    lines.append("**Conditions:**")
    for pred in rule.predicates:
        lines.append(f"- {pred.to_english()}")
    lines.append("")
    lines.append(f"- Historically, forward moves in this state average "
                 f"{abs(score.mean_fwd_return)*100:.2f}% with no clear direction")
    lines.append(f"- Sample: {score.support} snapshots")

    return lines


def _rule_to_json(score: RuleScore, preliminary: bool) -> dict:
    """Convert a scored rule to JSON-friendly dict."""
    mfe_pts = score.mes_median_mfe_pts
    mae_pts = score.mes_median_mae_pts

    return {
        'name': score.rule.name,
        'direction': score.rule.direction,
        'horizon_min': score.rule.horizon_min,
        'conditions_english': [p.to_english() for p in score.rule.predicates],
        'conditions': [p.to_dict() for p in score.rule.predicates],
        'support': score.support,
        'distinct_days': score.distinct_days,
        'win_rate': round(score.win_rate, 4),
        'median_mfe_pts': round(mfe_pts, 2),
        'median_mfe_usd': round(mfe_pts * MES_POINT_VALUE, 2),
        'median_mae_pts': round(mae_pts, 2),
        'median_mae_usd': round(mae_pts * MES_POINT_VALUE, 2),
        'net_expectancy_usd': round(score.mes_net_expectancy, 2),
        'suggested_stop_pts': round(mae_pts * 1.5, 2),
        'suggested_stop_usd': round(mae_pts * 1.5 * MES_POINT_VALUE, 2),
        'suggested_target_lo_pts': round(mfe_pts * 0.6, 2),
        'suggested_target_hi_pts': round(mfe_pts * 1.0, 2),
        'wf_stability': round(score.wf_stability, 4),
        'confidence': _confidence_label(score, preliminary),
        'composite_score': round(score.composite_score, 4),
        'neighbor_robust': score.neighbor_robust,
    }
