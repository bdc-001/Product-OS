"""Campaigns list for the prototype sandbox. Do not import go_services."""

CAMPAIGNS_PAGE = r'''import { useMemo, useState } from "react";
import SenseFilterBar from "../components/FilterBar";

const CAMPAIGN_CHANNELS = {
  ai_call: "AI Call",
  human_call: "Human Call",
  whatsapp: "WhatsApp",
  sms: "SMS",
  widget: "Website Widget",
};

const CAMPAIGN_NAMES = [
  "Home Loan Winback",
  "Q3 Renewal Drive",
  "Personal Loan Top Up",
  "Credit Card Upgrade",
  "Insurance Renewal Reminder",
  "Fresh Lead Qualification",
  "Dormant Account Revival",
  "Festive Offer Outreach",
  "Auto Loan Cross Sell",
  "Premium Tier Upsell",
  "Onboarding Follow Up",
  "Missed Payment Recovery",
  "Policy Lapse Prevention",
  "Referral Activation",
  "Demo Booking Drive",
  "Feedback Collection",
  "Wallet Reload Nudge",
  "Gold Loan Interest",
  "Student Loan Enquiry",
  "Merchant Onboarding",
  "Churn Save Programme",
  "Health Plan Awareness",
  "Business Loan Prospecting",
  "Annual Maintenance Renewal",
];

const CAMPAIGN_STATUS_LIST = ["active", "paused", "pausing", "resuming", "completed"];
const CAMPAIGN_CHANNEL_SETS = [
  ["ai_call", "whatsapp", "sms"],
  ["ai_call", "human_call"],
  ["whatsapp", "sms"],
  ["ai_call", "whatsapp", "sms", "widget"],
  ["human_call", "sms"],
];
const CAMPAIGN_AGENT_NAMES = ["Nova Sales Assistant", "Atlas Collections Agent", "Iris Support Concierge", "Orion Renewal Agent"];
const CAMPAIGN_OWNERS = ["Arsalaan Mohammed", "Priya Nair", "Diego Ruiz"];

const CAMPAIGNS = CAMPAIGN_NAMES.map((name, i) => ({
  id: "cmp_" + String(1000 + i * 37),
  name,
  type: i % 3 === 2 ? "rule_based" : "smart_ai",
  status: CAMPAIGN_STATUS_LIST[i % 5],
  started: String((i % 28) + 1).padStart(2, "0") + "/" + String((i % 12) + 1).padStart(2, "0") + "/2026",
  contacts: 240 + i * 137,
  channels: CAMPAIGN_CHANNEL_SETS[i % CAMPAIGN_CHANNEL_SETS.length],
  agent: CAMPAIGN_AGENT_NAMES[i % 4],
  owner: CAMPAIGN_OWNERS[i % 3],
  hot: 10 + (i * 7) % 30,
  warm: 8 + (i * 5) % 25,
  cold: 6 + (i * 3) % 20,
  skip: 5 + (i * 4) % 22,
}));

const CAMP_FILTER_FIELDS = [
  {
    key: "status",
    label: "Status",
    group: "Campaign",
    primary: true,
    options: [
      { value: "active", label: "Active" },
      { value: "paused", label: "Paused" },
      { value: "pausing", label: "Pausing" },
      { value: "resuming", label: "Resuming" },
      { value: "completed", label: "Completed" },
    ],
  },
  {
    key: "type",
    label: "Type",
    group: "Campaign",
    primary: true,
    options: [
      { value: "smart_ai", label: "Smart AI" },
      { value: "rule_based", label: "Rule-Based" },
    ],
  },
  {
    key: "channel",
    label: "Channel",
    group: "Engagement",
    primary: true,
    options: Object.keys(CAMPAIGN_CHANNELS).map((id) => ({ value: id, label: CAMPAIGN_CHANNELS[id] })),
  },
  {
    key: "agent",
    label: "Agent",
    group: "Campaign",
    options: CAMPAIGN_AGENT_NAMES.map((name) => ({ value: name, label: name })),
  },
  {
    key: "owner",
    label: "Created by",
    group: "Campaign",
    options: CAMPAIGN_OWNERS.map((name) => ({ value: name, label: name })),
  },
];

const CAMP_SORTS = [
  { value: "started", label: "Recently started" },
  { value: "name", label: "Name A–Z" },
  { value: "contacts", label: "Most contacts" },
];

function CampaignStatusPill({ status }) {
  return (
    <span className={"status-pill status-" + status}>
      <span className="dot" />
      {status}
    </span>
  );
}

function CampaignChannelChips({ ids, max = 3 }) {
  const shown = ids.slice(0, max);
  const rest = ids.length - shown.length;
  return (
    <div className="channels">
      {shown.map((id) => (
        <span key={id} className="channel">
          <span className="dot" />
          {CAMPAIGN_CHANNELS[id] || id}
        </span>
      ))}
      {rest > 0 ? <span className="channel-more">+{rest}</span> : null}
    </div>
  );
}

function CampaignInterest({ row }) {
  const total = row.hot + row.warm + row.cold + row.skip || 1;
  const pct = (n) => Math.round((n / total) * 100);
  const items = [
    { key: "hot", label: "Hot", value: pct(row.hot), color: "#f43f5e" },
    { key: "warm", label: "Warm", value: pct(row.warm), color: "#f59e0b" },
    { key: "cold", label: "Cold", value: pct(row.cold), color: "#0ea5e9" },
    { key: "skip", label: "Not interested", value: pct(row.skip), color: "#9ca3af" },
  ];
  return (
    <div className="interest-box">
      <p className="label">Lead interest</p>
      <div className="interest-bar">
        {items.map((item) => (
          <span key={item.key} className={item.key} style={{ width: item.value + "%" }} />
        ))}
      </div>
      <div className="interest-legend">
        {items.map((item) => (
          <div key={item.key}>
            <p>
              <span className="legend-dot" style={{ background: item.color }} />
              {item.label}
            </p>
            <strong>{item.value}%</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function CampaignMenu({ open, onToggle, onEdit }) {
  return (
    <div className="relative">
      <button type="button" className="menu-btn" aria-label="Actions" onClick={onToggle}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="5" r="1.6" />
          <circle cx="12" cy="12" r="1.6" />
          <circle cx="12" cy="19" r="1.6" />
        </svg>
      </button>
      {open ? (
        <div className="menu-pop">
          <button type="button" onClick={onEdit}>Edit</button>
          <button type="button">Clone</button>
          <button type="button">Copy ID</button>
          <button type="button" className="danger">Delete</button>
        </div>
      ) : null}
    </div>
  );
}

function CampaignCard({ row, onOpenLeads, onOpenAnalytics, onOpenAnalysis, onEdit, menu, onMenu }) {
  return (
    <article className="campaign-card">
      <div className="card-head">
        <h3 onClick={() => onOpenLeads && onOpenLeads(row)}>{row.name}</h3>
        <CampaignStatusPill status={row.status} />
        <CampaignMenu open={menu === row.id} onToggle={() => onMenu(row.id)} onEdit={() => onEdit && onEdit(row)} />
      </div>
      <div className="card-body">
        <dl className="meta-grid">
          <div className="meta-cell">
            <dt>Agent</dt>
            <dd>{row.agent}</dd>
          </div>
          <div className="meta-cell">
            <dt>Created by</dt>
            <dd>{row.owner}</dd>
          </div>
          <div className="meta-cell">
            <dt>Started</dt>
            <dd>{row.started}</dd>
          </div>
        </dl>
        <CampaignInterest row={row} />
        <div className="flex justify-between items-center gap-3">
          <div className="min-w-0">
            <dl>
              <div className="meta-cell">
                <dt>Channels</dt>
                <dd className="mt-2"><CampaignChannelChips ids={row.channels} /></dd>
              </div>
            </dl>
          </div>
          <dl>
            <div className="meta-cell">
              <dt>Contacts</dt>
              <dd>{row.contacts.toLocaleString()}</dd>
            </div>
          </dl>
        </div>
      </div>
      <div className="card-foot">
        <div className="action-row">
          <button type="button" className="action-btn" onClick={() => onOpenLeads && onOpenLeads(row)}>View Leads</button>
          <button type="button" className="action-btn" onClick={() => onOpenAnalytics && onOpenAnalytics()}>Analytics</button>
          <button type="button" className="action-btn" onClick={() => onOpenAnalysis && onOpenAnalysis(row)}>Agent Analysis</button>
        </div>
      </div>
    </article>
  );
}

export default function Campaigns({ q = "", onOpenLeads, onOpenAnalytics, onOpenAnalysis, onCreate, onEdit }) {
  const [view, setView] = useState("grid");
  const [menu, setMenu] = useState("");
  const [filters, setFilters] = useState({});
  const [sort, setSort] = useState("started");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(9);
  const [createOpen, setCreateOpen] = useState(false);
  const [kind, setKind] = useState("");

  const filtered = useMemo(() => {
    const query = (q || "").toLowerCase();
    const status = filters.status || [];
    const types = filters.type || [];
    const channels = filters.channel || [];
    const agents = filters.agent || [];
    const owners = filters.owner || [];
    const rows = CAMPAIGNS.filter((row) => {
      if (query && !(row.name + row.agent + row.owner).toLowerCase().includes(query)) return false;
      if (status.length && !status.includes(row.status)) return false;
      if (types.length && !types.includes(row.type)) return false;
      if (channels.length && !channels.some((ch) => row.channels.includes(ch))) return false;
      if (agents.length && !agents.includes(row.agent)) return false;
      if (owners.length && !owners.includes(row.owner)) return false;
      return true;
    });
    rows.sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "contacts") return b.contacts - a.contacts;
      return 0;
    });
    return rows;
  }, [q, filters, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / limit));
  const current = Math.min(page, pages);
  const start = (current - 1) * limit;
  const rows = filtered.slice(start, start + limit);

  return (
    <div className="page">
      <SenseFilterBar
        fields={CAMP_FILTER_FIELDS}
        values={filters}
        onChange={(next) => { setFilters(next); setPage(1); }}
        sort={sort}
        sorts={CAMP_SORTS}
        onSort={setSort}
        trailing={(
          <div className="filter-trail-inner">
            <div className="view-toggle">
              <button type="button" className={view === "grid" ? "on" : ""} aria-label="Card view" onClick={() => setView("grid")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /></svg>
              </button>
              <button type="button" className={view === "list" ? "on" : ""} aria-label="List view" onClick={() => setView("list")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" /></svg>
              </button>
            </div>
            <button className="btn-primary" type="button" onClick={() => { setKind(""); setCreateOpen(true); }}>Create Campaign</button>
          </div>
        )}
      />
      {rows.length === 0 ? (
        <div className="empty">
          <div className="icon-wrap">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 7h18v12H3zM3 7l3-4h12l3 4" /></svg>
          </div>
          <h2 className="mt-4 font-semibold">No campaigns found</h2>
          <p className="muted mt-2">Adjust your search or create a campaign to start reaching leads.</p>
        </div>
      ) : view === "list" ? (
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>Campaign</th>
                <th>Status</th>
                <th>Type</th>
                <th>Agent</th>
                <th>Created by</th>
                <th>Started</th>
                <th>Channels</th>
                <th>Contacts</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="name" onClick={() => onOpenLeads && onOpenLeads(row)}>{row.name}</td>
                  <td><CampaignStatusPill status={row.status} /></td>
                  <td>{row.type === "smart_ai" ? "Smart AI" : "Rule-Based"}</td>
                  <td>{row.agent}</td>
                  <td>{row.owner}</td>
                  <td>{row.started}</td>
                  <td><CampaignChannelChips ids={row.channels} /></td>
                  <td>{row.contacts.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="campaign-grid">
          {rows.map((row) => (
            <CampaignCard
              key={row.id}
              row={row}
              menu={menu}
              onMenu={(id) => setMenu((cur) => (cur === id ? "" : id))}
              onOpenLeads={onOpenLeads}
              onOpenAnalytics={onOpenAnalytics}
              onOpenAnalysis={onOpenAnalysis}
              onEdit={onEdit}
            />
          ))}
        </div>
      )}
      <div className="pager">
        <div className="flex items-center gap-3">
          <label className="muted">Items per page</label>
          <select className="field-input" style={{ width: 80 }} value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setPage(1); }}>
            <option value={9}>9</option>
            <option value={15}>15</option>
            <option value={30}>30</option>
          </select>
          <span className="muted">Showing {filtered.length === 0 ? 0 : start + 1} to {Math.min(start + limit, filtered.length)} of {filtered.length}</span>
        </div>
        <div className="flex gap-2">
          <button type="button" disabled={current === 1} onClick={() => setPage(current - 1)}>Prev</button>
          {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
            <button key={n} type="button" className={n === current ? "on" : ""} onClick={() => setPage(n)}>{n}</button>
          ))}
          <button type="button" disabled={current === pages} onClick={() => setPage(current + 1)}>Next</button>
        </div>
      </div>
      {createOpen ? (
        <div className="sense-modal" onClick={() => setCreateOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2>Create Campaign</h2>
            <p className="muted">Choose how this campaign should engage leads.</p>
            <div className="kind-grid mt-4">
              <button type="button" className={kind === "smart_ai" ? "kind-card on" : "kind-card"} onClick={() => setKind("smart_ai")}>
                <strong>Smart AI Campaign</strong>
                <span>An AI agent sequences calls, WhatsApp and SMS using the full playbook.</span>
              </button>
              <button type="button" className={kind === "rule_based" ? "kind-card on" : "kind-card"} onClick={() => setKind("rule_based")}>
                <strong>Rule Based Campaign</strong>
                <span>Call-only agents follow a fixed script and routing rules.</span>
              </button>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>Cancel</button>
              <button
                type="button"
                className="btn-primary"
                disabled={!kind}
                onClick={() => { if (onCreate) onCreate(kind); setCreateOpen(false); }}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
'''
