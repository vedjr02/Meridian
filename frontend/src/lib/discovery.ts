import { connection } from "next/server";

// Server-side only: pages fetch from the FastAPI backend at request time, so the browser never
// needs cross-origin access to it. Configure with MERIDIAN_API_URL; the default matches
// `uvicorn meridian.api.main:app` run locally.
const API_URL = process.env.MERIDIAN_API_URL ?? "http://127.0.0.1:8000";

export type DistributionSeconds = {
  count: number;
  mean: number;
  min: number;
  p50: number;
  p90: number;
  p99: number;
  max: number;
};

export type Overview = {
  dataset: string;
  lifecycle_kept: string;
  case_count: number;
  event_count: number;
  activity_count: number;
  variant_count: number;
  coverage_share: number;
  variants_to_cover: number;
  top_variant_share: number;
  open_case_count: number;
  cycle_time_seconds: {
    all_cases: DistributionSeconds;
    most_common_variant: DistributionSeconds;
    other_variants: DistributionSeconds | null;
  };
};

export type EdgeKind = "causal" | "length_one_loop" | "length_two_loop" | "best_connection";

export type ProcessMapNode = {
  id: string;
  count: number;
  start_count: number;
  end_count: number;
  layer: number;
  order: number;
  x: number;
  y: number;
};

export type ProcessMapEdge = {
  source: string;
  target: string;
  kind: EdgeKind;
  dependency: number;
  frequency: number;
  case_frequency: number | null;
  median_duration_seconds: number | null;
};

export type ProcessMap = {
  threshold: number;
  case_count: number;
  nodes: ProcessMapNode[];
  edges: ProcessMapEdge[];
};

export type Variant = {
  rank: number;
  activities: string[];
  case_count: number;
  case_share: number;
  cumulative_share: number;
  outcomes: Record<string, number>;
};

export type VariantList = {
  case_count: number;
  variant_count: number;
  variants: Variant[];
};

export type HistogramBin = {
  start: number;
  end: number;
  all_cases: number;
  most_common_variant: number;
};

export type Histogram = {
  unit: "days";
  case_count: number;
  bin_width: number;
  bins: HistogramBin[];
  overflow: { start: number; all_cases: number; most_common_variant: number };
  percentiles: { p50: number; p90: number; p99: number };
};

export type DiscoveryData = {
  overview: Overview;
  processMap: ProcessMap;
  variants: VariantList;
  histogram: Histogram;
};

export type DiscoveryLoadResult =
  | { status: "ok"; data: DiscoveryData }
  | { status: "missing"; message: string; missing: string[] }
  | { status: "error"; message: string };

/** Raised when the API reports that discovery outputs do not exist yet (an expected state). */
class MissingOutputsError extends Error {
  readonly missing: string[];

  constructor(message: string, missing: string[]) {
    super(message);
    this.missing = missing;
  }
}

/**
 * Fetch one API resource. The backend signals "not computed yet" with a structured 404, which is
 * turned into its own error type so the page can show an empty state instead of an error.
 */
async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (response.status === 404) {
    const body = await response.json().catch(() => null);
    if (body?.detail?.code === "discovery_outputs_missing") {
      throw new MissingOutputsError(body.detail.message, body.detail.missing ?? []);
    }
  }
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Describe a failed fetch specifically: "connection refused" is actionable, "fetch failed" is not. */
function describeFailure(error: unknown): string {
  if (!(error instanceof Error)) return String(error);
  const cause = (error as Error & { cause?: { code?: string } }).cause;
  return cause?.code ? `${error.message} (${cause.code})` : error.message;
}

/**
 * Load everything the process discovery screen shows, in parallel, at request time.
 *
 * Why `connection()` first: without it, Next.js would run these fetches during `next build` and
 * bake whatever the API returned then into a static page, or fail the build if the API is down.
 */
export async function loadDiscovery(): Promise<DiscoveryLoadResult> {
  await connection();
  try {
    const [overview, processMap, variants, histogram] = await Promise.all([
      getJson<Overview>("/api/discovery/overview"),
      getJson<ProcessMap>("/api/discovery/process-map"),
      getJson<VariantList>("/api/discovery/variants?limit=25"),
      getJson<Histogram>("/api/discovery/cycle-time/histogram"),
    ]);
    return { status: "ok", data: { overview, processMap, variants, histogram } };
  } catch (error) {
    if (error instanceof MissingOutputsError) {
      return { status: "missing", message: error.message, missing: error.missing };
    }
    return { status: "error", message: describeFailure(error) };
  }
}

export const apiUrl = API_URL;
