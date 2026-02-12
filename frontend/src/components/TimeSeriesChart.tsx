import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface DataPoint {
  label: string;
  value: number;
}

interface TimeSeriesChartProps {
  data: DataPoint[];
  title: string;
  color?: string;
  yLabel?: string;
}

export default function TimeSeriesChart({
  data,
  title,
  color = "#4caf50",
  yLabel,
}: TimeSeriesChartProps) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 600 }}>
        {title}
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11 }}
            angle={-30}
            textAnchor="end"
            height={60}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            label={
              yLabel
                ? {
                    value: yLabel,
                    angle: -90,
                    position: "insideLeft",
                    style: { fontSize: 12 },
                  }
                : undefined
            }
          />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
