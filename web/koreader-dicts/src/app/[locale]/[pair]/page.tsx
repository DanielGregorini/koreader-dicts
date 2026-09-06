import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import {
  CoverageTable,
  SourceTable,
  StatRow,
} from "@/components/metrics";
import { Link } from "@/components/link";
import {
  builtDictionaries,
  downloadUrl,
  formatNumber,
  languageName,
  loadCatalog,
  sizeMb,
  type DictionaryRecord,
} from "@/lib/catalog";
import { DOCS } from "@/lib/install";
import { locales, type Locale } from "@/i18n/routing";

export function generateStaticParams() {
  const built = builtDictionaries(loadCatalog());
  return locales.flatMap((locale) =>
    built.map((record) => ({ locale, pair: record.pair })),
  );
}

export default async function PairPage({
  params,
}: {
  params: Promise<{ locale: string; pair: string }>;
}) {
  const { locale, pair } = await params;
  setRequestLocale(locale);
  const record = builtDictionaries(loadCatalog()).find((d) => d.pair === pair);
  if (!record) notFound();
  return <PairContent locale={locale as Locale} record={record} />;
}

function PairContent({
  locale,
  record,
}: {
  locale: Locale;
  record: DictionaryRecord;
}) {
  const t = useTranslations("pair");
  const ti = useTranslations("inside");
  const metrics = record.metrics!;

  const rows: [string, string][] = [
    [
      ti("withTranslation"),
      `${formatNumber(metrics.entries_with_translation)} (${metrics.percent_entries_with_translation}%)`,
    ],
    [ti("glossOnly"), formatNumber(metrics.entries_gloss_only)],
    [
      ti("withExample"),
      `${formatNumber(metrics.entries_with_example)} (${metrics.percent_entries_with_example}%)`,
    ],
    [
      ti("withForms"),
      `${formatNumber(metrics.entries_with_forms)} (${metrics.percent_entries_with_forms}%)`,
    ],
    [ti("withPronunciation"), formatNumber(metrics.entries_with_pronunciation)],
    [ti("senses"), formatNumber(metrics.senses)],
    [
      ti("definitionLength"),
      ti("characters", { n: metrics.mean_definition_chars }),
    ],
    [ti("translationsPerEntry"), String(metrics.mean_translations_per_entry)],
  ];

  return (
    <main>
      <p>
        <Link
          locale={locale}
          href="/"
          className="text-sm text-accent hover:underline dark:text-accent-dark"
        >
          &larr; {t("back")}
        </Link>
      </p>
      <h1 className="mt-3 text-3xl leading-tight font-bold">
        {languageName(record.source_lang)} &rarr;{" "}
        {languageName(record.target_lang)}
      </h1>
      <p className="mt-3 max-w-2xl text-neutral-500 dark:text-neutral-400">
        {record.description}
      </p>

      <StatRow metrics={metrics} />

      <h2 className="mt-12 text-xl font-bold">{t("downloadTitle")}</h2>
      <div className="mt-4 rounded-lg border border-line bg-card p-5 dark:border-line-dark dark:bg-card-dark">
        <p>
          <a
            className="inline-block rounded-md bg-accent px-4 py-2 font-semibold text-paper no-underline hover:opacity-90 dark:text-paper-dark"
            href={downloadUrl(record)}
          >
            {record.basename}.zip
          </a>{" "}
          <span className="text-sm text-neutral-500 dark:text-neutral-400">
            {t("downloadSize", {
              size: sizeMb(record),
              licence: metrics.bundle_license,
            })}
          </span>
        </p>
        <h3 className="mt-5 font-semibold">{t("installTitle")}</h3>
        <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          {t("installBody")}
        </p>
        <pre className="mt-2 overflow-x-auto rounded-md bg-accent-soft p-3 font-mono text-xs dark:bg-accent-soft-dark">{`koreader/data/dict/${record.basename}/${record.basename}.ifo`}</pre>
        <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          {t("installAfter")}
        </p>
        <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          <Link
            locale={locale}
            href="/how-it-works"
            className="text-accent hover:underline dark:text-accent-dark"
          >
            {t("installLink")}
          </Link>{" "}
          &middot;{" "}
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.dictionarySupport}
          >
            KOReader wiki
          </a>
        </p>
      </div>

      <h2 className="mt-12 text-xl font-bold">{t("coverageTitle")}</h2>
      <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
        {t("coverageBody")}
      </p>
      <CoverageTable metrics={metrics} />

      <h2 className="mt-12 text-xl font-bold">{t("insideTitle")}</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <tbody>
            {rows.map(([label, value]) => (
              <tr
                key={label}
                className="border-b border-line dark:border-line-dark"
              >
                <td className="py-2 pr-3">{label}</td>
                <td className="py-2 text-right tabular-nums">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
        {t("insideNote")}
      </p>

      <h2 className="mt-12 text-xl font-bold">{t("sourcesTitle")}</h2>
      <SourceTable metrics={metrics} />
    </main>
  );
}
