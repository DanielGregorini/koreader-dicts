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

// Real size of the published archive, in MB.
export function sizeMb(record: DictionaryRecord): number {
  return Math.round((record.archive_bytes / 1e6) * 10) / 10;
}

export const LANGUAGE_NAMES: Record<string, string> = {
  en: "English", pt: "Portuguese", es: "Spanish", fr: "French", de: "German",
  it: "Italian", ja: "Japanese", zh: "Chinese", id: "Indonesian", ar: "Arabic",
  ro: "Romanian", th: "Thai", nl: "Dutch", pl: "Polish", ms: "Malay",
  fi: "Finnish", sl: "Slovene", ca: "Catalan", eu: "Basque", hr: "Croatian",
  sk: "Slovak", el: "Greek",
};

export function languageName(code: string): string {
  return LANGUAGE_NAMES[code] ?? code;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}
