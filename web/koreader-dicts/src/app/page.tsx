import type { Metadata } from "next";
import "./globals.css";
import { LocaleRedirect, LocaleLinks } from "@/components/locale-redirect";
import { defaultLocale } from "@/i18n/routing";
import { SITE_URL } from "@/lib/repo";

export const metadata: Metadata = {
  title: "koreader-dicts",
  // No content of its own; the localised pages are the ones to index.
  robots: { index: false, follow: true },
  alternates: { canonical: `${SITE_URL}/${defaultLocale}/` },
};

export default function RootPage() {
  return (
    <html lang={defaultLocale}>
      <body className="min-h-screen bg-paper text-ink antialiased dark:bg-paper-dark dark:text-ink-dark">
        <LocaleRedirect />
        <noscript>
          <main className="mx-auto w-full max-w-lg px-5 py-32 text-center">
            <h1 className="text-2xl font-bold">koreader-dicts</h1>
            <p className="mt-3 text-neutral-500 dark:text-neutral-400">
              Choose a language: <LocaleLinks />
            </p>
          </main>
        </noscript>
      </body>
    </html>
  );
}
