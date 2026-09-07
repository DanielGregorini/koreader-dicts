import { Link } from "@/components/link";
import { locales, localeInfo, type Locale } from "@/i18n/routing";

// Same page, different interface language. `path` is the current route without
// its locale prefix, so every link lands on the equivalent page.
export function LocaleSwitcher({
  current,
  path = "/",
}: {
  current: Locale;
  path?: string;
}) {
  return (
    <ul className="ml-auto flex flex-wrap items-center gap-1">
      {locales.map((locale) => {
        const active = locale === current;
        return (
          <li key={locale}>
            <Link
              locale={locale}
              href={path}
              hrefLang={localeInfo[locale].tag}
              aria-current={active ? "true" : undefined}
              aria-label={localeInfo[locale].name}
              title={localeInfo[locale].name}
              className={
                active
                  ? "inline-block rounded px-1.5 py-0.5 text-xs font-semibold tracking-wide text-accent uppercase no-underline dark:text-accent-dark"
                  : "inline-block rounded px-1.5 py-0.5 text-xs tracking-wide text-neutral-500 uppercase no-underline hover:text-accent dark:text-neutral-400 dark:hover:text-accent-dark"
              }
            >
              {locale}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
