import Link from "next/link";
import "./globals.css";
import { defaultLocale } from "@/i18n/routing";
import englishMessages from "@/messages/en.json";

const t = englishMessages.notFound;

export default function NotFound() {
  return (
    <html lang="en" dir="ltr">
      <body className="min-h-screen bg-paper text-ink antialiased dark:bg-paper-dark dark:text-ink-dark">
        <main className="mx-auto w-full max-w-lg px-5 py-32 text-center">
          <p
            className="text-7xl font-bold text-accent-soft dark:text-accent-soft-dark"
            aria-hidden="true"
          >
            404
          </p>
          <h1 className="mt-4 text-2xl font-bold">{t.title}</h1>
          <p className="mt-3 text-neutral-500 dark:text-neutral-400">
            {t.body}
          </p>
          <p className="mt-6">
            <Link
              href={`/${defaultLocale}/`}
              className="inline-block rounded-md bg-accent px-4 py-2 font-semibold text-paper no-underline hover:opacity-90 dark:text-paper-dark"
            >
              {t.home}
            </Link>
          </p>
        </main>
      </body>
    </html>
  );
}
