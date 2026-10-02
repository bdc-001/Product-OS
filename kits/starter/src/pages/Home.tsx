import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import StatusPill from "../components/StatusPill";
import { items, stats } from "../data/fixtures";

export default function Home() {
  return (
    <>
      <PageHeader title="Home" subtitle="What changed and what needs attention." />
      <div className="space-y-6 px-8 py-6">
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-xl border border-line bg-surface p-4">
              <p className="text-sm text-muted">{stat.label}</p>
              <p className="mt-1 text-2xl font-semibold">{stat.value}</p>
            </div>
          ))}
        </section>
        <section className="rounded-xl border border-line bg-surface">
          <h2 className="border-b border-line px-4 py-3 text-sm font-semibold">Recently updated</h2>
          <ul>
            {items.slice(0, 3).map((item) => (
              <li key={item.id} className="flex items-center justify-between border-b border-line px-4 py-3 last:border-0">
                <Link to={`/items/${item.id}`} className="text-sm font-medium hover:text-brand">
                  {item.name}
                </Link>
                <StatusPill status={item.status} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
