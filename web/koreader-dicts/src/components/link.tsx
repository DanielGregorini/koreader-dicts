import NextLink from "next/link";
import type { ComponentProps } from "react";
import type { Locale } from "@/i18n/routing";

type Props = Omit<ComponentProps<typeof NextLink>, "href"> & {
  locale: Locale;
  // Path without the locale prefix, e.g. "/" or "/how-it-works".
  href: string;
};

// Adds the /<locale>/ prefix and the trailing slash that trailingSlash needs.
export function Link({ locale, href, ...props }: Props) {
  const path = href === "/" ? `/${locale}/` : `/${locale}${href}/`;
  return <NextLink href={path} {...props} />;
}
