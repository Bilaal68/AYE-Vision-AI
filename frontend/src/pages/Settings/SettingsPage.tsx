import { Card, PageHeader } from "@/components/ui/PageChrome";

export function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" description="Placeholder for user and system settings." />
      <Card>
        <p className="text-sm text-slate-400">Authentication UI will come after the API foundation.</p>
      </Card>
    </div>
  );
}
