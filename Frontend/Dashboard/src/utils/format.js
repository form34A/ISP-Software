import { safeToFixed } from './safeToFixed';

const zero = (dp) => (0).toFixed(dp);

const isInvalid = (value) => {
  const num = Number(value);
  return value === null || value === undefined || Number.isNaN(num);
};

export const formatPercent = (value, dp = 1) => `${safeToFixed(value, dp, zero(dp))}%`;

export const formatSpeed = (mbps, dp = 1) => {
  if (isInvalid(mbps)) return `${zero(dp)} Mbps`;
  const num = Number(mbps);
  if (num >= 1000) return `${safeToFixed(num / 1000, dp, zero(dp))} Gbps`;
  return `${safeToFixed(num, dp, zero(dp))} Mbps`;
};

export const formatMs = (ms, dp = 1) => {
  if (isInvalid(ms)) return `${zero(dp)}s`;
  return `${safeToFixed(Number(ms) / 1000, dp, zero(dp))}s`;
};

export const formatSeconds = (s, dp = 1) => `${safeToFixed(s, dp, zero(dp))}s`;
