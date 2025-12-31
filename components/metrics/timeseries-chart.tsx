"use client";

import { useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { TimeSeriesPoint } from "@/lib/api/metrics";

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[];
  title?: string;
  description?: string;
  /** Maximum number of data points to display */
  maxPoints?: number;
}

// Format timestamp for display - extracted for memoization
function formatTime(timestamp: string | null): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function TimeSeriesChart({
  data,
  title = "Executions Over Time",
  description = "Agent executions per hour",
  maxPoints = 24,
}: TimeSeriesChartProps) {
  // Memoize the visible data slice and formatted times
  const visibleData = useMemo(() => {
    const sliced = data.slice(-maxPoints);
    return sliced.map((point) => ({
      ...point,
      formattedTime: formatTime(point.timestamp),
    }));
  }, [data, maxPoints]);

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-8">
            No time series data available
          </p>
        </CardContent>
      </Card>
    );
  }

  // Use visible data for max calculation to ensure bars scale correctly
  const maxExecutions = Math.max(
    ...visibleData.map((d) => d.total_executions),
    1
  );
  const chartHeight = 200;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="relative" style={{ height: chartHeight }}>
          {/* Y-axis labels */}
          <div className="absolute left-0 top-0 bottom-0 w-10 flex flex-col justify-between text-xs text-muted-foreground pr-2">
            <span>{maxExecutions}</span>
            <span>{Math.round(maxExecutions / 2)}</span>
            <span>0</span>
          </div>

          {/* Chart area */}
          <div className="ml-12 h-full flex items-end gap-1">
            {visibleData.map((point, index) => {
              const successHeight =
                (point.successful_executions / maxExecutions) * chartHeight;
              const failedHeight =
                (point.failed_executions / maxExecutions) * chartHeight;

              return (
                <div
                  key={point.timestamp || index}
                  className="flex-1 flex flex-col justify-end group relative"
                  title={`${point.formattedTime}: ${point.total_executions} executions (${point.successful_executions} success, ${point.failed_executions} failed)`}
                >
                  {/* Stacked bar */}
                  <div className="flex flex-col">
                    {failedHeight > 0 && (
                      <div
                        className="bg-red-500 rounded-t-sm transition-all group-hover:opacity-80"
                        style={{ height: failedHeight }}
                      />
                    )}
                    <div
                      className="bg-green-500 rounded-t-sm transition-all group-hover:opacity-80"
                      style={{ height: successHeight }}
                    />
                  </div>

                  {/* Tooltip */}
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    <div className="bg-popover text-popover-foreground text-xs p-2 rounded shadow-lg whitespace-nowrap">
                      <div className="font-medium">{point.formattedTime}</div>
                      <div className="text-green-600">
                        Success: {point.successful_executions}
                      </div>
                      {point.failed_executions > 0 && (
                        <div className="text-red-600">
                          Failed: {point.failed_executions}
                        </div>
                      )}
                      <div className="text-muted-foreground">
                        Avg: {point.avg_duration_ms.toFixed(0)}ms
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* X-axis labels - use visible data for correct labels */}
        <div className="ml-12 mt-2 flex justify-between text-xs text-muted-foreground">
          {visibleData.length > 0 && (
            <>
              <span>{visibleData[0].formattedTime}</span>
              <span>{visibleData[visibleData.length - 1].formattedTime}</span>
            </>
          )}
        </div>

        {/* Legend */}
        <div className="flex justify-center gap-6 mt-4 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded" />
            <span>Successful</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded" />
            <span>Failed</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
