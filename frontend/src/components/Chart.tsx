import { useEffect, useRef, useState } from 'react';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { SVGRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  SVGRenderer,
]);

export interface ChartTable {
  caption: string;
  headers: string[];
  rows: (string | number)[][];
}

/**
 * An ECharts chart (bundled, SVG renderer) with a "view as table" toggle (P8.7, P12.5): every chart
 * has a table alternative with the same numbers.
 */
export default function Chart({
  option,
  table,
  height = 260,
  label,
}: {
  option: EChartsCoreOption;
  table: ChartTable;
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [asTable, setAsTable] = useState(false);

  useEffect(() => {
    if (asTable || !ref.current) return;
    // jsdom (unit tests) has no canvas for text measurement; the table view covers the data there.
    if (navigator.userAgent.includes('jsdom')) return;
    let chart: echarts.ECharts | null = null;
    try {
      chart = echarts.init(ref.current, undefined, { renderer: 'svg' });
      chart.setOption({ animation: false, textStyle: { fontFamily: 'inherit' }, ...option });
    } catch {
      return; // environments without layout (tests): the table view still works
    }
    const onResize = () => chart?.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart?.dispose();
    };
  }, [option, asTable]);

  return (
    <figure className="chart">
      <div className="chart-toolbar">
        <figcaption>{label}</figcaption>
        <button type="button" className="btn btn-link small" onClick={() => setAsTable(!asTable)}>
          {asTable ? 'View as chart' : 'View as table'}
        </button>
      </div>
      {asTable ? (
        <div className="table-scroll">
          <table className="table compact">
            <caption className="sr-only">{table.caption}</caption>
            <thead>
              <tr>
                {table.headers.map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          ref={ref}
          style={{ height }}
          role="img"
          aria-label={`${label}. Use “View as table” for the numbers.`}
        />
      )}
    </figure>
  );
}
