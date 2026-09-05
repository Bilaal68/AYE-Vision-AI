import { useQuery } from "@tanstack/react-query";
import { fetchHealth, type HealthResponse } from "@/services/api";
import { Card } from "@/components/ui/PageChrome";

function statusLabel(data: HealthResponse | undefined, error: Error | null, isLoading: boolean) {
  if (isLoading) return "Checking backend…";
  if (error) return "Backend unavailable";
  if (data?.status === "ok" && data.database === "ok") return "Backend available";
  if (data) return `Backend ${data.status} (database: ${data.database})`;
  return "Unknown";
}

export function BackendStatus() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15000,
  });

  const ok = !error && data?.status === "ok" && data.database === "ok";

  return (
    <Card>
      <h2 className="mb-2 text-lg font-semibold text-cyan-400">API health</h2>
      <p className="text-sm text-slate-300">{statusLabel(data, error as Error | null, isLoading)}</p>
      <p className={`mt-3 text-sm font-medium ${ok ? "text-emerald-400" : "text-amber-400"}`}>
        GET /api/health/
      </p>
      {data && (
        <pre className="mt-3 overflow-auto rounded bg-navy-950 p-3 text-xs text-slate-400">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
      {error && (
        <p className="mt-3 text-xs text-rose-400">
          {(error as Error).message}. Start Django on port 8000, or use Docker Compose.
        </p>
      )}
    </Card>
  );
}
