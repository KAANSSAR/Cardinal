interface SparklineProps {
    data: number[];
    width?: number;
    height?: number;
    strokeColor?: string;
    fillOpacity?: number;
    strokeWidth?: number;
    className?: string;
  }
  
  /**
   * Minimal inline SVG sparkline — line + semi-transparent area fill.
   * No charting library: this is deliberately lightweight since it's
   * rendered many times per page (comps rows, quant rows, index cards).
   */
  export default function Sparkline({
    data,
    width = 120,
    height = 36,
    strokeColor = "currentColor",
    fillOpacity = 0.15,
    strokeWidth = 2,
    className = "",
  }: SparklineProps) {
    if (!data || data.length < 2) {
      return <svg width={width} height={height} className={className} />;
    }
  
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padY = height * 0.12;
  
    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - padY - ((v - min) / range) * (height - padY * 2);
      return [x, y] as const;
    });
  
    const linePath = points
      .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
      .join(" ");
  
    const areaPath =
      `M${points[0][0].toFixed(2)},${height} ` +
      points.map(([x, y]) => `L${x.toFixed(2)},${y.toFixed(2)}`).join(" ") +
      ` L${points[points.length - 1][0].toFixed(2)},${height} Z`;
  
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        preserveAspectRatio="none"
      >
        <path d={areaPath} fill={strokeColor} opacity={fillOpacity} stroke="none" />
        <path
          d={linePath}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }