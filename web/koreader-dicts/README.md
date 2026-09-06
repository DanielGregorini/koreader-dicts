# koreader-dicts website

Static Next.js site. It renders `dictionaries/catalog.json`, produced by
`kdicts catalog`, and links downloads to GitHub Releases.

```bash
cd web
npm install
npm run dev 
npm run build  
```

There is no server and no API route, by design:

- **No uploads, ever.** A server that accepts dictionary files is a piracy
  magnet with unbounded hosting cost and real legal exposure. The planned
  in-browser converter will run client-side in WASM, so files never leave the
  user's machine.

Point `KDICTS_CATALOG` at a different catalog file to preview another build.
