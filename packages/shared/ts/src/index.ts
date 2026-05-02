export * from "./models.js";
export * from "./financial.js";
// industry_benchmarks.ts intentionally re-defines a handful of the same
// physical constants (PANEL_RATED_KW, UK_SEG_EXPORT_RATE_GBP_PER_KWH,
// UK_IMPORT_RATE_GBP_PER_KWH, PANEL_DEGRADATION_PER_YEAR) so it can mirror
// the Python `industry_benchmarks.py` 1:1 and stand alone as a citation
// source. Re-export the unique benchmark keys explicitly to avoid the flat
// `export *` collision; consumers can still import the duplicates directly
// from "@solarreach/shared/industry_benchmarks".
export {
  UK_INSTALL_COST_PER_KW_GBP,
  UK_INSTALL_COST_PER_KW_RANGE_GBP,
  UK_AVG_IRRADIANCE_KWH_PER_M2_YR,
  UK_TYPICAL_KWH_PER_KWP_YR,
  PERFORMANCE_DERATE_PCT,
  VAT_RESIDENTIAL_PV_PCT,
  AIA_CAP_GBP_MILLION,
  FULL_EXPENSING_AVAILABLE,
  GRID_CARBON_KG_PER_KWH,
  CO2_KG_PER_TREE_PER_YEAR,
  UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL,
  UK_TYPICAL_PAYBACK_RANGE_YEARS,
  UK_TYPICAL_IRR_COMMERCIAL,
  UK_COMMERCIAL_PV_GROWTH_YOY_PCT,
  UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT,
  FUNDING_MODELS,
  INDUSTRY_BENCHMARKS,
  type FundingModel,
  type IndustryBenchmarks,
} from "./industry_benchmarks.js";
