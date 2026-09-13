import StateMessage from "@/components/StateMessage";

/**
 * Shown while the page fetches its data. The results are precomputed by the backend, so there is
 * no long-running computation to report progress on; the message says what is being fetched.
 */
export default function Loading() {
  return (
    <StateMessage tone="loading" title="Loading process discovery results">
      <p>
        Fetching the mined process model, variants and cycle-time distribution from the Meridian
        API.
      </p>
    </StateMessage>
  );
}
