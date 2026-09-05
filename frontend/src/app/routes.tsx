import { createBrowserRouter } from "react-router-dom";
import { App } from "@/app/App";
import { DashboardPage } from "@/pages/Dashboard/DashboardPage";
import { InvestigationsPage } from "@/pages/Investigations/InvestigationsPage";
import { CamerasPage } from "@/pages/Cameras/CamerasPage";
import { VehiclesPage } from "@/pages/Vehicles/VehiclesPage";
import { SatellitePage } from "@/pages/Satellite/SatellitePage";
import { AlertsPage } from "@/pages/Alerts/AlertsPage";
import { SettingsPage } from "@/pages/Settings/SettingsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "investigations", element: <InvestigationsPage /> },
      { path: "cameras", element: <CamerasPage /> },
      { path: "vehicles", element: <VehiclesPage /> },
      { path: "satellite", element: <SatellitePage /> },
      { path: "alerts", element: <AlertsPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);
