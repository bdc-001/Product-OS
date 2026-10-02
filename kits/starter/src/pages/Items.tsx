import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import PageHeader from "../components/PageHeader";
import StatusPill from "../components/StatusPill";
import { items as seed, type Item } from "../data/fixtures";

export default function Items() {
  const [rows, setRows] = useState<Item[]>(seed);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const visible = useMemo(
    () => rows.filter((row) => row.name.toLowerCase().includes(query.trim().toLowerCase())),
    [rows, query],
  );

  function create() {
    const clean = name.trim();
    if (!clean) return;
    setRows((current) => [
      { id: String(Date.now()), name: clean, owner: "You", status: "draft", updatedAt: new Date().toISOString().slice(0, 10), description: "", metric: 0 },
      ...current,
    ]);
    setName("");
    setCreating(false);
  }

  return (
    <>
      <PageHeader
        title="Items"
        subtitle={`${rows.length} total`}
        actions={
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            <Plus size={16} /> New item
          </button>
        }
      />
      <div className="px-8 py-6">
        <label className="mb-4 flex max-w-sm items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2">
          <Search size={16} className="text-muted" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search items"
            className="w-full bg-transparent text-sm outline-none"
          />
        </label>
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="bg-canvas text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Owner</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.id} className="border-t border-line hover:bg-canvas">
                  <td className="px-4 py-3 font-medium">
                    <Link to={`/items/${row.id}`} className="hover:text-brand">{row.name}</Link>
                  </td>
                  <td className="px-4 py-3 text-muted">{row.owner}</td>
                  <td className="px-4 py-3"><StatusPill status={row.status} /></td>
                  <td className="px-4 py-3 text-muted">{row.updatedAt}</td>
                </tr>
              ))}
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-muted">No items match "{query}".</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      {creating ? (
        <div className="fixed inset-0 grid place-items-center bg-black/30" onClick={() => setCreating(false)}>
          <div className="w-full max-w-md rounded-xl bg-surface p-6 shadow-xl" onClick={(event) => event.stopPropagation()}>
            <h2 className="text-lg font-semibold">New item</h2>
            <input
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && create()}
              placeholder="Name"
              className="mt-4 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-brand"
            />
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setCreating(false)} className="rounded-lg px-3 py-2 text-sm text-muted hover:bg-canvas">Cancel</button>
              <button onClick={create} disabled={!name.trim()} className="rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white disabled:opacity-40">Create</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
