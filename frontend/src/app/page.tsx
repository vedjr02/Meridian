/**
 * Home view. Until ingestion and process discovery produce outputs there is nothing to show, so
 * this renders a designed empty state rather than a blank screen (03-UIUX-RULES.md section 4).
 */
export default function Home() {
  return (
    <section className="empty-state" aria-labelledby="empty-state-title">
      <h1 id="empty-state-title">No analysis yet</h1>
      <p>Process discovery results appear here once the event log has been ingested and mined.</p>
    </section>
  );
}
