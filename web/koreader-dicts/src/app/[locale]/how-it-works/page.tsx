import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Rich, raw } from "@/components/rich";
import { DOCS, INSTALL_PATHS } from "@/lib/install";
import { locales, type Locale } from "@/i18n/routing";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function HowItWorks({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <HowContent />;
}

function HowContent() {
  const t = useTranslations("how");

  return (
    <main>
      <h1 className="text-3xl leading-tight font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-neutral-500 dark:text-neutral-400">
        {t("lede")}
      </p>

      <h2 className="mt-12 text-xl font-bold">{t("pivotTitle")}</h2>
      <Rich className="mt-2" html={raw(t, "pivotBody")} />
      <pre className="mt-3 overflow-x-auto rounded-md bg-accent-soft p-4 font-mono text-xs dark:bg-accent-soft-dark">{`English   "wield"   ─┐
                       ├──▶  synset 01095899-v  ──┬──▶  "empunhar", "manejar"   Portuguese
Spanish   "empuñar"  ─┘                           └──▶  "impugnare"             Italian`}</pre>
      <Rich className="mt-2" html={raw(t, "pivotExample")} />
      <p className="mt-3">{t("pivotWhy")}</p>

      <h2 className="mt-12 text-xl font-bold">{t("layersTitle")}</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {[1, 2, 3].map((n) => (
          <section
            key={n}
            className="rounded-lg border border-line bg-card p-4 dark:border-line-dark dark:bg-card-dark"
          >
            <h3 className="font-semibold">
              {t(`layer${n}Title` as "layer1Title")}
            </h3>
            <Rich
              className="mt-3 text-sm text-neutral-500 dark:text-neutral-400"
              html={raw(t, `layer${n}Body`)}
            />
          </section>
        ))}
      </div>

      <h2 className="mt-12 text-xl font-bold">{t("inflectionTitle")}</h2>
      <Rich className="mt-2" html={raw(t, "inflectionBody")} />

      <h2 className="mt-12 text-xl font-bold">{t("honestTitle")}</h2>
      <p className="mt-2">{t("honestBody")}</p>

      <h2 className="mt-12 text-xl font-bold">{t("installTitle")}</h2>
      <p className="mt-2">{t("installIntro")}</p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="border-b border-line py-2 pr-4 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400">
                {t("installDevice")}
              </th>
              <th className="border-b border-line py-2 text-left text-xs font-semibold tracking-wide text-neutral-500 uppercase dark:border-line-dark dark:text-neutral-400">
                {t("installPath")}
              </th>
            </tr>
          </thead>
          <tbody>
            {INSTALL_PATHS.map((row) => (
              <tr
                key={row.device}
                className="border-b border-line dark:border-line-dark"
              >
                <td className="py-2 pr-4">{row.device}</td>
                <td className="py-2">
                  <code className="text-xs">{row.path}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4">{t("installResult")}</p>
      <pre className="mt-3 overflow-x-auto rounded-md bg-accent-soft p-4 font-mono text-xs dark:bg-accent-soft-dark">{`koreader/data/dict/en-pt-kdicts/en-pt-kdicts.ifo
koreader/data/dict/en-pt-kdicts/en-pt-kdicts.idx
koreader/data/dict/en-pt-kdicts/en-pt-kdicts.dict.dz
koreader/data/dict/en-pt-kdicts/en-pt-kdicts.syn`}</pre>
      <p className="mt-3">{t("installRestart")}</p>
      <Rich
        className="mt-3 text-sm text-neutral-500 dark:text-neutral-400"
        html={raw(t, "installOverride")}
      />
      <Rich
        className="mt-3 text-sm text-neutral-500 dark:text-neutral-400"
        html={raw(t, "installTest")}
      />
      <pre className="mt-3 overflow-x-auto rounded-md bg-accent-soft p-4 font-mono text-xs dark:bg-accent-soft-dark">{`sdcv -02 data/dict/ quaint`}</pre>

      <h2 className="mt-12 text-xl font-bold">{t("kindleTitle")}</h2>
      <Rich className="mt-2" html={raw(t, "kindleBody")} />
      <p className="mt-3 text-sm text-amber-700 dark:text-amber-500">
        {t("kindleWarning")}
      </p>

      <h2 className="mt-12 text-xl font-bold">{t("sourcesTitle")}</h2>
      <ul className="mt-3 list-disc space-y-1 pl-5">
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.dictionarySupport}
          >
            {t("sourceKoreaderDict")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.kindleInstall}
          >
            {t("sourceKoreaderKindle")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.userGuide}
          >
            {t("sourceKoreaderGuide")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.wordnet}
          >
            {t("sourceWordnet")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.omw}
          >
            {t("sourceOmw")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.wiktionary}
          >
            {t("sourceWiktionary")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.kaikki}
          >
            {t("sourceKaikki")}
          </a>
        </li>
        <li>
          <a
            className="text-accent hover:underline dark:text-accent-dark"
            href={DOCS.stardict}
          >
            {t("sourceStardict")}
          </a>
        </li>
      </ul>
    </main>
  );
}
