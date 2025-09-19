// Chart.tsx
import React, { useEffect, useRef } from "react";
import type { PlotData, Layout, Config } from "plotly.js";
import Plotly from "plotly.js/dist/plotly";

export type ChartProps = {
  data: Partial<PlotData>[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  style?: React.CSSProperties;
  className?: string;
  frames?: Plotly.Frame[];
};

export const Chart: React.FC<ChartProps> = ({
  data,
  layout,
  config,
  frames,
  style,
  className
}) => {
  const ref = useRef<HTMLDivElement | null>(null);

  // Mount/unmount
  useEffect(() => {
    if (!ref.current) return;
    Plotly.newPlot(ref.current, data as any, { uirevision: 'stable', ...layout } as any, {
      responsive: true,
      displaylogo: false,
      ...(config || {})
    } as any).then(() => {
      if (frames?.length) Plotly.addFrames(ref.current as any, frames);
    });

    return () => { if (ref.current) Plotly.purge(ref.current); };
    // run once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Updates
  useEffect(() => {
    if (!ref.current) return;
    Plotly.react(ref.current, data as any, { uirevision: 'stable', ...layout } as any, {
      responsive: true,
      displaylogo: false,
      ...(config || {})
    } as any).then(() => {
      if (frames?.length) Plotly.addFrames(ref.current as any, frames);
    });
  }, [data, layout, config, frames]);

  return <div ref={ref} className={className} style={{ width: "100%", height: 400, ...style }} />;
};
