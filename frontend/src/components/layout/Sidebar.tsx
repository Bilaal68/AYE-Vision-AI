import { NavLink } from "react-router-dom";
import {
  Bell,
  Camera,
  LayoutDashboard,
  Map,
  Satellite,
  Settings,
  Car,
  FolderSearch,
} from "lucide-react";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/investigations", label: "Investigations", icon: FolderSearch },
  { to: "/cameras", label: "Cameras", icon: Camera },
  { to: "/vehicles", label: "Vehicles", icon: Car },
  { to: "/satellite", label: "Satellite", icon: Satellite },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-700 bg-navy-900">
      <div className="flex items-center gap-2 border-b border-slate-700 px-5 py-4">
        <Map className="h-5 w-5 text-cyan-400" />
        <span className="text-sm font-semibold tracking-wide text-cyan-400">
          SecInt Platform
        </span>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition",
                isActive
                  ? "bg-navy-800 text-white"
                  : "text-slate-400 hover:bg-navy-800 hover:text-white",
              ].join(" ")
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
