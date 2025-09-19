// Plot.tsx
import React, { useEffect, useRef } from "react";
import Plotly, { Layout, Config, Data } from "plotly.js-dist-min";

type Props = {
  data: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  className?: string;
  style?: React.CSSProperties;
  // Optional: keep UI state (zoom/pan) across updates by passing a stable key
  uirevision?: string | number;
  // Optional: force reread of array contents if you mutate arrays in place
  datarevision?: number | string;
  // Callbacks
  onInitialized?: (gd: Plotly.Root) => void;
  onUpdate?: (gd: Plotly.Root) => void;
  onError?: (err: unknown) => void;
};

export default function Plot({
  data,
  layout,
  config,
  className,
  style,
  uirevision,
  datarevision,
  onInitialized,
  onUpdate,
  onError,
}: Props) {
  const divRef = useRef<HTMLDivElement | null>(null);
  const gdRef = useRef<Plotly.Root | null>(null);
  const roRef = useRef<ResizeObserver | null>(null);

  // Initialize once
  useEffect(() => {
    const el = divRef.current;
    if (!el) return;

    // First render: use newPlot for the initial draw
    const firstLayout = {
      ...layout,
      uirevision: uirevision ?? layout?.uirevision,
      datarevision: datarevision ?? layout?.datarevision,
    };

    Plotly.newPlot(el, data, firstLayout, config)
      .then((gd) => {
        gdRef.current = gd;
        onInitialized?.(gd);

        // Resize handling
        if (!roRef.current && "ResizeObserver" in window) {
          roRef.current = new ResizeObserver(() => {
            if (gdRef.current) Plotly.Plots.resize(gdRef.current);
          });
          roRef.current.observe(el);
        }
      })
      .catch(onError);

    // Cleanup
    return () => {
      try {
        roRef.current?.disconnect();
        roRef.current = null;
        if (gdRef.current) {
          Plotly.purge(gdRef.current);
          gdRef.current = null;
        }
      } catch (e) {
        onError?.(e);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // init once

  // Update on prop changes (data/layout/config/uirevision/datarevision)
  useEffect(() => {
    const gd = gdRef.current;
    if (!gd) return;

    const nextLayout: Partial<Layout> = {
      ...layout,
      uirevision: uirevision ?? layout?.uirevision,
      datarevision: datarevision ?? layout?.datarevision,
    };

    Plotly.react(gd, data, nextLayout, config)
      .then(onUpdate)
      .catch(onError);
  }, [data, layout, config, uirevision, datarevision, onUpdate, onError]);

  return <div ref={divRef} className={className} style={style} />;
}
