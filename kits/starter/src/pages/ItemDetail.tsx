import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import PageHeader from "../components/PageHeader";
import StatusPill from "../components/StatusPill";
import { items } from "../data/fixtures";

export default function ItemDetail() {
  const { id } = useParams();
  const item = items.find((row) => row.id === id);
  if (!item) {
    return (
      <div className="px-8 py-10 text-sm text-muted">
        Item not found. <Link to="/items" className="text-brand">Back to items</Link>
      </div>
    );
  }
  return (
    <>
      <PageHeader
        title={item.name}
        subtitle={`Owned by ${item.owner} · updated ${item.updatedAt}`}
        actions={<StatusPill status={item.status} />}
      />
      <div className="space-y-4 px-8 py-6">
        <Link to="/items" className="inline-flex items-center gap-1 text-sm text-muted hover:text-brand">
          <ArrowLeft size={14} /> All items
        </Link>
        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="text-sm font-semibold">Overview</h2>
          <p className="mt-2 text-sm text-muted">{item.description || "No description yet."}</p>
        </section>
        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="text-sm font-semibold">Health</h2>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-canvas">
            <div className="h-full rounded-full bg-brand" style={{ width: `${item.metric}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted">{item.metric}% of target</p>
        </section>
      </div>
    </>
  );
}
