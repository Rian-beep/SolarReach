// UK commercial solar PV industry benchmarks — web bundle copy.
// Mirrors packages/shared/ts/src/industry_benchmarks.ts and
// packages/shared/py/solarreach_shared/industry_benchmarks.py.
//
// We duplicate here (rather than import @solarreach/shared) for the same
// reason the web `lib/financial.ts` module duplicates: the workspace TS
// package is built to dist/ + not wired through tsconfig refs, hackathon
// speed wins over DRY. Update all three files together.

export const UK_INSTALL_COST_PER_KW_GBP = 950.0;
export const UK_INSTALL_COST_PER_KW_RANGE_GBP: readonly [number, number] = [
  800.0, 1100.0,
];

export const UK_AVG_IRRADIANCE_KWH_PER_M2_YR = 1050.0;
export const UK_TYPICAL_KWH_PER_KWP_YR = 950.0;

export const UK_SEG_EXPORT_RATE_GBP_PER_KWH = 0.15;
export const UK_IMPORT_RATE_GBP_PER_KWH = 0.27;
export const AIA_CAP_GBP_MILLION = 1.0;

export const GRID_CARBON_KG_PER_KWH = 0.193;

export const UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL = 7.5;
export const UK_TYPICAL_IRR_COMMERCIAL = 0.10;

export const UK_COMMERCIAL_PV_GROWTH_YOY_PCT = 0.21;
export const UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT = 0.78;

export interface IndustryBenchmarks {
  uk_install_cost_per_kw_gbp: number;
  uk_install_cost_per_kw_range_gbp: readonly [number, number];
  uk_avg_irradiance_kwh_per_m2_yr: number;
  uk_typical_kwh_per_kwp_yr: number;
  seg_export_rate_gbp_per_kwh: number;
  import_rate_gbp_per_kwh: number;
  aia_cap_gbp_million: number;
  co2_kg_per_kwh_uk_2025: number;
  uk_typical_payback_years_commercial: number;
  uk_typical_irr_commercial: number;
  uk_commercial_pv_growth_yoy_pct: number;
  uk_commercial_electricity_price_rise_since_2019_pct: number;
}

export const INDUSTRY_BENCHMARKS: IndustryBenchmarks = {
  uk_install_cost_per_kw_gbp: UK_INSTALL_COST_PER_KW_GBP,
  uk_install_cost_per_kw_range_gbp: UK_INSTALL_COST_PER_KW_RANGE_GBP,
  uk_avg_irradiance_kwh_per_m2_yr: UK_AVG_IRRADIANCE_KWH_PER_M2_YR,
  uk_typical_kwh_per_kwp_yr: UK_TYPICAL_KWH_PER_KWP_YR,
  seg_export_rate_gbp_per_kwh: UK_SEG_EXPORT_RATE_GBP_PER_KWH,
  import_rate_gbp_per_kwh: UK_IMPORT_RATE_GBP_PER_KWH,
  aia_cap_gbp_million: AIA_CAP_GBP_MILLION,
  co2_kg_per_kwh_uk_2025: GRID_CARBON_KG_PER_KWH,
  uk_typical_payback_years_commercial: UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL,
  uk_typical_irr_commercial: UK_TYPICAL_IRR_COMMERCIAL,
  uk_commercial_pv_growth_yoy_pct: UK_COMMERCIAL_PV_GROWTH_YOY_PCT,
  uk_commercial_electricity_price_rise_since_2019_pct:
    UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT,
};
