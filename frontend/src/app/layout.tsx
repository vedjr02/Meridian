import type { Metadata } from "next";
import { IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

// Serif for headings and report titles gives the "executive document" register; a neutral sans
// with tabular figures carries data and UI chrome. Two families total, per 03-UIUX-RULES.md.
const serif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  display: "swap",
});

const sans = IBM_Plex_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Meridian",
  description: "Process mining, diagnosis and business-case analytics over real event logs.",
};

// Order matches the analysis flow: each module builds on the outputs of the ones above it. Only
// built modules get a link, so the navigation never leads to an empty page.
const MODULES: { key: string; label: string; href?: string }[] = [
  { key: "A", label: "Process Discovery", href: "/discovery" },
  { key: "B", label: "Conformance & Diagnosis" },
  { key: "C", label: "Automation Scoring" },
  { key: "D", label: "Business Case & ROI" },
  { key: "E", label: "Organizational Network" },
  { key: "F", label: "What-If Simulation" },
];

/**
 * Root layout: the persistent shell (top bar, module sidebar, content area) every module screen
 * renders inside. Why a fixed shell: users cross-reference modules constantly, so navigation and
 * context should never move when switching between them.
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>
        <div className="shell">
          <header className="topbar">
            <span className="wordmark">Meridian</span>
            <span className="wordmark-subtitle">Process analytics</span>
          </header>
          <nav className="sidebar" aria-label="Analysis modules">
            <h2 className="sidebar-heading">Modules</h2>
            <ol className="module-list">
              {MODULES.map((module) => (
                <li key={module.key}>
                  <span className="module-key">{module.key}</span>
                  {module.href ? <Link href={module.href}>{module.label}</Link> : module.label}
                </li>
              ))}
            </ol>
          </nav>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
