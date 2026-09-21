import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/repo";

// Served at <basePath>/robots.txt. Crawlers only read robots.txt at the domain
// root, which this project does not own on github.io, so this file is correct
// but not consulted today; the sitemap is submitted to Search Console instead.
// It starts working unchanged the day the site moves to its own domain.
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
