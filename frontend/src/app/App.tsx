import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";

export function App() {
  return (
    <div className="flex min-h-screen bg-navy-950 text-slate-100">
      <Sidebar />
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
