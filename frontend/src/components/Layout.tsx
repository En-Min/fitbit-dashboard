import { NavLink, Outlet } from "react-router-dom";
import {
  Heart,
  Moon,
  Activity,
  BarChart3,
  Settings,
  LayoutDashboard,
  Droplet,
} from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: <LayoutDashboard size={20} /> },
  { to: "/heart-rate", label: "Heart Rate", icon: <Heart size={20} /> },
  { to: "/sleep", label: "Sleep", icon: <Moon size={20} /> },
  { to: "/activity", label: "Activity", icon: <Activity size={20} /> },
  { to: "/glucose", label: "Glucose", icon: <Droplet size={20} /> },
  {
    to: "/correlations",
    label: "Correlations",
    icon: <BarChart3 size={20} />,
  },
  { to: "/settings", label: "Settings", icon: <Settings size={20} /> },
];

export default function Layout() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <Activity size={28} className="logo-icon" />
            <div className="logo-text">
              <h1>Fitbit Raw</h1>
              <span>Dashboard</span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-footer-text">Fitbit Data Explorer</div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
