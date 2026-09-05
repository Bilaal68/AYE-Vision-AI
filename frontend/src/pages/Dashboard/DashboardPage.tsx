import { Card, PageHeader } from "@/components/ui/PageChrome";
import { BackendStatus } from "@/features/dashboard/BackendStatus";

export function DashboardPage() {
  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Application shell only. Feature widgets will be added in Prototype 1."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <BackendStatus />
        <Card>
          <h2 className="mb-2 text-lg font-semibold text-cyan-400">Map</h2>
          <p className="text-sm text-slate-400">
            Leaflet is installed. A live map is not implemented in this foundation.
          </p>
        </Card>
      </div>
    </div>
  );
}
