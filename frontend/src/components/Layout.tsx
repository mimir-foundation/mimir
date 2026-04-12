import { Outlet, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Search,
  BookOpen,
  Settings,
  GitBranch,
  MessageCircle,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import CaptureBar from "./CaptureBar";
import { useState } from "react";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/chat", icon: MessageCircle, label: "Chat" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/browse", icon: BookOpen, label: "Browse" },
  { to: "/connections", icon: GitBranch, label: "Connections" },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-surface-0">
      {/* Sidebar */}
      <aside
        className={`${
          collapsed ? "w-[68px]" : "w-60"
        } bg-surface-1 border-r border-border-subtle flex flex-col shrink-0 transition-all duration-200`}
      >
        {/* Logo */}
        <div className={`flex items-center gap-3 border-b border-border-subtle ${collapsed ? "px-3 py-4 justify-center" : "px-5 py-4"}`}>
          <img
            src="/logo.png"
            alt="Mimir"
            className={`${collapsed ? "w-8 h-8" : "w-9 h-9"} shrink-0`}
          />
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-[15px] font-bold text-white tracking-tight">Mimir</span>
              <span className="text-[10px] text-zinc-500 -mt-0.5">Second Brain</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 pt-3 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg text-[13px] font-medium transition-all duration-150 ${
                  collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
                } ${
                  isActive
                    ? "bg-brand-500/10 text-brand-400 shadow-[inset_0_0_0_1px] shadow-brand-500/20"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-surface-3"
                }`
              }
              title={collapsed ? label : undefined}
            >
              <Icon className="w-[18px] h-[18px] shrink-0" />
              {!collapsed && label}
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="border-t border-border-subtle px-2 py-2 space-y-0.5">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-lg text-[13px] font-medium transition-all duration-150 ${
                collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
              } ${
                isActive
                  ? "bg-brand-500/10 text-brand-400 shadow-[inset_0_0_0_1px] shadow-brand-500/20"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-surface-3"
              }`
            }
            title={collapsed ? "Settings" : undefined}
          >
            <Settings className="w-[18px] h-[18px] shrink-0" />
            {!collapsed && "Settings"}
          </NavLink>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={`flex items-center gap-3 rounded-lg text-[13px] font-medium text-zinc-500 hover:text-zinc-300 hover:bg-surface-3 transition-all duration-150 w-full ${
              collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
            }`}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <PanelLeft className="w-[18px] h-[18px]" />
            ) : (
              <>
                <PanelLeftClose className="w-[18px] h-[18px]" />
                Collapse
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <CaptureBar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-6 page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
