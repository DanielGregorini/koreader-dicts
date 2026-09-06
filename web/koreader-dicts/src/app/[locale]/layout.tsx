import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import {
  getMessages,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import "../globals.css";
import { Footer } from "@/components/footer";
import { Nav } from "@/components/nav";
import { locales, localeInfo, type Locale } from "@/i18n/routing";
import { SITE_URL } from "@/lib/repo";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "site" });
  return {
    title: t("title"),
    description: t("description"),
    alternates: {
      canonical: `${SITE_URL}/${locale}/`,
      languages: Object.fromEntries([
        ...locales.map((l) => [localeInfo[l].tag, `${SITE_URL}/${l}/`]),
        ["x-default", `${SITE_URL}/en/`],
      ]),
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(locales, locale)) notFound();

  // Required for static rendering.
  setRequestLocale(locale);

  const messages = await getMessages();
  const info = localeInfo[locale as Locale];

  return (
    <html lang={info.tag} dir={info.dir}>
      <body className="min-h-screen bg-paper text-ink antialiased dark:bg-paper-dark dark:text-ink-dark">
        <NextIntlClientProvider messages={messages}>
          <Nav locale={locale as Locale} />
          <main className="mx-auto w-full max-w-4xl px-5 py-10">
            {children}
          </main>
          <Footer locale={locale as Locale} />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
