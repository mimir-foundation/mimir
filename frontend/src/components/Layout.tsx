import { Outlet, NavLink } from "react-router-dom";
import { LayoutDashboard, Search, BookOpen, Settings, Brain, GitBranch } from "lucide-react";
import CaptureBar from "./CaptureBar";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/browse", icon: BookOpen, label: "Browse" },
  { to: "/connections", icon: GitBranch, label: "Connections" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        <div className="p-4 flex items-center gap-2 border-b border-gray-800">
          <Brain className="w-6 h-6 text-indigo-400" />
          <span className="text-lg font-bold text-white">Mimir</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-indigo-600/20 text-indigo-300"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <CaptureBar />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
