import fs from "node:fs";
import path from "node:path";
import type { Catalog, DictionaryRecord } from "./dictionaries";

// Reads the catalog written by `kdicts catalog`, at build time only.
// Server-only: it touches the filesystem. Client Components import types and
// helpers from ./dictionaries instead.

const CATALOG_PATH =
  process.env.KDICTS_CATALOG ?? path.join(process.cwd(), "..", "..", "dictionaries", "catalog.json");

export function loadCatalog(): Catalog {
  try {
    return JSON.parse(fs.readFileSync(CATALOG_PATH, "utf8")) as Catalog;
  } catch {
    // A clean checkout has no build output.
    return { generated_at: "", schema: 1, dictionaries: [] };
  }
}

export function builtDictionaries(catalog: Catalog): DictionaryRecord[] {
  return catalog.dictionaries.filter((d) => d.built && d.metrics);
}

export * from "./dictionaries";
