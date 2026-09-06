// Messages rendered by <Rich> contain HTML tags. next-intl parses those as ICU
// rich-text tags and throws FORMATTING_ERROR, so read them with t.raw and
// substitute placeholders here. Use this, not t(), for any <Rich> message.
export function raw(
  t: { raw: (key: string) => unknown },
  key: string,
  values: Record<string, string | number> = {},
): string {
  const message = String(t.raw(key));
  return Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    message,
  );
}

// Renders a message containing inline markup. The HTML is trusted: it comes
// from messages/*.json, never from user input.
export function Rich({
  html,
  as = "p",
  className,
}: {
  html: string;
  as?: "p" | "dd" | "span" | "li";
  className?: string;
}) {
  const Tag = as;
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
