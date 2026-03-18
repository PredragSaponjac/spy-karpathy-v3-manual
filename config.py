"""
Karpathy Autoresearch — Configuration
All tunables in one place. No magic numbers scattered across modules.
"""
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────
DB_PATH = Path(r"C:\Users\18329\Downloads\spy_autoresearch.db")
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# ─── /MES Conversion Layer ──────────────────────────────────────────────
# SPY forward return % → /MES points → dollars
MES_REFERENCE_PRICE = 6030.0        # fallback /ES level (≈ SPY × 10)
MES_REFERENCE_SOURCE = "hardcoded"   # tracks where the reference came from
MES_POINT_VALUE     = 5.0           # $5 per /MES point
TICK_SIZE           = 0.25          # /MES tick
TICK_VALUE          = 1.25          # $1.25 per tick
ROUND_TRIP_COST_USD = 2.50          # commissions + exchange RT
SLIPPAGE_TICKS_RT   = 2             # 2 ticks RT slippage
SLIPPAGE_USD        = SLIPPAGE_TICKS_RT * TICK_VALUE

def update_mes_reference_from_data(df):
    """Update MES_REFERENCE_PRICE from the latest available SPY spot price.

    Derives /ES reference as SPY × 10. Falls back to the hardcoded default
    if no valid spot data is available.

    Call this once after loading data, before any MES conversion.
    """
    global MES_REFERENCE_PRICE, MES_REFERENCE_SOURCE
    import pandas as pd

    if df is None or len(df) == 0:
        return

    # Try spot column (latest non-null value)
    if 'spot' in df.columns:
        spot_vals = df['spot'].dropna()
        if len(spot_vals) > 0:
            latest_spot = float(spot_vals.iloc[-1])
            if latest_spot > 100:  # sanity: SPY should be > $100
                MES_REFERENCE_PRICE = round(latest_spot * 10, 1)
                MES_REFERENCE_SOURCE = f"live SPY spot {latest_spot:.2f} x10"
                return

    # Fallback: keep the hardcoded default
    MES_REFERENCE_SOURCE = f"hardcoded fallback ({MES_REFERENCE_PRICE})"

def spy_pct_to_mes_points(spy_pct: float) -> float:
    """Convert SPY % return to /MES points."""
    return spy_pct / 100.0 * MES_REFERENCE_PRICE

def spy_pct_to_mes_dollars(spy_pct: float, gross: bool = False) -> float:
    """Convert SPY % return to /MES dollars (net of costs unless gross=True)."""
    pts = spy_pct_to_mes_points(spy_pct)
    gross_usd = pts * MES_POINT_VALUE
    if gross:
        return gross_usd
    return gross_usd - ROUND_TRIP_COST_USD - SLIPPAGE_USD

# ─── Forward-label columns (the ONLY outcome layer) ────────────────────
FWD_RETURN_COLS = [
    'fwd_1m', 'fwd_5m', 'fwd_15m', 'fwd_30m', 'fwd_60m', 'fwd_eod',
]
FWD_EXCURSION_COLS = [
    'fwd_max_up_5m', 'fwd_max_dn_5m',
    'fwd_max_up_15m', 'fwd_max_dn_15m', 'fwd_range_15m',
    'fwd_max_up_30m', 'fwd_max_dn_30m',
    'fwd_max_up_60m', 'fwd_max_dn_60m', 'fwd_range_60m',
]
LABEL_COLS = ['label_5m', 'label_15m', 'label_30m']

# FIX: QQQ forward columns must also be excluded from features.
# If the DB ever adds qqq_fwd_* columns, they would leak future QQQ returns
# into model features via extract_qqq_features() which only checks ALL_OUTCOME_COLS.
QQQ_OUTCOME_PREFIXES = ['qqq_fwd_', 'qqq_label_']  # defensive exclusion

ALL_OUTCOME_COLS = FWD_RETURN_COLS + FWD_EXCURSION_COLS + LABEL_COLS

# Primary horizons for pattern search (minutes)
PRIMARY_HORIZONS = [15, 30, 60]

# ─── Feature Families ───────────────────────────────────────────────────
# Column prefixes/names that define each family (used in feature_factory)
FAMILY_SPY_TAPE = [
    'spot', 'spot_chg', 'spot_chg_pct', 'spot_open', 'spot_high', 'spot_low',
    'spot_volume', 'spot_spread', 'spot_velocity', 'spot_accel',
    'from_open_pct', 'range_pos', 'day_range_pct',
]
FAMILY_SPY_DEALER = [
    'gex_total', 'dex', 'vex', 'cex', 'gamma_flip', 'gamma_flip_dist_pct',
    'gex_concentration', 'gex_above_spot', 'gex_below_spot', 'gex_asym_ratio',
    'gex_support_score', 'gex_imbalance', 'gex_normalized',
    'dealer_gamma_regime', 'dealer_pressure', 'gamma_magnification',
]
FAMILY_SPY_FLOW = [
    'nope', 'net_c_prem', 'net_p_prem', 'net_prem', 'net_delta_flow',
    'tc_vol', 'tp_vol', 'tco', 'tpo', 'pcr_vol', 'pcr_oi',
    'c_agg', 'p_agg', 'c_vol_oi_ratio', 'p_vol_oi_ratio',
    'nope_signal', 'flow_skew_div',
]
FAMILY_SPY_SKEW = [
    'atm_c_iv', 'atm_p_iv', 'atm_avg_iv',
    'iv_25d_put', 'iv_25d_call', 'iv_10d_put', 'iv_10d_call',
    'skew_25d', 'skew_10d', 'skew_rr_25d',
    'iv_slope', 'iv_curvature', 'smile_asym', 'skew_steepness',
]
FAMILY_SPY_STRUCTURE = [
    'max_pain', 'call_wall', 'put_wall', 'vol_poc', 'vah', 'val',
    'cw_prox', 'pw_prox', 'spot_vs_poc', 'spot_vs_mp',
    'spot_vs_vah', 'spot_vs_val',
    'pin_score', 'pin_magnet',
]
FAMILY_SPY_EXPANDED = [
    'real_theta_atm', 'total_real_theta', 'real_vega_atm', 'total_real_vega',
    'extrinsic_atm', 'pitm_delta_div',
    'atm_straddle_chg_from_open', 'netchg_call_put_div',
]
FAMILY_SPY_0DTE = [
    'theta_per_min', 'theta_per_hour', 'atm_straddle', 'atm_straddle_pct',
    'expected_move_pct', 'atm_gamma_dollar',
    'strike_gravity', 'gravity_center', 'gravity_pull',
    'credit_env', 'breakout_env',
]
FAMILY_FLUXGATE = [
    'efficiency_ratio', 'price_entropy', 'entropy_normalized',
    'fractal_cohesion', 'directional_intensity',
    'persistence', 'persistence_direction', 'price_curvature',
    'shock_ratio', 'rvol', 'structural_gate',
]
FAMILY_MICRO = [
    'charm_meltup_score', 'charm_meltup_dir',
    'vanna_crush_score', 'vanna_crush_dir',
    'iv_crush_magnitude', 'seller_dominance', 'fresh_put_bias',
    'theta_curve_pos', 'theta_divergence',
    'tick_proxy', 'tick_zone', 'tick_zone_code',
    'gamma_danger', 'exposure_score',
]
FAMILY_INTERNALS = [
    'tick', 'tick_sp', 'nyse_add', 'adspd', 'ad_ratio', 'ad_breadth',
    'vold', 'uvol_dvol_ratio', 'trin', 'trin_sp', 'trin_zone',
    'vix', 'vix9d', 'vvix', 'vix_chg',
    'vix_term_ratio', 'vix_term_spread', 'vix_term_inverted',
    'breadth_composite', 'cross_asset_score',
    'sector_rotation', 'sectors_green', 'sectors_red',
    'es_spy_basis', 'cl_chg', 'gc_chg', 'zn_chg', 'dx_chg',
]
FAMILY_SIGNALS = [
    'sig_trend_long', 'sig_trend_short', 'sig_mean_revert',
    'sig_breakout', 'sig_fade',
    'regime_transitioning', 'pin_trending',
    'iv_trending', 'iv_crush_active', 'iv_spike_active', 'volume_surge',
]
FAMILY_CONTEXT = [
    'mins_since_open', 'mins_to_close', 'pct_of_day',
    'regime',
]

# All SPY feature families (order matters for reporting)
ALL_SPY_FAMILIES = {
    'tape':      FAMILY_SPY_TAPE,
    'dealer':    FAMILY_SPY_DEALER,
    'flow':      FAMILY_SPY_FLOW,
    'skew':      FAMILY_SPY_SKEW,
    'structure': FAMILY_SPY_STRUCTURE,
    'expanded':  FAMILY_SPY_EXPANDED,
    '0dte':      FAMILY_SPY_0DTE,
    'fluxgate':  FAMILY_FLUXGATE,
    'micro':     FAMILY_MICRO,
    'internals': FAMILY_INTERNALS,
    'signals':   FAMILY_SIGNALS,
    'context':   FAMILY_CONTEXT,
}

# ─── Pattern Search ─────────────────────────────────────────────────────
MAX_PREDICATES_DEFAULT = 3       # max conjuncts per rule
MAX_PREDICATES_ELITE   = 4       # only for top survivors
MIN_SUPPORT            = 30      # min snapshots matching a rule
MIN_DISTINCT_DAYS      = 2       # min trading days (relaxed for early data)
QUANTILE_BINS          = 5       # quintile binning for level rules
NEIGHBOR_BAND_PCT      = 0.10    # ±10% for threshold robustness check
MAX_OVERLAP            = 0.60    # Jaccard overlap threshold for deduplication
MIN_COMPOSITE_SCORE    = 0.0     # minimum composite score to pass promotion

# ─── Tiered Maturity System ─────────────────────────────────────────────
# Hard gates based on how many distinct trading days are in the DB.
# Prevents one-day regime capture from masquerading as alpha.
MATURITY_TIERS = {
    # (min_days, max_days): {config overrides}
    (0, 2):   {  # < 3 days → FEATURES ONLY, no promotion at all
        'mode': 'features_only',
        'max_promoted': 0,
        'max_entry_rules': 0,
        'max_skip_rules': 0,
        'label': 'FEATURES ONLY — insufficient data',
    },
    (3, 4):   {  # 3-4 days → RESEARCH mode, watchlist only
        'mode': 'research',
        'max_promoted': 8,
        'max_entry_rules': 4,
        'max_skip_rules': 4,
        'min_wf_folds': 1,
        'label': 'RESEARCH — watchlist candidates only',
    },
    (5, 9):   {  # 5-9 days → PRELIMINARY, cautious promotion
        'mode': 'preliminary',
        'max_promoted': 14,
        'max_entry_rules': 6,
        'max_skip_rules': 8,
        'min_wf_folds': 2,
        'label': 'PRELIMINARY — not yet live-trading ready',
    },
    (10, 999): { # 10+ days → LIVE, full walk-forward promotion
        'mode': 'live',
        'max_promoted': 24,
        'max_entry_rules': 6,
        'max_skip_rules': 12,
        'min_wf_folds': 3,
        'label': 'LIVE — walk-forward validated',
    },
}

def get_maturity_tier(n_days: int) -> dict:
    """Return the maturity config for the given day count."""
    for (lo, hi), tier in MATURITY_TIERS.items():
        if lo <= n_days <= hi:
            return tier
    return MATURITY_TIERS[(0, 2)]  # fallback to most conservative

# Legacy alias (used in rule_compiler)
MAX_LIVE_RULES = 24

# ─── Concentration Limits ───────────────────────────────────────────────
# Prevents single-day/regime dominance from inflating scores
MAX_SINGLE_DAY_SCORE_PCT   = 0.35   # no single day may contribute >35% of total score
MAX_SINGLE_REGIME_SCORE_PCT = 0.60   # no single regime may contribute >60%
MIN_TOD_BUCKETS            = 2       # rule must fire in ≥2 time-of-day buckets (unless TOD-specific)

# ─── MFE Winsorization ──────────────────────────────────────────────────
MFE_WINSORIZE_PCTILE = 0.95   # clip MFE at 95th percentile to prevent outlier inflation

# ─── Walk-Forward ────────────────────────────────────────────────────────
WF_MIN_TRAIN_DAYS  = 3           # min days in train fold
WF_VAL_DAYS        = 1           # days per validation fold
WF_HOLDOUT_DAYS    = 1           # final holdout (untouched)
WF_EXPANDING       = True        # expanding window (vs rolling)

# ─── Scoring Weights ────────────────────────────────────────────────────
W_NET_EXPECTANCY   = 0.40        # net $ after costs
W_MFE              = 0.20        # median favorable excursion
W_DIRECTION        = 0.15        # directional accuracy
W_SKIP_ACCURACY    = 0.10        # skip-rule accuracy
W_STABILITY        = 0.15        # day-to-day stability

# Penalties
P_DRAWDOWN         = 0.10        # penalize high MAE
P_COMPLEXITY       = 0.05        # per predicate beyond 2
P_LOW_SUPPORT      = 0.10        # penalize thin rules
P_OVERLAP          = 0.15        # penalize overlapping rules

# ─── Time-of-Day Buckets ────────────────────────────────────────────────
# Minutes since 9:30 ET open
TOD_BUCKETS = {
    'open_5':     (0, 5),
    'open_15':    (5, 15),
    'open_30':    (15, 30),
    'morning':    (30, 90),
    'midday':     (90, 210),
    'afternoon':  (210, 330),
    'power_hour': (330, 390),
}

# ─── Flat thresholds for labeling ───────────────────────────────────────
FLAT_THRESH = {
    '5m':  0.10,    # % return
    '15m': 0.15,
    '30m': 0.20,
}

# ─── Karpathy Shell Defaults ──────────────────────────────────────────
# These are overridden at runtime by HypothesisOverride in karpathy_runner.py.
# Do NOT change defaults here — change hypothesis.py instead.
RULE_FAMILIES_ENABLED = {
    "level": True, "interaction": True, "divergence": True,
    "sequence": True, "skip": True,
}
FEATURE_FAMILY_WEIGHTS = {}      # empty = all 1.0
DIVERGENCE_FAMILY_WEIGHTS = {}   # empty = all 1.0
SEQUENCE_FAMILY_WEIGHTS = {}     # empty = all 1.0

# Divergence priority tier weights (Primary > Secondary > Tertiary)
DIVERGENCE_PRIORITY_WEIGHTS = {
    "primary":   1.0,   # div_nope, div_net_prem, div_net_delta_flow, div_gex, div_atm_iv
    "secondary": 0.7,   # div_gex_normalized, div_pin_score, div_skew_*, div_iv_*, div_straddle_pct
    "tertiary":  0.4,   # div_dex, div_vex, div_cex, div_pcr_vol, div_awks (multi-day only)
}
SKIP_AGGRESSIVENESS = 1.0        # multiplier on skip composite score
INTERMARKET_WEIGHT = 1.0         # bonus multiplier for divergence-family rules
MOVE_SIZE_PREFERENCE = 1.0       # multiplier on MFE component in entry composite

# ─── LLM Budget Guard ──────────────────────────────────────────────────
# Controls proposer/critic spend only. Does NOT affect the deterministic engine.
LLM_INPUT_PRICE_PER_MTOK          = 3.0      # $/1M input tokens  (claude-sonnet-4-6)
LLM_OUTPUT_PRICE_PER_MTOK         = 15.0     # $/1M output tokens (claude-sonnet-4-6)
LLM_HARD_BUDGET_USD               = 30.0     # abort LLM loop immediately
LLM_SOFT_BUDGET_USD               = 24.0     # stop launching new challengers
LLM_MAX_CHALLENGERS               = 5        # max challenger attempts per run
LLM_MAX_OUTPUT_TOKENS_PER_CALL    = 4000     # max_tokens sent to API
LLM_DEFAULT_MODEL                 = "claude-sonnet-4-6"
LLM_PROJECTED_PROPOSER_INPUT_TOKENS  = 6000  # typical proposer context size
LLM_PROJECTED_PROPOSER_OUTPUT_TOKENS = 1500  # typical proposer response
LLM_PROJECTED_CRITIC_INPUT_TOKENS    = 8000  # critic sees diagnostics + patch
LLM_PROJECTED_CRITIC_OUTPUT_TOKENS   = 1000  # critic response
