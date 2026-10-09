const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = new Intl.NumberFormat("en-US");

export const money = (v: number | null | undefined, cents = true) =>
  v == null ? "—" : (cents ? usd2 : usd0).format(v);
export const moneyCompact = (v: number) => (Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${Math.round(v)}`);
export const num = (v: number | null | undefined) => (v == null ? "—" : int.format(v));
export const pct = (v: number | null | undefined, digits = 1) => (v == null ? "—" : `${v.toFixed(digits)}%`);
export const signed = (v: number, digits = 1) => `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;

/** YYYY-MM-DD arithmetic in UTC so it never shifts with the viewer's timezone. */
export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
