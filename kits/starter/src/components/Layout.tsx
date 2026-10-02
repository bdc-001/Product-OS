import { NavLink, Outlet } from "react-router-dom";
import { Home, LayoutList, Settings } from "lucide-react";
import clsx from "clsx";
import { product } from "../data/fixtures";

const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/items", label: "Items", icon: LayoutList, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

export default function Layout() {
  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r border-line bg-surface px-3 py-4">
        <div className="mb-6 flex items-center gap-2 px-2">
          <span className="grid size-8 place-items-center rounded-lg bg-brand text-sm font-bold text-white">
            {product.name.slice(0, 1)}
          </span>
          <span className="font-semibold">{product.name}</span>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
                  isActive ? "bg-brand-soft font-medium text-brand" : "text-muted hover:bg-canvas",
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
