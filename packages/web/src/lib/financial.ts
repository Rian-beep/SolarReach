// JS mirror of UK SEG rates and ECO4 grant logic.
// Re-exports from @solarreach/shared/ts when available; duplicates here for
// the web bundle (no workspace tsconfig refs, hackathon speed).

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

// ECO4 — simplified eligibility heuristic for the calculator.
// Real ECO4 needs: low income / off gas grid / EPC D-G / certain benefits.
// We expose two thresholds: residential income proxy via "household_income_gbp"
// and EPC band; here we ship constants the UI uses for a green pill.
export const ECO4_HOUSEHOLD_INCOME_THRESHOLD_GBP = 31000;
export const ECO4_GRANT_FLAT_GBP = 14000;
export const ECO4_GRANT_PARTIAL_GBP = 7000;

export interface Eco4Inputs {
  householdIncomeGbp?: number;
  epcBand?: "A" | "B" | "C" | "D" | "E" | "F" | "G";
  offGasGrid?: boolean;
  receivesQualifyingBenefits?: boolean;
}

export function eco4Eligibility(inputs: Eco4Inputs): {
  eligible: boolean;
  grantGbp: number;
  reason: string;
} {
  const epcBand = inputs.epcBand;
  const epcQualifies = epcBand
    ? ["D", "E", "F", "G"].includes(epcBand)
    : false;
  const incomeQualifies =
    inputs.householdIncomeGbp !== undefined &&
    inputs.householdIncomeGbp <= ECO4_HOUSEHOLD_INCOME_THRESHOLD_GBP;
  const benefitsQualify = inputs.receivesQualifyingBenefits === true;

  if ((incomeQualifies || benefitsQualify) && epcQualifies) {
    return {
      eligible: true,
      grantGbp: inputs.offGasGrid
        ? ECO4_GRANT_FLAT_GBP
        : ECO4_GRANT_PARTIAL_GBP,
      reason: "Income/benefits + EPC band D-G qualifies for ECO4",
    };
  }
  return { eligible: false, grantGbp: 0, reason: "Does not meet ECO4 criteria" };
}

const clamp = (x: number, lo = 0, hi = 1): number =>
  Math.max(lo, Math.min(hi, x));

export function compositeScore(
  solarRoi: number,
  finHealth: number,
  socialImpact: number,
): number {
  const s =
    clamp(solarRoi) * 0.5 + clamp(finHealth) * 0.3 + clamp(socialImpact) * 0.2;
  return Math.round(s * 100);
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
  annualSavingGbpVal: number,
): number {
  if (annualSavingGbpVal <= 0) return Number.POSITIVE_INFINITY;
  return capexGbp / annualSavingGbpVal;
}

export function npv25yr(
  capexGbp: number,
  annualSavingGbpVal: number,
): number {
  let npv = -capexGbp;
  for (let t = 1; t <= NPV_HORIZON_YEARS; t++) {
    const deg = (1 - PANEL_DEGRADATION_PER_YEAR) ** (t - 1);
    const cf = annualSavingGbpVal * deg;
    const disc = (1 + DISCOUNT_RATE) ** t;
    npv += cf / disc;
  }
  return npv;
}

export interface FundingModel {
  id: "outright" | "loan" | "ppa" | "lease" | "shared_savings";
  label: string;
  paymentFormula: string;
  ownershipAtEnd: string;
  segClaimer: string;
  bestFor: string;
}

export const FUNDING_MODELS: FundingModel[] = [
  {
    id: "outright",
    label: "Outright Purchase",
    paymentFormula: "100% upfront capex",
    ownershipAtEnd: "Customer owns from day one",
    segClaimer: "Customer claims SEG export tariff",
    bestFor: "Strong cash position, max long-term NPV",
  },
  {
    id: "loan",
    label: "Asset Finance Loan",
    paymentFormula: "Monthly £ = capex × annuity factor (5-10yr term)",
    ownershipAtEnd: "Customer owns after final payment",
    segClaimer: "Customer claims SEG",
    bestFor: "Spread capex; treat as opex line",
  },
  {
    id: "ppa",
    label: "Power Purchase Agreement (PPA)",
    paymentFormula: "£ per kWh consumed (typically 60-80% of grid)",
    ownershipAtEnd: "Provider owns; transfer optional at year 20-25",
    segClaimer: "PPA provider claims SEG",
    bestFor: "Zero capex, immediate bill reduction",
  },
  {
    id: "lease",
    label: "Operating Lease",
    paymentFormula: "Fixed monthly £ for 7-15 year term",
    ownershipAtEnd: "Return, extend, or buyout at residual",
    segClaimer: "Lessor claims SEG",
    bestFor: "Off-balance-sheet treatment",
  },
  {
    id: "shared_savings",
    label: "Shared Savings",
    paymentFormula: "Provider takes X% of measured savings",
    ownershipAtEnd: "Negotiated — usually customer at year 10",
    segClaimer: "Split per contract",
    bestFor: "Risk-averse customers; pay only on performance",
  },
];
