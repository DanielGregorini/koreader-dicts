import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { DictionaryList } from "@/components/dictionary-list";
import { Rich, raw } from "@/components/rich";
import { loadCatalog } from "@/lib/catalog";
import { formatNumber } from "@/lib/dictionaries";
import { locales, type Locale } from "@/i18n/routing";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function Home({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <HomeContent locale={locale as Locale} />;
}

function HomeContent({ locale }: { locale: Locale }) {
  const t = useTranslations("home");
  const catalog = loadCatalog();
  const built = catalog.dictionaries.filter((d) => d.built);

  return (
    <>
      <h1 className="text-3xl leading-tight font-bold">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-neutral-500 dark:text-neutral-400">
        {t("lede")}
      </p>

      {built.length === 0 ? (
        <Rich
          className="mt-6 text-sm text-amber-700 dark:text-amber-500"
          html={raw(t, "noBuilds")}
        />
      ) : (
        <div className="mt-8">
          <p className="mb-3 text-sm text-neutral-500 dark:text-neutral-400">
            {t("listIntro")}
          </p>
          <DictionaryList locale={locale} records={built} />
        </div>
      )}

      <h2 className="mt-12 text-xl font-bold">{t("howTitle")}</h2>
      <p className="mt-2">{t("howBody")}</p>
      <pre className="mt-3 overflow-x-auto rounded-md bg-accent-soft p-4 font-mono text-xs dark:bg-accent-soft-dark">
        {`wield  --(WordNet)-->  01095899-v  --(OpenWN-PT)-->  empunhar, manejar`}
      </pre>
      <p className="mt-3">{t("howAfter")}</p>

      <h2 className="mt-12 text-xl font-bold">{t("whyTitle")}</h2>
      <Rich className="mt-2" html={raw(t, "whyBody")} />

      {catalog.generated_at ? (
        <p className="mt-10 text-sm text-neutral-500 dark:text-neutral-400">
          {t("catalogGenerated", {
            date: catalog.generated_at.slice(0, 10),
            count: formatNumber(built.length),
          })}
        </p>
      ) : null}
    </>
  );
}
