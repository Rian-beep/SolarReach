import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format a GBP amount.
 * Pass `cents: true` if value is in pennies/cents — otherwise treated as GBP.
 */
export function gbp(
  amount: number,
  opts: { cents?: boolean; decimals?: number } = {},
): string {
  const { cents = false, decimals } = opts;
  const value = cents ? amount / 100 : amount;
  const fmt = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: decimals ?? (Math.abs(value) < 10 ? 2 : 0),
    maximumFractionDigits: decimals ?? (Math.abs(value) < 10 ? 2 : 0),
  });
  return fmt.format(value);
}

/** UK postcode normalizer — uppercase + single space before final 3 chars. */
export function formatPostcode(s: string): string {
  const cleaned = s.replace(/\s+/g, "").toUpperCase();
  if (cleaned.length < 5) return cleaned;
  return `${cleaned.slice(0, cleaned.length - 3)} ${cleaned.slice(-3)}`;
}

/** Tailwind class names for score-band tints. */
export function scoreBadgeClass(score: number): string {
  if (score >= 70) {
    return "bg-emerald/10 text-emerald border-emerald/40";
  }
  if (score >= 50) {
    return "bg-amber/10 text-amber border-amber/40";
  }
  return "bg-red/10 text-red border-red/40";
}

/** Format lat/lng to fixed mono presentation. */
export function formatLatLng(lng: number, lat: number): string {
  const sign = (n: number, p: string, neg: string): string =>
    n >= 0 ? `${p}${Math.abs(n).toFixed(4)}` : `${neg}${Math.abs(n).toFixed(4)}`;
  return `${sign(lat, "N", "S")} ${sign(lng, "E", "W")}`;
}

/** Sleep helper. */
export const sleep = (ms: number): Promise<void> =>
  new Promise((r) => setTimeout(r, ms));

/**
 * Gotham caption className — single source of truth for tiny UPPERCASE labels
 * (e.g. CAPEX, OWNER, LAT/LNG, "buyer · #1 question").
 * Mono · 10px · widest tracking · grid color by default.
 * Override the color by passing `cn(caption, "text-emerald")` etc.
 */
export const caption =
  "font-mono text-[10px] uppercase tracking-widest text-grid";
