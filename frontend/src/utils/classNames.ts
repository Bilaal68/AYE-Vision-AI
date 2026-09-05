export function classNames(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(" ");
}
