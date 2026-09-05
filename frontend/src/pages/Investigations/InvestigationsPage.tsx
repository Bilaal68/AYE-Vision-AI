import { Card, PageHeader } from "@/components/ui/PageChrome";

export function InvestigationsPage() {
  return (
    <div>
      <PageHeader
        title="Investigations"
        description="Placeholder page. Investigation workflows are not built yet."
      />
      <Card>
        <p className="text-sm text-slate-400">No investigations in this foundation.</p>
      </Card>
    </div>
  );
}
