import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { DictionaryList } from "@/components/dictionary-list";
import { Rich, raw } from "@/components/rich";
import { builtDictionaries, loadCatalog } from "@/lib/catalog";
import { RELEASES_URL } from "@/lib/repo";
import { COMPRESSION, PACKAGE_FILES } from "@/lib/install";
import { locales, type Locale } from "@/i18n/routing";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function Downloads({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <DownloadsContent locale={locale as Locale} />;
}

function DownloadsContent({ locale }: { locale: Locale }) {
  const t = useTranslations("downloads");

  return (
    <>
      <h1 className="text-3xl leading-tight font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-neutral-500 dark:text-neutral-400">
        {t("lede")}
      </p>

      <div className="mt-8">
        <p className="mb-3 text-sm text-neutral-500 dark:text-neutral-400">
          {t("listIntro")}
        </p>
        <DictionaryList locale={locale} records={builtDictionaries(loadCatalog())} />
        <p className="mt-4 text-sm text-neutral-500 dark:text-neutral-400">
          <a className="text-accent hover:underline dark:text-accent-dark" href={RELEASES_URL}>
            {t("allReleases")}
          </a>
        </p>
      </div>

      <h2 className="mt-12 text-xl font-bold">{t("whatYouGetTitle")}</h2>
      <p className="mt-2">{t("whatYouGetBody")}</p>
      <dl className="mt-4">
        {PACKAGE_FILES.map((file) => (
          <div
            key={file.ext}
            className="grid gap-1 border-b border-line py-2.5 sm:grid-cols-[10rem_1fr] sm:gap-5 dark:border-line-dark"
          >
            <dt className="font-semibold">
              <code>{file.ext}</code>
            </dt>
            <Rich
              as="dd"
              className="m-0 text-sm text-neutral-500 dark:text-neutral-400"
              html={raw(t, file.key)}
            />
          </div>
        ))}
      </dl>

      <h2 className="mt-12 text-xl font-bold">{t("formatTitle")}</h2>
      <p className="mt-2">{t("formatBody")}</p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line dark:border-line-dark">
              <th className="py-2 pr-3 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:text-neutral-400">
                {t("formatMethod")}
              </th>
              <th className="py-2 pr-3 text-right text-xs font-semibold tracking-wide text-neutral-500 uppercase tabular-nums dark:text-neutral-400">
                {t("formatSize")}
              </th>
              <th className="py-2 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:text-neutral-400">
                {t("formatNote")}
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPRESSION.map((row) => (
              <tr
                key={row.method}
                className="border-b border-line dark:border-line-dark"
              >
                <td className="py-2 pr-3">
                  {"chosen" in row && row.chosen ? (
                    <strong>{row.method}</strong>
                  ) : (
                    row.method
                  )}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {row.size}
                </td>
                <td className="py-2 text-neutral-500 dark:text-neutral-400">
                  {t(row.key)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4">{t("formatConclusion")}</p>
      <p className="mt-3 text-sm text-neutral-500 dark:text-neutral-400">
        {t("checksumNote")}
      </p>
    </>
  );
}
