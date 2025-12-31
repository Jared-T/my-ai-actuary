"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { LatencyPercentiles } from "@/lib/api/metrics";

interface LatencyChartProps {
  data: LatencyPercentiles;
}

export function LatencyChart({ data }: LatencyChartProps) {
  const maxValue = data.max || 1;

  const percentiles = [
    { label: "Min", value: data.min, color: "bg-green-500" },
    { label: "P50", value: data.p50, color: "bg-blue-400" },
    { label: "P75", value: data.p75, color: "bg-blue-500" },
    { label: "P90", value: data.p90, color: "bg-yellow-500" },
    { label: "P95", value: data.p95, color: "bg-orange-500" },
    { label: "P99", value: data.p99, color: "bg-red-500" },
    { label: "Max", value: data.max, color: "bg-red-600" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Latency Distribution</CardTitle>
        <CardDescription>
          Response time percentiles (avg: {data.avg.toFixed(0)}ms)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {percentiles.map((p) => (
            <div key={p.label} className="flex items-center gap-3">
              <span className="w-10 text-sm font-medium text-right">
                {p.label}
              </span>
              <div className="flex-1 bg-muted rounded-full h-4 overflow-hidden">
                <div
                  className={`h-full ${p.color} transition-all duration-500`}
                  style={{
                    width: `${Math.max((p.value / maxValue) * 100, 2)}%`,
                  }}
                />
              </div>
              <span className="w-20 text-sm text-right text-muted-foreground">
                {p.value.toFixed(0)}ms
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
