"use client";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/components/link";
import { LocaleSwitcher } from "@/components/locale-switcher";
import type { Locale } from "@/i18n/routing";

const TABS = [
  { href: "/", key: "dictionaries" },
  { href: "/downloads", key: "downloads" },
  { href: "/how-it-works", key: "howItWorks" },
] as const;

export function Nav({ locale }: { locale: Locale }) {
  const t = useTranslations("nav");
  const pathname = usePathname() ?? "/";
  const rest = pathname.replace(/^\/[^/]+/, "").replace(/\/$/, "") || "/";

  return (
    <header className="border-b border-line bg-card dark:border-line-dark dark:bg-card-dark">
      <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
        <Link
          locale={locale}
          href="/"
          className="font-bold whitespace-nowrap text-ink no-underline dark:text-ink-dark"
        >
          <span aria-hidden="true">📖</span> KOReader Dicts
        </Link>

        <nav aria-label={t("label")}>
          <ul className="flex flex-wrap gap-1">
            {TABS.map((tab) => {
              const current = tab.href === rest;
              return (
                <li key={tab.key}>
                  <Link
                    locale={locale}
                    href={tab.href}
                    aria-current={current ? "page" : undefined}
                    className={
                      current
                        ? "inline-block rounded-md bg-accent-soft px-3 py-1.5 text-sm font-semibold text-accent no-underline dark:bg-accent-soft-dark dark:text-accent-dark"
                        : "inline-block rounded-md px-3 py-1.5 text-sm text-neutral-500 no-underline hover:bg-accent-soft hover:text-accent dark:text-neutral-400 dark:hover:bg-accent-soft-dark dark:hover:text-accent-dark"
                    }
                  >
                    {t(tab.key)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <LocaleSwitcher current={locale} path={rest} />
      </div>
    </header>
  );
}
