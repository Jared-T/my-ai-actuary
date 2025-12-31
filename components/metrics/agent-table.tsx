"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { AgentBreakdown } from "@/lib/api/metrics";

interface AgentTableProps {
  data: AgentBreakdown[];
}

export function AgentTable({ data }: AgentTableProps) {
  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Agent Performance</CardTitle>
          <CardDescription>Breakdown by agent type</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-8">
            No agent data available
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Performance</CardTitle>
        <CardDescription>Breakdown by agent type</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-3 px-2 font-medium">Agent Type</th>
                <th className="text-right py-3 px-2 font-medium">Executions</th>
                <th className="text-right py-3 px-2 font-medium">Success Rate</th>
                <th className="text-right py-3 px-2 font-medium">Avg Duration</th>
                <th className="text-right py-3 px-2 font-medium">Tokens</th>
                <th className="text-right py-3 px-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {data.map((agent) => (
                <tr key={agent.agent_type} className="border-b last:border-0">
                  <td className="py-3 px-2 font-medium capitalize">
                    {agent.agent_type.replace(/_/g, " ")}
                  </td>
                  <td className="py-3 px-2 text-right">
                    <span className="text-green-600">{agent.successful_executions}</span>
                    {" / "}
                    <span>{agent.total_executions}</span>
                    {agent.failed_executions > 0 && (
                      <span className="text-red-600 ml-1">
                        ({agent.failed_executions} failed)
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-right">
                    <span
                      className={
                        agent.success_rate >= 0.95
                          ? "text-green-600"
                          : agent.success_rate >= 0.8
                            ? "text-yellow-600"
                            : "text-red-600"
                      }
                    >
                      {(agent.success_rate * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-3 px-2 text-right">
                    {agent.avg_duration_ms.toFixed(0)}ms
                  </td>
                  <td className="py-3 px-2 text-right">
                    {agent.total_tokens.toLocaleString()}
                  </td>
                  <td className="py-3 px-2 text-right">
                    ${agent.total_cost_usd.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
