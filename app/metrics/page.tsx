import { Metadata } from "next";
import { MetricsDashboard } from "@/components/metrics/metrics-dashboard";

export const metadata: Metadata = {
  title: "Agent Performance Metrics | AI Actuary",
  description:
    "Monitor agent performance, latency, success rates, and token usage in real-time.",
};

export default function MetricsPage() {
  return (
    <div className="container mx-auto py-8 px-4">
      <MetricsDashboard />
    </div>
  );
}
