// Interface locales, unrelated to a dictionary's language pair. To add one:
// add messages/<code>.json, then an entry in locales and localeInfo.

export const locales = ["en"] as const;

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
};

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}
