import type { ReactNode } from "react";

type StateMessageProps = {
  tone: "loading" | "empty" | "error";
  title: string;
  children: ReactNode;
};

const TAGS = { loading: "Loading", empty: "No results yet", error: "Error" } as const;

/**
 * Shared frame for loading, empty and error states (03-UIUX-RULES.md §4). Errors are announced
 * as alerts; loading and empty states as polite status updates, so screen readers hear both.
 */
export default function StateMessage({ tone, title, children }: StateMessageProps) {
  return (
    <section
      className={`state-message${tone === "error" ? " state-message--error" : ""}`}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
    >
      <p className="state-message__tag">{TAGS[tone]}</p>
      <h1>{title}</h1>
      {children}
    </section>
  );
}
