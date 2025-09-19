// src/components/Chart.tsx
import React from "react";
import type { Config, Layout, PlotData } from "plotly.js";
import Plotly from "plotly.js/dist/plotly";

export interface ChartProps {
  data: Partial<PlotData>[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  frames?: Plotly.Frame[];

  // React-specific
  style?: React.CSSProperties;
  className?: string;
  useResizeHandler?: boolean; // optional manual resize listener
}

export const Chart: React.FC<ChartProps> = ({
  data,
  layout,
  config,
  frames,
  style,
  className,
  useResizeHandler
}) => {
  const divRef = React.useRef<HTMLDivElement | null>(null);

  // Mount: create the figure
  React.useEffect(() => {
    if (!divRef.current) return;

    // First render: newPlot
    Plotly.newPlot(divRef.current, data as any, layout as any, {
      responsive: true,
      displaylogo: false,
      ...(config || {})
    } as any).then(() => {
      // If frames were provided initially
      if (frames && frames.length) {
        Plotly.addFrames(divRef.current as any, frames);
      }
    });

    return () => {
      // Unmount: purge to free memory/listeners
      if (divRef.current) {
        Plotly.purge(divRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // run once

  // Update: react on data/layout/config/frames changes
  React.useEffect(() => {
    if (!divRef.current) return;

    // react(data, layout, config) is the correct signature
    Plotly.react(divRef.current, data as any, layout as any, {
      responsive: true,
      displaylogo: false,
      ...(config || {})
    } as any).then(() => {
      if (frames && frames.length) {
        Plotly.addFrames(divRef.current as any, frames);
      }
    });
  }, [data, layout, config, frames]);

  // Optional: manual resize handler (usually not needed if responsive: true)
  React.useEffect(() => {
    if (!useResizeHandler || !divRef.current) return;
    const onResize = () => Plotly.Plots.resize(divRef.current as any);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [useResizeHandler]);

  return <div ref={divRef} className={className} style={{ width: "100%", height: 400, ...style }} />;
};
