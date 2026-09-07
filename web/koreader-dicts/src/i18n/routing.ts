// Interface locales, unrelated to a dictionary's language pair. To add one:
// add messages/<code>.json, then an entry in locales and localeInfo.

export const locales = ["en", "pt", "es", "fr", "it", "pl", "ru"] as const;

export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

export type LocaleInfo = {
  name: string;
  english: string;
  dir: "ltr" | "rtl";
  tag: string;
};

export const localeInfo: Record<Locale, LocaleInfo> = {
  en: { name: "English", english: "English", dir: "ltr", tag: "en" },
  pt: { name: "Português", english: "Portuguese", dir: "ltr", tag: "pt" },
  es: { name: "Español", english: "Spanish", dir: "ltr", tag: "es" },
  fr: { name: "Français", english: "French", dir: "ltr", tag: "fr" },
  it: { name: "Italiano", english: "Italian", dir: "ltr", tag: "it" },
  pl: { name: "Polski", english: "Polish", dir: "ltr", tag: "pl" },
  ru: { name: "Русский", english: "Russian", dir: "ltr", tag: "ru" },
};

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}
