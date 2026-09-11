import { RELEASES_BASE } from "./repo";

export { RELEASES_BASE };

// Catalog types and pure helpers. Separate from lib/catalog.ts so Client
// Components can import them without pulling in node:fs.

export type CoveragePoint = {
  cutoff: number;
  sampled: number;
  headword_hits: number;
  form_hits: number;
  hits: number;
  percent: number;
};

export type SourceRecord = {
  id: string;
  kind: string;
  license: string;
  credit: string;
  url: string;
};

export type Metrics = {
  pair: string;
  source_lang: string;
  target_lang: string;
  generated_at: string;
  entries: number;
  senses: number;
  inflected_forms: number;
  entries_with_translation: number;
  entries_gloss_only: number;
  senses_with_translation: number;
  senses_gloss_only: number;
  entries_with_example: number;
  entries_with_pronunciation: number;
  entries_with_forms: number;
  mean_definition_chars: number;
  median_definition_chars: number;
  mean_translations_per_entry: number;
  mean_forms_per_entry: number;
  percent_entries_with_translation: number;
  percent_entries_with_example: number;
  percent_entries_with_forms: number;
  coverage: CoveragePoint[];
  frequency_list: string;
  licenses: string[];
  bundle_license: string;
  sources: SourceRecord[];
};

export type DictionaryRecord = {
  pair: string;
  name: string;
  source_lang: string;
  target_lang: string;
  tier: number;
  description: string;
  basename: string;
  built: boolean;
  // Size of the published .zip in bytes, measured at catalog time.
  archive_bytes: number;
  metrics?: Metrics;
};

export type Catalog = {
  generated_at: string;
  schema: number;
  dictionaries: DictionaryRecord[];
};

export function downloadUrl(record: DictionaryRecord): string {
  return `${RELEASES_BASE}/${record.basename}.zip`;
}

// A monolingual dictionary defines a language in itself. What a bilingual pair
// calls a translation is a synonym here, and the site has to say so.
export function isMonolingual(record: {
  source_lang: string;
  target_lang: string;
}): boolean {
  return record.source_lang === record.target_lang;
}

// Real size of the published archive, in MB.
export function sizeMb(record: DictionaryRecord): number {
  return Math.round((record.archive_bytes / 1e6) * 10) / 10;
}

// Fallback only. Intl.DisplayNames covers every code we ship and translates
// itself into the interface language; this is what is used if it throws.
export const LANGUAGE_NAMES: Record<string, string> = {
  en: "English", pt: "Portuguese", es: "Spanish", fr: "French", de: "German",
  it: "Italian", ja: "Japanese", zh: "Chinese", id: "Indonesian", ar: "Arabic",
  ro: "Romanian", th: "Thai", nl: "Dutch", pl: "Polish", ms: "Malay",
  fi: "Finnish", sl: "Slovene", ca: "Catalan", eu: "Basque", hr: "Croatian",
  sk: "Slovak", el: "Greek", ko: "Korean", cs: "Czech",
};

const displayNames = new Map<string, Intl.DisplayNames | null>();

function namesFor(locale: string): Intl.DisplayNames | null {
  if (!displayNames.has(locale)) {
    try {
      displayNames.set(locale, new Intl.DisplayNames([locale], { type: "language" }));
    } catch {
      displayNames.set(locale, null);
    }
  }
  return displayNames.get(locale) ?? null;
}

// Language names come from the platform rather than the message catalogues:
// they are the one string set that has to exist in seven interface languages
// for every code we might ever publish.
export function languageName(code: string, locale = "en"): string {
  const resolved = namesFor(locale)?.of(code);
  return resolved && resolved !== code ? resolved : (LANGUAGE_NAMES[code] ?? code);
}

export function formatNumber(value: number, locale = "en"): string {
  return value.toLocaleString(locale);
}
