import { useTranslations } from "next-intl";
import { Link } from "@/components/link";
import { DOCS } from "@/lib/install";
import { ISSUES_URL, REPO_URL } from "@/lib/repo";
import type { Locale } from "@/i18n/routing";

const LINK = "text-accent hover:underline dark:text-accent-dark";

export function Footer({ locale }: { locale: Locale }) {
  const t = useTranslations("footer");

  return (
    <footer className="border-t border-line dark:border-line-dark">
      <div className="mx-auto w-full max-w-4xl px-5 py-8 text-sm text-neutral-500 dark:text-neutral-400">
        <div className="grid gap-6 sm:grid-cols-3">
          <div>
            <strong className="text-ink dark:text-ink-dark">koreader-dicts</strong>
            <p className="mt-1">{t("tagline")}</p>
            <p className="mt-2">
              {t("hosted")}{" "}
              <a className={LINK} href={REPO_URL}>
                {REPO_URL.replace("https://", "")}
              </a>
            </p>
          </div>

          <nav aria-label={t("linksLabel")}>
            <ul className="space-y-1">
              <li>
                <Link locale={locale} href="/" className={LINK}>
                  {t("dictionaries")}
                </Link>
              </li>
              <li>
                <Link locale={locale} href="/downloads" className={LINK}>
                  {t("downloads")}
                </Link>
              </li>
              <li>
                <Link locale={locale} href="/how-it-works" className={LINK}>
                  {t("howItWorks")}
                </Link>
              </li>
            </ul>
          </nav>

          <ul className="space-y-1">
            <li>
              <a className={LINK} href={REPO_URL}>
                {t("sourceCode")}
              </a>
            </li>
            <li>
              <a className={LINK} href={ISSUES_URL}>
                {t("issues")}
              </a>
            </li>
            <li>
              <a className={LINK} href={DOCS.dictionarySupport}>
                {t("koreaderDocs")}
              </a>
            </li>
            <li>
              <a className={LINK} href={DOCS.omw}>
                {t("omw")}
              </a>
            </li>
            <li>
              <a className={LINK} href={DOCS.wordnet}>
                {t("wordnet")}
              </a>
            </li>
          </ul>
        </div>

        <p className="mt-8">{t("licence")}</p>
        <p className="mt-2 font-semibold">{t("notAffiliated")}</p>
      </div>
    </footer>
  );
}
