# 03 — UI/UX Rules

This is an analytical BA tool, not a marketing site. Every rule below optimizes for one
thing: a stakeholder or interviewer trusts the numbers on screen and can act on them without
being confused, distracted, or misled by false precision.

## 1. The one rule that overrides everything else

**Never show a single number where the underlying reality is a distribution or an estimate.**
Cycle time, ROI, NPV, simulation output — all of these are ranges or distributions in the
real data. A dashboard that shows "$45,000 saved annually" as if it's a fact, when it's
actually a modeled estimate with real uncertainty, is dishonest data presentation and
actively undermines the credibility this whole project is trying to build. Show ranges,
show distributions (histograms/box plots for cycle time), show confidence bands on
simulation output.

## 2. Visual identity

- No default shadcn/Tailwind "AI app" look (purple gradients, glassmorphism, generic hero
  sections). This is a professional analytics tool — closer in spirit to a Bloomberg
  terminal or a well-designed internal enterprise tool than a consumer SaaS landing page.
- Base palette: neutral grays/off-whites for structure, one accent color used sparingly and
  consistently for interactive/primary elements, and a small deliberate semantic palette for
  status (a muted red/amber/green for risk levels — not saturated traffic-light colors,
  which read as childish in a BA context).
- Typography: one serif or distinctive display font for headings/report titles (this is
  where the "executive document" feel comes from), a clean system/sans font for data and UI
  chrome. Do not use more than two font families total.
- Dense information is fine and expected — this is a tool for someone who wants the number,
  not a tool that needs to look "friendly." Favor tables, sparklines, and compact charts over
  large decorative visuals.

## 3. Layout patterns by module

- **Module A (Process Discovery)**: the mined process graph is the hero element of this
  screen — large, pannable/zoomable, with edge thickness encoding frequency. Variant
  frequency table sits alongside, not below, so a user can cross-reference "which variant is
  this edge part of" without scrolling.
- **Module B (Diagnosis)**: lead with the headline quantified findings as a short list of
  stat cards (e.g., "23% of cases deviate," "4.2 days added by rework") before any chart —
  the numbers are the point, charts support them.
- **Module C (Recommendations)**: present as a ranked list, not a grid — ranking order is
  itself information (it communicates priority) and a grid loses that signal.
- **Module D (Business case)**: the executive one-pager view must be genuinely printable/
  exportable and look correct as a standalone document, not just as a page in the app —
  test this by actually exporting it, don't assume the CSS "should" work.
- **Module E (Network)**: interactive force-directed graph, with a side panel that updates
  on node selection to show that resource's stats (volume handled, centrality score) — don't
  make the user cross-reference a separate table manually.
- **Module F (Simulation)**: baseline and scenario distributions shown as overlaid or
  side-by-side histograms, never as two separate single numbers — the whole point of this
  module is showing the shape of the change, not just "faster/slower."

## 4. States that must be explicitly designed, not left as an afterthought

- **Loading**: for any computation that takes more than ~1 second (mining, simulation runs),
  show real progress if the underlying process can report it, not an indefinite spinner.
- **Empty**: what does Module E look like on a log with no resource data? What does Module F
  look like before a scenario has been run? Design these, don't let them default to a blank
  white screen.
- **Error**: if ingestion fails on malformed data, the error must say what went wrong and how
  many rows were affected — not a generic "something went wrong."
- **Uncertainty**: as per rule 1 — every estimate needs a visual treatment that reads as
  "estimate," not "fact." A shaded confidence band, an explicit range in the label, or a
  small "modeled, not measured" tag are all acceptable; a bare number is not.

## 5. Accessibility baseline (non-negotiable, not a stretch goal)

- Color is never the only signal — risk levels/status need a text label or icon alongside
  the color, not color alone.
- All interactive elements keyboard-navigable.
- Sufficient contrast on the neutral palette — check this explicitly, don't eyeball it.

## 6. What NOT to build

- No onboarding tour, no marketing copy, no "features" landing page. This is a working tool,
  not a product being sold — time spent on that is time not spent on Modules E/F.
- No dark mode requirement unless it comes free from the component library — not worth
  dedicated build time on this timeline.
