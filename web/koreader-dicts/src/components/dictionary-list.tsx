"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/components/link";
import {
  downloadUrl,
  formatNumber,
  languageName,
  sizeMb,
  type DictionaryRecord,
} from "@/lib/dictionaries";
import type { Locale } from "@/i18n/routing";

const ALL = "all";

// One row per published dictionary, filtered by language.
export function DictionaryList({
  locale,
  records,
}: {
  locale: Locale;
  records: DictionaryRecord[];
}) {
  const t = useTranslations("list");
  const [language, setLanguage] = useState<string>(ALL);

  const languages = useMemo(() => {
    const codes = new Set<string>();
    for (const record of records) {
      codes.add(record.source_lang);
      codes.add(record.target_lang);
    }
    return [...codes].sort((a, b) => languageName(a).localeCompare(languageName(b)));
  }, [records]);

  const visible = useMemo(() => {
    // Matches either side of the pair.
    const filtered =
      language === ALL
        ? records
        : records.filter((r) => r.source_lang === language || r.target_lang === language);
    return [...filtered].sort((a, b) => a.pair.localeCompare(b.pair));
  }, [records, language]);

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <label
          htmlFor="language-filter"
          className="text-sm text-neutral-500 dark:text-neutral-400"
        >
          {t("filterLabel")}
        </label>
        <select
          id="language-filter"
          value={language}
          onChange={(event) => setLanguage(event.target.value)}
          className="rounded-md border border-line bg-card px-2.5 py-1.5 text-sm dark:border-line-dark dark:bg-card-dark"
        >
          <option value={ALL}>{t("allLanguages")}</option>
          {languages.map((code) => (
            <option key={code} value={code}>
              {languageName(code)}
            </option>
          ))}
        </select>
        <span className="text-sm text-neutral-500 dark:text-neutral-400">
          {t("showing", { count: visible.length, total: records.length })}
        </span>
      </div>

      <ul className="border-t border-line dark:border-line-dark">
        {visible.map((record) => (
          <li
            key={record.pair}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line py-3 dark:border-line-dark"
          >
            <div className="min-w-48 flex-1">
              <Link
                locale={locale}
                href={`/${record.pair}`}
                className="font-semibold text-accent hover:underline dark:text-accent-dark"
              >
                {languageName(record.source_lang)} &rarr; {languageName(record.target_lang)}
              </Link>
              <code className="block text-xs text-neutral-500 dark:text-neutral-400">
                {record.pair}
              </code>
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-neutral-500 dark:text-neutral-400">
              {record.metrics ? (
                <>
                  <span>{t("entries", { count: formatNumber(record.metrics.entries) })}</span>
                  <span>{t("forms", { count: formatNumber(record.metrics.inflected_forms) })}</span>
                  {sizeMb(record) ? <span>{sizeMb(record)} MB</span> : null}
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs tracking-wide text-accent uppercase dark:bg-accent-soft-dark dark:text-accent-dark">
                    {record.metrics.bundle_license}
                  </span>
                </>
              ) : null}
            </div>

            <div className="ml-auto">
              <a
                href={downloadUrl(record)}
                className="inline-block rounded-md bg-accent px-3 py-1.5 text-sm font-semibold whitespace-nowrap text-paper no-underline hover:opacity-90 dark:text-paper-dark"
              >
                {t("download")}
              </a>
            </div>
          </li>
        ))}
      </ul>

      {visible.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500 dark:text-neutral-400">{t("noMatches")}</p>
      ) : null}
    </section>
  );
}
