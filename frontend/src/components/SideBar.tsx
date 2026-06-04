import { NavLink } from "react-router-dom";
import clsx from "clsx";

const items = [
  { to: "/", label: "Dashboard" },
  { to: "/library", label: "Library" },
  { to: "/jobs", label: "Jobs" },
  { to: "/settings", label: "Settings" },
];

export function SideBar() {
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card flex flex-col">
      <div className="p-5 text-lg font-semibold tracking-tight">Media Toolkit</div>
      <nav className="px-2 flex-1 overflow-y-auto">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.to === "/"}
            className={({ isActive }) =>
              clsx(
                "block px-3 py-2 rounded-md mb-1 transition",
                isActive ? "bg-accent/20 text-white" : "text-muted hover:text-white hover:bg-white/5",
              )
            }
          >
            {it.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 text-xs text-muted">v0.1.0 · localhost</div>
    </aside>
  );
}
