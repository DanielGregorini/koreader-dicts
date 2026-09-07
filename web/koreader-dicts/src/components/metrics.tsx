import { useLocale, useTranslations } from "next-intl";
import { Rich, raw } from "@/components/rich";
import type { Metrics } from "@/lib/dictionaries";
import { formatNumber, isMonolingual } from "@/lib/dictionaries";

export function StatRow({ metrics }: { metrics: Metrics }) {
  const t = useTranslations("stats");
  const locale = useLocale();
  return (
    <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
      <Stat value={formatNumber(metrics.entries, locale)} label={t("entries")} />
      <Stat value={formatNumber(metrics.inflected_forms, locale)} label={t("forms")} />
      <Stat
        value={`${metrics.percent_entries_with_translation}%`}
        label={t(isMonolingual(metrics) ? "withSynonym" : "withTranslation")}
      />
      <Stat
        value={metrics.coverage.length ? `${topCoverage(metrics)}%` : "—"}
        label={t("coverage10k")}
      />
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="min-w-24">
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-neutral-500 dark:text-neutral-400">{label}</div>
    </div>
  );
}

export function topCoverage(metrics: Metrics, cutoff = 10000): number | string {
  return metrics.coverage.find((c) => c.cutoff === cutoff)?.percent ?? "—";
}

// Coverage against a frequency list, counting inflected forms.
export function CoverageTable({ metrics }: { metrics: Metrics }) {
  const t = useTranslations("coverage");
  const locale = useLocale();
  if (!metrics.coverage.length) {
    return <p className="mt-3 text-sm text-neutral-500 dark:text-neutral-400">{t("none")}</p>;
  }
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="border-b border-line py-2 pr-3 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400">{t("band")}</th>
            <th className="border-b border-line py-2 pr-3 text-right text-xs font-semibold tracking-wide text-neutral-500 uppercase tabular-nums dark:border-line-dark dark:text-neutral-400">{t("found")}</th>
            <th className="border-b border-line py-2 pr-3 text-right text-xs font-semibold tracking-wide text-neutral-500 uppercase tabular-nums dark:border-line-dark dark:text-neutral-400">{t("asHeadword")}</th>
            <th className="border-b border-line py-2 pr-3 text-right text-xs font-semibold tracking-wide text-neutral-500 uppercase tabular-nums dark:border-line-dark dark:text-neutral-400">{t("viaInflection")}</th>
            <th className="border-b border-line py-2 pr-3 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400 w-[30%]">{t("coverage")}</th>
          </tr>
        </thead>
        <tbody>
          {metrics.coverage.map((point) => (
            <tr key={point.cutoff} className="border-b border-line dark:border-line-dark">
              <td className="py-2 pr-3">{t("top", { n: formatNumber(point.cutoff, locale) })}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{formatNumber(point.hits, locale)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{formatNumber(point.headword_hits, locale)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{formatNumber(point.form_hits, locale)}</td>
              <td className="py-2 pr-3">
                <div
                  className="h-2 rounded-sm bg-accent-soft dark:bg-accent-soft-dark"
                  title={`${point.percent}%`}
                >
                  <span
                    className="block h-full rounded-sm bg-accent dark:bg-accent-dark"
                    style={{ width: `${point.percent}%` }}
                  />
                </div>
                <span className="text-xs text-neutral-500 dark:text-neutral-400">
                  {point.percent}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {metrics.frequency_list ? (
        <p className="mt-3 text-sm text-neutral-500 dark:text-neutral-400">{t("measuredAgainst", { list: metrics.frequency_list })}</p>
      ) : null}
    </div>
  );
}

export function SourceTable({ metrics }: { metrics: Metrics }) {
  const t = useTranslations("sources");
  const bundled = raw(t, "bundled", { licence: metrics.bundle_license });
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="border-b border-line py-2 pr-3 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400">{t("source")}</th>
            <th className="border-b border-line py-2 pr-3 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400">{t("licence")}</th>
            <th className="border-b border-line py-2 pr-3 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400">{t("credit")}</th>
          </tr>
        </thead>
        <tbody>
          {metrics.sources.map((source) => (
            <tr key={source.id} className="border-b border-line dark:border-line-dark">
              <td className="py-2 pr-3">
                <code>{source.id}</code>
              </td>
              <td className="py-2 pr-3">{source.license}</td>
              <td className="py-2 pr-3 text-neutral-500 dark:text-neutral-400">{source.credit}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Rich
        className="mt-3 text-sm text-neutral-500 dark:text-neutral-400"
        html={bundled}
      />
    </div>
  );
}
