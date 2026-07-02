/**
 * Safely coerce a value to a fixed-decimal string, guarding against
 * null/undefined/NaN/non-numeric values (e.g. Decimal fields the API
 * serializes as strings, like "12.50").
 */
export const safeToFixed = (value, decimals = 1, fallback = '0') => {
  const num = Number(value);
  if (value === null || value === undefined || Number.isNaN(num)) return fallback;
  return num.toFixed(decimals);
};
