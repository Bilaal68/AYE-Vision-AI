import { Card, PageHeader } from "@/components/ui/PageChrome";

export function AlertsPage() {
  return (
    <div>
      <PageHeader title="Alerts" description="Placeholder. Alert pipelines are not built yet." />
      <Card>
        <p className="text-sm text-slate-400">No live alerts in the foundation.</p>
      </Card>
    </div>
  );
}
