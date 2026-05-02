// JS mirror of solarreach_shared/financial.py — parity within ±£1.

export const SCORE_WEIGHT_SOLAR_ROI = 0.5;
export const SCORE_WEIGHT_FIN_HEALTH = 0.3;
export const SCORE_WEIGHT_SOCIAL_IMPACT = 0.2;
export const SCORE_THRESHOLD_DEFAULT = 70;

export const PANEL_UNIT_COST_GBP = 850.0;
export const INSTALL_COST_PER_KW_GBP = 180.0;
export const PANEL_RATED_KW = 0.42;
export const INSTALLER_MARGIN_PCT = 0.04;

export const UK_SEG_EXPORT_RATE_GBP_PER_KWH = 0.15;
export const UK_IMPORT_RATE_GBP_PER_KWH = 0.27;
export const SELF_CONSUME_FRACTION = 0.5;
export const DISCOUNT_RATE = 0.05;
export const NPV_HORIZON_YEARS = 25;
export const PANEL_DEGRADATION_PER_YEAR = 0.005;

const clamp = (x: number, lo = 0, hi = 1): number =>
  Math.max(lo, Math.min(hi, x));

export function compositeScore(
  solarRoi: number,
  finHealth: number,
  socialImpact: number,
): number {
  const s =
    clamp(solarRoi) * SCORE_WEIGHT_SOLAR_ROI +
    clamp(finHealth) * SCORE_WEIGHT_FIN_HEALTH +
    clamp(socialImpact) * SCORE_WEIGHT_SOCIAL_IMPACT;
  return Math.round(s * 100);
}

export function roiGate(
  score: number,
  threshold: number = SCORE_THRESHOLD_DEFAULT,
): boolean {
  return score >= threshold;
}

export function capex(panelCount: number): number {
  if (panelCount <= 0) return 0;
  const ratedKw = panelCount * PANEL_RATED_KW;
  const base =
    panelCount * PANEL_UNIT_COST_GBP + ratedKw * INSTALL_COST_PER_KW_GBP;
  return base * (1 + INSTALLER_MARGIN_PCT);
}

export function annualSavingGbp(annualKwh: number): number {
  if (annualKwh <= 0) return 0;
  const selfConsumed = annualKwh * SELF_CONSUME_FRACTION;
  const exported = annualKwh - selfConsumed;
  return (
    selfConsumed * UK_IMPORT_RATE_GBP_PER_KWH +
    exported * UK_SEG_EXPORT_RATE_GBP_PER_KWH
  );
}

export function paybackYears(
  capexGbp: number,
  annualSavingGbp: number,
): number {
  if (annualSavingGbp <= 0) return Infinity;
  return capexGbp / annualSavingGbp;
}

export function npv25yr(
  capexGbp: number,
  annualSavingGbp: number,
): number {
  let npv = -capexGbp;
  for (let t = 1; t <= NPV_HORIZON_YEARS; t++) {
    const deg = (1 - PANEL_DEGRADATION_PER_YEAR) ** (t - 1);
    const cf = annualSavingGbp * deg;
    const disc = (1 + DISCOUNT_RATE) ** t;
    npv += cf / disc;
  }
  return npv;
}

// CLI smoke
if (
  typeof process !== "undefined" &&
  process.argv?.[1]?.endsWith("financial.ts")
) {
  console.log("compositeScore(0.8, 0.6, 0.4) =", compositeScore(0.8, 0.6, 0.4));
  console.log("capex(24) =", capex(24).toFixed(2));
  console.log("npv25yr(20000, 2500) =", npv25yr(20000, 2500).toFixed(2));
}
