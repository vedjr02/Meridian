import type { Metadata } from "next";

import DiscoveryView from "@/components/discovery/DiscoveryView";
import StateMessage from "@/components/StateMessage";
import { apiUrl, loadDiscovery } from "@/lib/discovery";

export const metadata: Metadata = {
  title: "Process Discovery · Meridian",
};

/**
 * Module A screen. Data is loaded on the server at request time; the three outcomes (results, not
 * yet computed, API unreachable) each get their own designed state, and errors say what failed.
 */
export default async function DiscoveryPage() {
  const result = await loadDiscovery();

  if (result.status === "missing") {
    return (
      <StateMessage tone="empty" title="No process discovery results yet">
        <p>{result.message}</p>
        <p>
          From the repository root, run <code>.venv/bin/python -m meridian.discovery</code>. It
          ingests the raw event log if needed, then writes the process map, mined model, variant
          table and cycle-time summary this page displays.
        </p>
        <p>Missing: {result.missing.join(", ")}</p>
      </StateMessage>
    );
  }

  if (result.status === "error") {
    return (
      <StateMessage tone="error" title="Could not load process discovery results">
        <p>
          The Meridian API at <code>{apiUrl}</code> did not respond as expected: {result.message}.
        </p>
        <p>
          Start it from the repository root with{" "}
          <code>.venv/bin/uvicorn meridian.api.main:app</code>, or point <code>MERIDIAN_API_URL</code>{" "}
          at a running instance, then reload this page.
        </p>
      </StateMessage>
    );
  }

  return <DiscoveryView data={result.data} />;
}
