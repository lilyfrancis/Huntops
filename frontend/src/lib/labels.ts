/**
 * Turning stored values into words a person would actually write.
 *
 * The database stores `gtm`, `hr`, `email-linkedin`. Naively title-casing those
 * gives "Gtm", "Hr", "Linkedin" — which look like bugs to anyone who works in
 * those fields, because they are the one thing on the screen we spelled wrong.
 */

/** Acronyms and camel-cased brands that title-casing would mangle. */
const EXACT_CASE: Record<string, string> = {
  gtm: "GTM",
  hr: "HR",
  revops: "RevOps",
  linkedin: "LinkedIn",
  indeed: "Indeed",
  glassdoor: "Glassdoor",
  remotive: "Remotive",
  remoteok: "RemoteOK",
  arbeitnow: "Arbeitnow",
  adzuna: "Adzuna",
  jobicy: "Jobicy",
  internal: "HuntOps",
  unknown: "the source site",
};

export function humanize(value: string): string {
  const exact = EXACT_CASE[value.toLowerCase()];
  if (exact) return exact;
  return value
    .split(/[_\s]+/)
    .map((word) => EXACT_CASE[word.toLowerCase()] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** `email-linkedin` and `remotive` both name where a listing came from. */
export function sourceLabel(source: string): string {
  return humanize(source.replace(/^email-/, ""));
}
