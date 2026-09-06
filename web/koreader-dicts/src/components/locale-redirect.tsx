"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { locales, defaultLocale, isLocale, type Locale } from "@/i18n/routing";

function preferredLocale(): Locale {
  const wanted = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const tag of wanted) {
    // Base subtag only, so pt-BR and pt-PT both match pt.
    const base = tag?.toLowerCase().split("-")[0] ?? "";
    if (isLocale(base)) return base;
  }

  return defaultLocale;
}

// Static export has no middleware, so language negotiation runs in the browser.
export function LocaleRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace(`/${preferredLocale()}/`);
  }, [router]);

  return null;
}

// Fallback for readers without JavaScript. A bare <a> does not get basePath
// from Next, so it is applied here.
export function LocaleLinks() {
  const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  return locales.map((locale) => (
    <a key={locale} href={`${base}/${locale}/`}>
      {locale}
    </a>
  ));
}
