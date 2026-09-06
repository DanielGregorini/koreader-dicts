// Verbatim from https://github.com/koreader/koreader/wiki/Dictionary-support
export const INSTALL_PATHS: { device: string; path: string }[] = [
  { device: "Kindle", path: "koreader/data/dict" },
  { device: "Kobo", path: ".adds/koreader/data/dict/" },
  { device: "Android", path: "/sdcard/koreader/data/dict" },
  { device: "PocketBook", path: "applications/koreader/data/dict" },
  { device: "Cervantes", path: "/mnt/private/koreader/data/dict" },
  { device: "Linux", path: "$HOME/.config/koreader/data/dict" },
  { device: "macOS", path: "$HOME/Library/Application Support/koreader/data/dict" },
];

export const DOCS = {
  dictionarySupport: "https://github.com/koreader/koreader/wiki/Dictionary-support",
  kindleInstall: "https://github.com/koreader/koreader/wiki/Installation-on-Kindle-devices",
  userGuide: "https://koreader.rocks/user_guide/",
  wordnet: "https://wordnet.princeton.edu/",
  omw: "https://github.com/omwn/omw-data",
  wiktionary: "https://www.wiktionary.org/",
  kaikki: "https://kaikki.org/",
  stardict: "https://github.com/huzheng001/stardict-3/blob/master/dict/doc/StarDictFileFormat",
};

// Files inside a dictionary package, in the order the page explains them.
export const PACKAGE_FILES = [
  { ext: ".ifo", key: "fileIfo" },
  { ext: ".idx", key: "fileIdx" },
  { ext: ".dict.dz", key: "fileDict" },
  { ext: ".syn", key: "fileSyn" },
  { ext: "LICENSE / ATTRIBUTION", key: "fileLicence" },
  { ext: "README.txt", key: "fileReadme" },
] as const;

// Measured on the 21.6 MB en-pt build; see tooling/kdicts/package.py.
export const COMPRESSION = [
  { method: "Stored", size: "21.6 MB", key: "formatStored" },
  { method: "ZIP (DEFLATE)", size: "15.1 MB", key: "formatDeflate", chosen: true },
  { method: "ZIP (bzip2)", size: "15.1 MB", key: "formatBzip2" },
  { method: "ZIP (LZMA)", size: "14.3 MB", key: "formatLzma" },
] as const;
