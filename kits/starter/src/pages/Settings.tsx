import { useState } from "react";
import PageHeader from "../components/PageHeader";

export default function Settings() {
  const [notify, setNotify] = useState(true);
  const [name, setName] = useState("My workspace");

  return (
    <>
      <PageHeader title="Settings" subtitle="Workspace preferences." />
      <div className="max-w-2xl space-y-4 px-8 py-6">
        <section className="rounded-xl border border-line bg-surface p-5">
          <label className="text-sm font-medium" htmlFor="workspace-name">Workspace name</label>
          <input
            id="workspace-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-2 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-brand"
          />
        </section>
        <section className="flex items-center justify-between rounded-xl border border-line bg-surface p-5">
          <div>
            <p className="text-sm font-medium">Email notifications</p>
            <p className="text-xs text-muted">Send a summary when an item fails.</p>
          </div>
          <button
            role="switch"
            aria-checked={notify}
            onClick={() => setNotify((value) => !value)}
            className={`relative h-6 w-11 rounded-full transition ${notify ? "bg-brand" : "bg-line"}`}
          >
            <span className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition ${notify ? "left-5" : "left-0.5"}`} />
          </button>
        </section>
      </div>
    </>
  );
}
