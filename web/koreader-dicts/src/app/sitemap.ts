import type { MetadataRoute } from "next";
import { builtDictionaries, loadCatalog } from "@/lib/catalog";
import { locales, localeInfo, defaultLocale } from "@/i18n/routing";
import { SITE_URL } from "@/lib/repo";

// Next does not apply basePath here, so every URL is built from SITE_URL.
// Emitted at <basePath>/sitemap.xml; submit that URL in Search Console.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const catalog = loadCatalog();
  const lastModified = new Date(catalog.generated_at);
  const paths = [
    { path: "/", priority: 1 },
    { path: "/downloads/", priority: 0.9 },
    { path: "/how-it-works/", priority: 0.7 },
    ...builtDictionaries(catalog).map((record) => ({
      path: `/${record.pair}/`,
      priority: 0.8,
    })),
  ];

  return locales.flatMap((locale) =>
    paths.map(({ path, priority }) => ({
      url: `${SITE_URL}/${locale}${path}`,
      lastModified,
      changeFrequency: "monthly" as const,
      priority,
      alternates: {
        languages: Object.fromEntries([
          ...locales.map((l) => [localeInfo[l].tag, `${SITE_URL}/${l}${path}`]),
          ["x-default", `${SITE_URL}/${defaultLocale}${path}`],
        ]),
      },
    })),
  );
}
