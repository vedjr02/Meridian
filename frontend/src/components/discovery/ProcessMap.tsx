"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { formatCount, formatMeasure, formatShortDuration } from "@/lib/format";
import type { EdgeKind, ProcessMap as ProcessMapData, ProcessMapEdge } from "@/lib/discovery";

import styles from "./discovery.module.css";

// Matches the backend layout spacing (210 between stages, 64 between rows).
const NODE_WIDTH = 164;
const NODE_HEIGHT = 42;
const PADDING = 28;
const LOOP_HEADROOM = 60;
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 4;
const PAN_STEP = 60;

type View = { x: number; y: number; k: number };
const IDENTITY: View = { x: 0, y: 0, k: 1 };

const KIND_LABELS: Record<EdgeKind, string> = {
  causal: "causal",
  length_one_loop: "repeats itself",
  length_two_loop: "two-activity loop",
  best_connection: "kept for connectivity",
};

type ProcessMapProps = {
  map: ProcessMapData;
  /** Activity sequence of the selected variant; its transitions are highlighted. */
  highlight: string[] | null;
};

/** Collision-proof key for an ordered activity pair; activity names may contain any character. */
function pairKey(source: string, target: string): string {
  return JSON.stringify([source, target]);
}

/** Map a transition frequency to a line width, square-root scaled as in the Mermaid export. */
function strokeWidth(frequency: number, maxFrequency: number): number {
  return 1 + 7 * Math.sqrt(frequency / Math.max(maxFrequency, 1));
}

/**
 * SVG path for an edge. Forward edges run from the right side of the source to the left side of
 * the target; edges pointing back (rework) arc above the nodes so they never hide forward flow;
 * self-loops are small loops on top of the node.
 */
function edgePath(
  source: { x: number; y: number; layer: number },
  target: { x: number; y: number; layer: number },
  isSelfLoop: boolean,
): string {
  const halfW = NODE_WIDTH / 2;
  const halfH = NODE_HEIGHT / 2;
  if (isSelfLoop) {
    const top = source.y - halfH;
    return `M ${source.x - 20} ${top} C ${source.x - 34} ${top - 34}, ${source.x + 34} ${top - 34}, ${source.x + 20} ${top}`;
  }
  if (target.layer > source.layer) {
    const x1 = source.x + halfW;
    const x2 = target.x - halfW;
    const bend = (x2 - x1) / 2;
    return `M ${x1} ${source.y} C ${x1 + bend} ${source.y}, ${x2 - bend} ${target.y}, ${x2} ${target.y}`;
  }
  const lift = 44 + 18 * Math.abs(source.layer - target.layer);
  const y1 = source.y - halfH;
  const y2 = target.y - halfH;
  const peak = Math.min(y1, y2) - lift;
  return `M ${source.x} ${y1} C ${source.x} ${peak}, ${target.x} ${peak}, ${target.x} ${y2}`;
}

type Bounds = { minX: number; minY: number; width: number; height: number };

/**
 * Initial view: zoomed so the map fills the canvas height, anchored at the left where the process
 * starts. Why not "fit everything": the mined model is far wider than tall, so fitting its width
 * leaves most of the canvas empty and shrinks labels to about 6 px, which nobody can read. Filling
 * the height keeps labels legible; "Whole map" is one click away for the overview.
 */
function readableView(svg: SVGSVGElement, bounds: Bounds): View {
  const { width, height } = svg.getBoundingClientRect();
  if (width === 0 || height === 0) return IDENTITY;
  const fit = Math.min(width / bounds.width, height / bounds.height);
  const k = Math.min(MAX_ZOOM, Math.max(1, height / (bounds.height * fit)));
  const centreY = bounds.minY + bounds.height / 2;
  return { k, x: bounds.minX * (1 - k), y: centreY * (1 - k) };
}

/** Zoom by `factor` keeping the SVG point (px, py) fixed on screen, within the zoom limits. */
function zoomAt(current: View, factor: number, px: number, py: number): View {
  const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current.k * factor));
  const ratio = k / current.k;
  return { k, x: px - (px - current.x) * ratio, y: py - (py - current.y) * ratio };
}

/** Describe an edge for its tooltip: frequency, cases, typical duration, and why it is in the model. */
function edgeTitle(edge: ProcessMapEdge): string {
  const parts = [
    `${edge.source} → ${edge.target}`,
    `${formatCount(edge.frequency)} transitions`,
    edge.case_frequency !== null ? `in ${formatCount(edge.case_frequency)} cases` : null,
    edge.median_duration_seconds !== null
      ? `median ${formatShortDuration(edge.median_duration_seconds)}`
      : null,
    `${KIND_LABELS[edge.kind]}, measure ${formatMeasure(edge.dependency)}`,
  ];
  return parts.filter(Boolean).join(" · ");
}

/**
 * The mined process model as a pannable, zoomable map (03-UIUX-RULES.md §3, Module A). Line width
 * encodes frequency; line style encodes why the miner kept the edge. Selecting a variant in the
 * table highlights its path, and the map reports any transitions the model does not contain.
 */
export default function ProcessMap({ map, highlight }: ProcessMapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ pointerX: number; pointerY: number; view: View } | null>(null);
  // Once the user pans or zooms, resizing the window must not snap the map back.
  const userMovedRef = useRef(false);
  const [view, setView] = useState<View>(IDENTITY);

  const nodesById = useMemo(() => new Map(map.nodes.map((node) => [node.id, node])), [map.nodes]);
  const maxFrequency = useMemo(
    () => Math.max(1, ...map.edges.map((edge) => edge.frequency)),
    [map.edges],
  );
  const bounds = useMemo<Bounds>(() => {
    const xs = map.nodes.map((node) => node.x);
    const ys = map.nodes.map((node) => node.y);
    const minX = Math.min(...xs) - NODE_WIDTH / 2 - PADDING;
    const minY = Math.min(...ys) - NODE_HEIGHT / 2 - PADDING - LOOP_HEADROOM;
    const maxX = Math.max(...xs) + NODE_WIDTH / 2 + PADDING;
    const maxY = Math.max(...ys) + NODE_HEIGHT / 2 + PADDING;
    return { minX, minY, width: maxX - minX, height: maxY - minY };
  }, [map.nodes]);

  // Apply the readable initial view once the canvas has a size, and again on resize until the
  // user takes over.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(() => {
      if (!userMovedRef.current) setView(readableView(svg, bounds));
    });
    observer.observe(svg);
    return () => observer.disconnect();
  }, [bounds]);

  const highlighted = useMemo(() => {
    if (!highlight) return null;
    const pairs = new Set<string>();
    for (let i = 0; i + 1 < highlight.length; i += 1) {
      pairs.add(pairKey(highlight[i], highlight[i + 1]));
    }
    const modelPairs = new Set(map.edges.map((edge) => pairKey(edge.source, edge.target)));
    const missing = [...pairs].filter((pair) => !modelPairs.has(pair)).length;
    return { pairs, activities: new Set(highlight), missing, total: pairs.size };
  }, [highlight, map.edges]);

  /** Convert a pointer position to the SVG's own coordinate system. */
  function toSvgPoint(clientX: number, clientY: number): { x: number; y: number } {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return { x: 0, y: 0 };
    const point = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  }

  // Wheel zoom needs a non-passive listener so the page does not scroll while zooming the map.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      userMovedRef.current = true;
      const matrix = svg.getScreenCTM();
      if (!matrix) return;
      const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
      const factor = Math.exp(-event.deltaY * 0.0015);
      setView((current) => zoomAt(current, factor, point.x, point.y));
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, []);

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    userMovedRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = toSvgPoint(event.clientX, event.clientY);
    dragRef.current = { pointerX: point.x, pointerY: point.y, view };
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const point = toSvgPoint(event.clientX, event.clientY);
    setView({
      ...drag.view,
      x: drag.view.x + point.x - drag.pointerX,
      y: drag.view.y + point.y - drag.pointerY,
    });
  }

  function onPointerUp() {
    dragRef.current = null;
  }

  const centreX = bounds.minX + bounds.width / 2;
  const centreY = bounds.minY + bounds.height / 2;

  /** Apply a view chosen by the user, which stops automatic resizing from overriding it. */
  function userView(next: View | ((current: View) => View)) {
    userMovedRef.current = true;
    setView(next);
  }

  function showReadable() {
    if (svgRef.current) userView(readableView(svgRef.current, bounds));
  }

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [PAN_STEP, 0],
      ArrowRight: [-PAN_STEP, 0],
      ArrowUp: [0, PAN_STEP],
      ArrowDown: [0, -PAN_STEP],
    };
    if (event.key in moves) {
      const [dx, dy] = moves[event.key];
      userView((current) => ({ ...current, x: current.x + dx, y: current.y + dy }));
    } else if (event.key === "+" || event.key === "=") {
      userView((current) => zoomAt(current, 1.25, centreX, centreY));
    } else if (event.key === "-") {
      userView((current) => zoomAt(current, 0.8, centreX, centreY));
    } else if (event.key === "0") {
      userView(IDENTITY);
    } else {
      return;
    }
    event.preventDefault();
  }

  return (
    <div className={styles.mapFrame}>
      <div className={styles.mapToolbar}>
        <div className={styles.mapButtons}>
          <button type="button" onClick={() => userView((v) => zoomAt(v, 1.25, centreX, centreY))}>
            Zoom in
          </button>
          <button type="button" onClick={() => userView((v) => zoomAt(v, 0.8, centreX, centreY))}>
            Zoom out
          </button>
          <button type="button" onClick={() => userView(IDENTITY)}>
            Whole map
          </button>
          <button type="button" onClick={showReadable}>
            Readable size
          </button>
          <span className={styles.mapHint}>Drag to pan, scroll to zoom</span>
        </div>
        <ul className={styles.legend} aria-label="Edge styles">
          <li><span className={`${styles.legendLine} ${styles.legendCausal}`} aria-hidden="true" />causal</li>
          <li><span className={`${styles.legendLine} ${styles.legendLoop}`} aria-hidden="true" />loop (rework)</li>
          <li><span className={`${styles.legendLine} ${styles.legendConnection}`} aria-hidden="true" />kept for connectivity</li>
        </ul>
      </div>

      {highlighted && highlighted.missing > 0 ? (
        <p className={styles.mapNote} role="note">
          {highlighted.missing} of {highlighted.total} transitions in this variant{" "}
          {highlighted.missing === 1 ? "is" : "are"} below the miner&apos;s dependency threshold, so{" "}
          {highlighted.missing === 1 ? "it is" : "they are"} not drawn as{" "}
          {highlighted.missing === 1 ? "an edge" : "edges"}.
        </p>
      ) : null}

      <svg
        ref={svgRef}
        className={styles.mapCanvas}
        viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`}
        role="img"
        aria-label={`Process map with ${map.nodes.length} activities and ${map.edges.length} edges. Use arrow keys to pan, plus and minus to zoom, 0 to show the whole map.`}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onKeyDown={onKeyDown}
      >
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className={styles.arrow} />
          </marker>
          <marker id="arrow-highlight" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="11" markerHeight="11" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className={styles.arrowHighlight} />
          </marker>
        </defs>
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {map.edges.map((edge) => {
            const source = nodesById.get(edge.source);
            const target = nodesById.get(edge.target);
            if (!source || !target) return null;
            const key = pairKey(edge.source, edge.target);
            const isOn = highlighted?.pairs.has(key) ?? false;
            const isDimmed = highlighted !== null && !isOn;
            const kindClass =
              edge.kind === "best_connection"
                ? styles.edgeConnection
                : edge.kind === "causal"
                  ? ""
                  : styles.edgeLoop;
            return (
              <path
                key={key}
                d={edgePath(source, target, edge.source === edge.target)}
                className={[styles.edge, kindClass, isOn ? styles.edgeOn : "", isDimmed ? styles.edgeDimmed : ""].join(" ")}
                strokeWidth={strokeWidth(edge.frequency, maxFrequency) + (isOn ? 1.5 : 0)}
                markerEnd={isOn ? "url(#arrow-highlight)" : "url(#arrow)"}
              >
                <title>{edgeTitle(edge)}</title>
              </path>
            );
          })}
          {map.nodes.map((node) => {
            const isOn = highlighted?.activities.has(node.id) ?? false;
            const isDimmed = highlighted !== null && !isOn;
            return (
              <g
                key={node.id}
                transform={`translate(${node.x - NODE_WIDTH / 2} ${node.y - NODE_HEIGHT / 2})`}
                className={[styles.node, node.start_count > 0 ? styles.nodeStart : "", isOn ? styles.nodeOn : "", isDimmed ? styles.nodeDimmed : ""].join(" ")}
              >
                <title>
                  {`${node.id} · ${formatCount(node.count)} events` +
                    (node.start_count ? ` · starts ${formatCount(node.start_count)} cases` : "") +
                    (node.end_count ? ` · ends ${formatCount(node.end_count)} cases` : "")}
                </title>
                <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx={2} />
                <text x={8} y={18} className={styles.nodeLabel}>
                  {node.id}
                </text>
                <text x={8} y={33} className={styles.nodeCount}>
                  {formatCount(node.count)} events{node.start_count > 0 ? " · start" : ""}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
