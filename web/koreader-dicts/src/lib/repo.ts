export const GITHUB_USER = "https://github.com/DanielGregorini";

export const REPO_URL = `${GITHUB_USER}/koreader-dicts`;

export const ISSUES_URL = `${REPO_URL}/issues`;

export const RELEASES_URL = `${REPO_URL}/releases`;

// Absolute, no trailing slash. Next does not apply basePath to metadata, so
// canonical and hreflang links are built from this.
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://danielgregorini.github.io/koreader-dicts"
).replace(/\/$/, "");

export const RELEASES_BASE =
  process.env.NEXT_PUBLIC_RELEASES_BASE ?? `${REPO_URL}/releases/latest/download`;
