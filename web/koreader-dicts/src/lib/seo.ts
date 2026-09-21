// One place that builds page metadata, because every page needs its own.
//
// Next merges a layout's metadata into each page's, and the page only wins on
// the fields it sets. A canonical declared once in the locale layout was
// therefore inherited by all 490 dictionary pages, every one of them telling
// Google it was a duplicate of that locale's home page. Nothing under /en/
// except /en/ itself could be indexed. Every page now names its own.

import type { Metadata } from "next";
import { locales, localeInfo, defaultLocale, type Locale } from "@/i18n/routing";
import { SITE_URL } from "@/lib/repo";

/** *path* is the part after the locale, with both slashes: "/", "/downloads/". */
export function pageMetadata({
  locale,
  path,
  title,
  description,
}: {
  locale: Locale;
  path: string;
  title: string;
  description: string;
}): Metadata {
  const url = `${SITE_URL}/${locale}${path}`;
  return {
    title,
    description,
    alternates: {
      canonical: url,
      languages: Object.fromEntries([
        ...locales.map((l) => [localeInfo[l].tag, `${SITE_URL}/${l}${path}`]),
        ["x-default", `${SITE_URL}/${defaultLocale}${path}`],
      ]),
    },
    openGraph: {
      type: "website",
      siteName: "koreader-dicts",
      locale: localeInfo[locale].tag,
      url,
      title,
      description,
    },
    twitter: { card: "summary", title, description },
  };
}
