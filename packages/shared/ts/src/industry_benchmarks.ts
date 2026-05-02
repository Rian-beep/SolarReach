// UK commercial solar PV industry benchmarks — TS mirror of
// packages/shared/py/solarreach_shared/industry_benchmarks.py.
//
// Keep keys + values identical across both files. Update them together.
// Source documentation lives in the Python module's docstrings.

export const UK_INSTALL_COST_PER_KW_GBP = 950.0;
export const UK_INSTALL_COST_PER_KW_RANGE_GBP: readonly [number, number] = [
  800.0, 1100.0,
];
export const PANEL_RATED_KW = 0.42;

export const UK_AVG_IRRADIANCE_KWH_PER_M2_YR = 1050.0;
export const UK_TYPICAL_KWH_PER_KWP_YR = 950.0;
export const PERFORMANCE_DERATE_PCT = 0.85;
export const PANEL_DEGRADATION_PER_YEAR = 0.005;

export const UK_SEG_EXPORT_RATE_GBP_PER_KWH = 0.15;
export const UK_IMPORT_RATE_GBP_PER_KWH = 0.27;
export const VAT_RESIDENTIAL_PV_PCT = 0.0;
export const AIA_CAP_GBP_MILLION = 1.0;
export const FULL_EXPENSING_AVAILABLE = true;

export const GRID_CARBON_KG_PER_KWH = 0.193;
export const CO2_KG_PER_TREE_PER_YEAR = 22.0;

export const UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL = 7.5;
export const UK_TYPICAL_PAYBACK_RANGE_YEARS: readonly [number, number] = [
  6.0, 10.0,
];
export const UK_TYPICAL_IRR_COMMERCIAL = 0.10;

export const UK_COMMERCIAL_PV_GROWTH_YOY_PCT = 0.21;
export const UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT = 0.78;

export interface FundingModel {
  name: string;
  fit: string;
  term_years: string;
  balance_sheet: string;
}

export const FUNDING_MODELS: readonly FundingModel[] = [
  {
    name: "Capital Expense",
    fit: "Best NPV, full ownership, claims SEG",
    term_years: "n/a (outright)",
    balance_sheet: "on (asset)",
  },
  {
    name: "Free Install (PPA)",
    fit: "Zero capex, provider keeps SEG",
    term_years: "25",
    balance_sheet: "off (no asset, opex only)",
  },
  {
    name: "Lease Purchase",
    fit: "Cashflow + ownership at year 7",
    term_years: "7",
    balance_sheet: "on (finance lease)",
  },
  {
    name: "Operational Lease",
    fit: "Off-balance-sheet, fully tax-deductible",
    term_years: "5",
    balance_sheet: "off (operating lease)",
  },
  {
    name: "Hire Purchase",
    fit: "VAT efficient, year-1 capital allowances",
    term_years: "5",
    balance_sheet: "on (asset + loan)",
  },
] as const;

export interface IndustryBenchmarks {
  uk_install_cost_per_kw_gbp: number;
  uk_install_cost_per_kw_range_gbp: readonly [number, number];
  uk_avg_irradiance_kwh_per_m2_yr: number;
  uk_typical_kwh_per_kwp_yr: number;
  performance_derate_pct: number;
  panel_degradation_per_year: number;
  seg_export_rate_gbp_per_kwh: number;
  import_rate_gbp_per_kwh: number;
  vat_residential_pct: number;
  aia_cap_gbp_million: number;
  full_expensing_available: boolean;
  co2_kg_per_kwh_uk_2025: number;
  co2_kg_per_tree_per_year: number;
  uk_typical_payback_years_commercial: number;
  uk_typical_payback_range_years: readonly [number, number];
  uk_typical_irr_commercial: number;
  uk_commercial_pv_growth_yoy_pct: number;
  uk_commercial_electricity_price_rise_since_2019_pct: number;
}

export const INDUSTRY_BENCHMARKS: IndustryBenchmarks = {
  uk_install_cost_per_kw_gbp: UK_INSTALL_COST_PER_KW_GBP,
  uk_install_cost_per_kw_range_gbp: UK_INSTALL_COST_PER_KW_RANGE_GBP,
  uk_avg_irradiance_kwh_per_m2_yr: UK_AVG_IRRADIANCE_KWH_PER_M2_YR,
  uk_typical_kwh_per_kwp_yr: UK_TYPICAL_KWH_PER_KWP_YR,
  performance_derate_pct: PERFORMANCE_DERATE_PCT,
  panel_degradation_per_year: PANEL_DEGRADATION_PER_YEAR,
  seg_export_rate_gbp_per_kwh: UK_SEG_EXPORT_RATE_GBP_PER_KWH,
  import_rate_gbp_per_kwh: UK_IMPORT_RATE_GBP_PER_KWH,
  vat_residential_pct: VAT_RESIDENTIAL_PV_PCT,
  aia_cap_gbp_million: AIA_CAP_GBP_MILLION,
  full_expensing_available: FULL_EXPENSING_AVAILABLE,
  co2_kg_per_kwh_uk_2025: GRID_CARBON_KG_PER_KWH,
  co2_kg_per_tree_per_year: CO2_KG_PER_TREE_PER_YEAR,
  uk_typical_payback_years_commercial: UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL,
  uk_typical_payback_range_years: UK_TYPICAL_PAYBACK_RANGE_YEARS,
  uk_typical_irr_commercial: UK_TYPICAL_IRR_COMMERCIAL,
  uk_commercial_pv_growth_yoy_pct: UK_COMMERCIAL_PV_GROWTH_YOY_PCT,
  uk_commercial_electricity_price_rise_since_2019_pct:
    UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT,
};
