"""Checked-in Sense product shell for prototype sandbox. Do not import go_services."""

SENSE_SHELL = r'''import { useEffect, useState } from "react";

function Icon({ d, size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

function SenseLogo() {
  return (
    <svg className="sense-logo" viewBox="0 0 40 40" width="36" height="36" aria-hidden="true">
      <circle cx="16" cy="20" r="12" fill="#5B8DEF" opacity="0.9" />
      <circle cx="24" cy="20" r="12" fill="#5CE1E6" opacity="0.9" />
    </svg>
  );
}

const NAV = [
  {
    section: "Main",
    items: [
      { id: "campaigns", name: "Campaigns", d: "M3 8l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
      { id: "analytics", name: "Analytics", d: "M4 19V9m6 10V5m6 14v-7m6 7V8" },
      { id: "customers", name: "Customers", d: "M16 21v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2M12 7a4 4 0 110-8 4 4 0 010 8z" },
    ],
  },
  {
    section: "AI",
    items: [
      { id: "agents", name: "AI Agents", d: "M9 3h6l1 3h4v14H4V6h4l1-3zM9 13h6" },
      { id: "tools", name: "AI Tools", d: "M14.7 6.3a4 4 0 01.8 5.4L9 18l-4 1 1-4 6.5-6.5a4 4 0 015.2-.9z" },
      { id: "kb", name: "Knowledge Base", d: "M4 19a2 2 0 012-2h12M6 17V5a2 2 0 012-2h10v14H8a2 2 0 00-2 2z" },
    ],
  },
  {
    section: "Human",
    items: [
      { id: "human", name: "Human Agent", d: "M4 6h16v12H4zM8 10h8M8 14h5" },
      { id: "settings", name: "Settings", d: "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H8a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V8c.3.7 1 1.2 1.8 1.2H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z" },
    ],
  },
];

const NOTICES = [
  { title: "Home Loan Winback paused", body: "Campaign paused after a DND spike on AI Call.", when: "2m ago" },
  { title: "Nova analysis ready", body: "Overall score 79. Review suggested prompt edits.", when: "1h ago" },
  { title: "Wallet running low", body: "₹18,420 remaining this billing cycle.", when: "Yesterday" },
];

export default function SenseShell({ active = "campaigns", title = "Campaigns", onNavigate, search = "", onSearch, searchPlaceholder = "Search", children }) {
  const [collapsed, setCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <div className={collapsed ? "sense-app is-collapsed" : "sense-app"}>
      <aside className="sense-sidebar">
        <div className="sense-brand">
          <SenseLogo />
          {collapsed ? null : <span>Sense</span>}
        </div>
        <nav className="sense-nav">
          {NAV.map((group) => (
            <div key={group.section} className="sense-nav-section">
              {collapsed ? null : <p className="sense-nav-label">{group.section}</p>}
              {group.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={item.id === active ? "nav-item on" : "nav-item"}
                  onClick={() => onNavigate && onNavigate(item.id)}
                >
                  <Icon d={item.d} />
                  {collapsed ? null : <span>{item.name}</span>}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <button
          type="button"
          className="sense-collapse"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={() => setCollapsed((value) => !value)}
        >
          <Icon d={collapsed ? "M10 7l5 5-5 5" : "M14 7l-5 5 5 5"} size={16} />
        </button>
      </aside>
      <div className="sense-main">
        <header className="sense-top">
          <h1 className="sense-top-title">{title}</h1>
          <div className="top-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="18" height="18"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" /></svg>
            <input value={search} placeholder={searchPlaceholder} onChange={(e) => onSearch && onSearch(e.target.value)} />
          </div>
          <div className="sense-top-actions">
            <button type="button" className="icon-btn" aria-label="Theme" onClick={() => setDark((value) => !value)}>
              <Icon d={dark ? "M12 3v2m0 14v2m9-9h-2M5 12H3m14.4 6.4l-1.4-1.4M8 8L6.6 6.6m10.8 0L16 8M8 16l-1.4 1.4M16 12a4 4 0 11-8 0 4 4 0 018 0z" : "M21 14.5A8.5 8.5 0 1112.5 3 7 7 0 0021 14.5z"} />
            </button>
            <button type="button" className="icon-btn" aria-label="Notifications" onClick={() => { setNotifyOpen((value) => !value); setMenuOpen(false); }}>
              <Icon d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0a3 3 0 11-6 0" />
              <span className="dot" />
            </button>
            <button type="button" className="sense-avatar" aria-label="Account menu" onClick={() => { setMenuOpen((value) => !value); setNotifyOpen(false); }}>
              A
            </button>
          </div>
          {notifyOpen ? (
            <div className="notify-menu">
              <p className="notify-head">Notifications</p>
              {NOTICES.map((item) => (
                <div key={item.title} className="notify-row">
                  <strong>{item.title}</strong>
                  <span>{item.body}</span>
                  <em>{item.when}</em>
                </div>
              ))}
            </div>
          ) : null}
          {menuOpen ? (
            <div className="account-menu">
              <div className="who">
                <div className="sense-avatar">A</div>
                <div>
                  <strong>Arsalaan Mohammed</strong>
                  <span>Admin</span>
                </div>
              </div>
              <button type="button" className="menu-row">Profile</button>
              <button type="button" className="menu-row">Sign out</button>
            </div>
          ) : null}
        </header>
        <div className="sense-body">{children}</div>
      </div>
    </div>
  );
}
'''

CAMPAIGNS_PAGE = r'''import { useMemo, useState } from "react";

const CAMPAIGN_CHANNELS = {
  ai_call: "AI Call",
  human_call: "Human Call",
  whatsapp: "WhatsApp",
  sms: "SMS",
  widget: "Website Widget",
};

const CAMPAIGNS = [
  {
    id: "cmp_1000",
    name: "Home Loan Winback",
    type: "smart_ai",
    status: "active",
    started: "01/08/2026",
    contacts: 240,
    channels: ["ai_call", "whatsapp", "sms"],
    agent: "Nova Sales Assistant",
    owner: "Arsalaan Mohammed",
    hot: 18,
    warm: 12,
    cold: 10,
    skip: 8,
  },
  {
    id: "cmp_1025",
    name: "Q3 Renewal Drive",
    type: "smart_ai",
    status: "paused",
    started: "04/07/2026",
    contacts: 377,
    channels: ["ai_call", "human_call"],
    agent: "Atlas Collections Agent",
    owner: "Priya Nair",
    hot: 25,
    warm: 17,
    cold: 13,
    skip: 19,
  },
  {
    id: "cmp_104a",
    name: "Personal Loan Top Up",
    type: "rule_based",
    status: "pausing",
    started: "07/06/2026",
    contacts: 514,
    channels: ["whatsapp", "sms"],
    agent: "Iris Support Concierge",
    owner: "Diego Ruiz",
    hot: 32,
    warm: 22,
    cold: 16,
    skip: 30,
  },
  {
    id: "cmp_106f",
    name: "Credit Card Upgrade",
    type: "smart_ai",
    status: "resuming",
    started: "10/05/2026",
    contacts: 651,
    channels: ["ai_call", "whatsapp", "sms", "widget"],
    agent: "Orion Renewal Agent",
    owner: "Arsalaan Mohammed",
    hot: 14,
    warm: 27,
    cold: 19,
    skip: 16,
  },
  {
    id: "cmp_1094",
    name: "Insurance Renewal Reminder",
    type: "smart_ai",
    status: "completed",
    started: "13/04/2026",
    contacts: 788,
    channels: ["human_call", "sms"],
    agent: "Nova Sales Assistant",
    owner: "Priya Nair",
    hot: 21,
    warm: 12,
    cold: 22,
    skip: 27,
  },
  {
    id: "cmp_10b9",
    name: "Fresh Lead Qualification",
    type: "rule_based",
    status: "active",
    started: "16/03/2026",
    contacts: 925,
    channels: ["ai_call", "whatsapp", "sms"],
    agent: "Atlas Collections Agent",
    owner: "Diego Ruiz",
    hot: 28,
    warm: 17,
    cold: 10,
    skip: 13,
  },
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

function CampaignMenu({ open, onToggle }) {
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
          <button type="button">Edit</button>
          <button type="button">Clone</button>
          <button type="button">Copy ID</button>
          <button type="button" className="danger">Delete</button>
        </div>
      ) : null}
    </div>
  );
}

function CampaignCard({ row, onOpenLeads, onOpenAnalytics, onOpenAnalysis, menu, onMenu }) {
  return (
    <article className="campaign-card">
      <div className="card-head">
        <h3 onClick={() => onOpenLeads && onOpenLeads(row)}>{row.name}</h3>
        <CampaignStatusPill status={row.status} />
        <CampaignMenu open={menu === row.id} onToggle={() => onMenu(row.id)} />
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

export default function Campaigns({ onOpenLeads, onOpenAnalytics, onOpenAnalysis }) {
  const [q, setQ] = useState("");
  const [view, setView] = useState("grid");
  const [menu, setMenu] = useState("");
  const rows = useMemo(
    () => CAMPAIGNS.filter((row) => row.name.toLowerCase().includes(q.toLowerCase()) || row.agent.toLowerCase().includes(q.toLowerCase())),
    [q],
  );

  return (
    <div className="page">
      <div className="toolbar">
        <div className="search-field">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3-3" />
          </svg>
          <input value={q} placeholder="Search campaigns" onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="view-toggle">
          <button type="button" className={view === "grid" ? "on" : ""} aria-label="Card view" onClick={() => setView("grid")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /></svg>
          </button>
          <button type="button" className={view === "list" ? "on" : ""} aria-label="List view" onClick={() => setView("list")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" /></svg>
          </button>
        </div>
        <button className="btn-primary" type="button">Create Campaign</button>
      </div>
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
            />
          ))}
        </div>
      )}
      <div className="pager">
        <span className="muted">Showing {rows.length} of {CAMPAIGNS.length}</span>
        <div className="flex gap-2">
          <button type="button" disabled>Prev</button>
          <button type="button" className="on">1</button>
          <button type="button" disabled>Next</button>
        </div>
      </div>
    </div>
  );
}
'''

AGENTS_PAGE = r'''import { useMemo, useState } from "react";

const AGENT_CHANNELS = {
  ai_call: "AI Call",
  human_call: "Human Call",
  whatsapp: "WhatsApp",
  sms: "SMS",
  widget: "Website Widget",
};

const AGENTS = [
  {
    id: "nova",
    name: "Nova Sales Assistant",
    active: true,
    owner: "Arsalaan Mohammed",
    languages: ["English", "Hindi"],
    voice: "Aria (Neural)",
    channels: ["ai_call", "whatsapp", "sms"],
    gender: "F",
  },
  {
    id: "atlas",
    name: "Atlas Collections Agent",
    active: true,
    owner: "Priya Nair",
    languages: ["English"],
    voice: "Marcus (Neural)",
    channels: ["ai_call", "human_call"],
    gender: "M",
  },
  {
    id: "iris",
    name: "Iris Support Concierge",
    active: false,
    owner: "Diego Ruiz",
    languages: ["English", "Spanish"],
    voice: "Sofia (Neural)",
    channels: ["whatsapp", "sms"],
    gender: "F",
  },
  {
    id: "orion",
    name: "Orion Renewal Agent",
    active: true,
    owner: "Arsalaan Mohammed",
    languages: ["English", "Hindi", "Tamil"],
    voice: "Kai (Neural)",
    channels: ["ai_call", "whatsapp", "sms", "widget"],
    gender: "M",
  },
];

function AgentStatusPill({ agent }) {
  const cls = agent.active ? "status-pill status-active" : "status-pill status-inactive";
  return (
    <span className={cls}>
      <span className="dot" />
      {agent.active ? "Active" : "Inactive"}
    </span>
  );
}

function AgentChannelChips({ ids, max = 4 }) {
  const shown = ids.slice(0, max);
  const rest = ids.length - shown.length;
  return (
    <div className="channels">
      {shown.map((id) => (
        <span key={id} className="channel">
          <span className="dot" />
          {AGENT_CHANNELS[id] || id}
        </span>
      ))}
      {rest > 0 ? <span className="channel-more">+{rest}</span> : null}
    </div>
  );
}

export default function Agents({ onOpen }) {
  const [q, setQ] = useState("");
  const [view, setView] = useState("grid");
  const [menu, setMenu] = useState("");
  const rows = useMemo(
    () => AGENTS.filter((row) => row.name.toLowerCase().includes(q.toLowerCase()) || row.owner.toLowerCase().includes(q.toLowerCase())),
    [q],
  );

  return (
    <div className="page">
      <div className="toolbar">
        <div className="search-field">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3-3" />
          </svg>
          <input value={q} placeholder="Search agents" onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="view-toggle">
          <button type="button" className={view === "grid" ? "on" : ""} aria-label="Card view" onClick={() => setView("grid")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /></svg>
          </button>
          <button type="button" className={view === "list" ? "on" : ""} aria-label="List view" onClick={() => setView("list")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" /></svg>
          </button>
        </div>
        <button className="btn-primary" type="button">Create Agent</button>
      </div>
      {view === "list" ? (
        <div className="data-table">
          <table>
            <thead>
              <tr>
                <th>Agent</th>
                <th>Status</th>
                <th>Created by</th>
                <th>Language</th>
                <th>Voice</th>
                <th>Channels</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((agent) => (
                <tr key={agent.id}>
                  <td className="name" onClick={() => onOpen && onOpen(agent.id)}>{agent.name}</td>
                  <td><AgentStatusPill agent={agent} /></td>
                  <td>{agent.owner}</td>
                  <td>{agent.languages.join(", ")}</td>
                  <td>{agent.voice}</td>
                  <td><AgentChannelChips ids={agent.channels} max={2} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="agent-grid">
          {rows.map((agent) => (
            <article key={agent.id} className="agent-card">
              <div className="card-head">
                <div className="agent-avatar">{agent.gender}</div>
                <h3 className="min-w-0" onClick={() => onOpen && onOpen(agent.id)}>{agent.name}</h3>
                <AgentStatusPill agent={agent} />
                <button type="button" className="menu-btn" onClick={() => setMenu((cur) => (cur === agent.id ? "" : agent.id))}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="12" cy="5" r="1.6" />
                    <circle cx="12" cy="12" r="1.6" />
                    <circle cx="12" cy="19" r="1.6" />
                  </svg>
                </button>
                {menu === agent.id ? (
                  <div className="menu-pop">
                    <button type="button" onClick={() => onOpen && onOpen(agent.id)}>Edit</button>
                    <button type="button">Clone</button>
                    <button type="button">Copy ID</button>
                    <button type="button" className="danger">Delete</button>
                  </div>
                ) : null}
              </div>
              <div className="card-body">
                <dl className="meta-grid">
                  <div className="meta-cell">
                    <dt>Created by</dt>
                    <dd>{agent.owner}</dd>
                  </div>
                  <div className="meta-cell">
                    <dt>Language</dt>
                    <dd>{agent.languages.join(", ")}</dd>
                  </div>
                  <div className="meta-cell">
                    <dt>Voice</dt>
                    <dd>{agent.voice}</dd>
                  </div>
                </dl>
              </div>
              <div className="card-foot">
                <dl>
                  <div className="meta-cell">
                    <dt>Channels</dt>
                    <dd className="mt-2"><AgentChannelChips ids={agent.channels} /></dd>
                  </div>
                </dl>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
'''

AGENT_EDITOR_PAGE = r'''import { useMemo, useState } from "react";

const EDITOR_TABS = [
  { id: "basic", label: "AI Agent" },
  { id: "training", label: "Agent Training" },
  { id: "ai_call", label: "AI Call" },
  { id: "whatsapp_call", label: "AI Whatsapp Call" },
  { id: "human_call", label: "Human Call" },
  { id: "whatsapp", label: "AI Whatsapp Msg" },
  { id: "sms", label: "AI SMS" },
  { id: "widget", label: "AI Widget" },
];

const PROMPT_SECTIONS = ["Role & Identity", "Opening", "Qualification", "Objection Handling", "Compliance & Closure"];
const AGENT_NAMES = {
  nova: "Nova Sales Assistant",
  atlas: "Atlas Collections Agent",
  iris: "Iris Support Concierge",
  orion: "Orion Renewal Agent",
};
const STARTER_PROMPT = `## 1. Role & Identity
You are {{agent_name}}, a friendly and professional AI calling agent for {{company_name}}. You speak clearly, keep responses short, and always stay polite.

## 2. Opening
Greet the customer by name, introduce yourself as an AI assistant from {{company_name}}, and state the reason for the call in one sentence. Confirm you are speaking with the right person before proceeding.

## 3. Qualification
Ask up to three qualifying questions about the customer's current plan, usage, and interest level. Listen actively and acknowledge every answer before moving on.

## 4. Objection Handling
If the customer hesitates, acknowledge the concern, offer one relevant benefit, and ask a follow-up question. Never argue. Offer a callback at a better time if the customer is busy.

## 5. Compliance & Closure
Respect DND requests immediately. Summarize the agreed next steps, thank the customer for their time, and end the call politely.`;

const METHODS = [
  { id: "upload", label: "Upload Files", desc: "Upload past call recordings or transcripts. The AI will learn from real conversations and generate a system prompt." },
  { id: "custom", label: "Custom Prompt", desc: "Describe your agent's behavior, personality and instructions. The AI will generate a complete system prompt from your description." },
  { id: "script", label: "Call Script", desc: "Paste an existing call script or conversation template. The AI will convert it into a structured system prompt." },
];

export default function AgentEditor({ id = "nova", onBack }) {
  const [tab, setTab] = useState("training");
  const [section, setSection] = useState("Role & Identity");
  const [prompt, setPrompt] = useState(STARTER_PROMPT);
  const [builderOpen, setBuilderOpen] = useState(true);
  const [method, setMethod] = useState("upload");
  const [naturalness, setNaturalness] = useState("full");
  const [name, setName] = useState(AGENT_NAMES[id] || "Nova Sales Assistant");
  const [description, setDescription] = useState("Hindi Loan Collections Agent");
  const chars = prompt.length;

  const warning = useMemo(() => {
    if (chars >= 20000) return "Prompt is at the 20,000 character cap.";
    if (chars >= 18000) return "Approaching the 20,000 character cap.";
    return "";
  }, [chars]);

  return (
    <div className="page">
      <div className="editor-head">
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost" aria-label="Back to agents" onClick={() => onBack && onBack()}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M15 19l-7-7 7-7" /></svg>
          </button>
          <h1>Edit {name}</h1>
        </div>
        <div className="editor-actions">
          <button type="button" className="btn-secondary">Analyse Agent</button>
          <button type="button" className="btn-secondary">Test</button>
          <button type="button" className="btn-secondary">Test Logs</button>
          <button type="button" className="btn-blue">Update Agent</button>
        </div>
      </div>
      <div className="sense-tabs">
        {EDITOR_TABS.map((item) => (
          <button key={item.id} type="button" className={item.id === tab ? "on" : ""} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      {tab === "basic" ? (
        <section className="section-card">
          <header>
            <h2>Agent</h2>
            <p>Define your AI agent's identity and communication style.</p>
          </header>
          <div className="body">
            <div className="field-grid">
              <div className="field">
                <label htmlFor="agentName">Agent Name</label>
                <input id="agentName" className="field-input" value={name} onChange={(e) => setName(e.target.value)} />
                <p className="hint">Define the name customers will know your AI agent by.</p>
              </div>
              <div className="field">
                <label htmlFor="agentDescription">Agent Description</label>
                <input id="agentDescription" className="field-input" value={description} onChange={(e) => setDescription(e.target.value)} />
                <p className="hint">Add an internal name to help your team identify this agent.</p>
              </div>
            </div>
          </div>
        </section>
      ) : null}
      {tab === "training" ? (
        <div>
          <section className="prompt-card">
            <div className="prompt-toolbar">
              <div className="flex items-center gap-2">
                <strong>System Prompt</strong>
                <span className="badge badge-live">Published</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="badge badge-warn">Analysis Available</span>
                <button type="button" className="btn-blue">Publish</button>
              </div>
            </div>
            <p className="muted">This is the live prompt your agent uses. Edit and choose Publish Prompt to roll out changes.</p>
            <p className="muted mt-4" style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.05em" }}>JUMP TO SECTION</p>
            <div className="jumps">
              {PROMPT_SECTIONS.map((item) => (
                <button key={item} type="button" className={item === section ? "on" : ""} onClick={() => setSection(item)}>
                  {item}
                </button>
              ))}
            </div>
            <textarea className="prompt-box" value={prompt} maxLength={20000} onChange={(e) => setPrompt(e.target.value)} />
            <div className={warning ? "char-meta warn" : "char-meta"}>
              <span>Total characters {chars.toLocaleString()} / 20,000</span>
              <span>Total tokens ~{Math.ceil(chars / 4)}</span>
              {warning ? <span>{warning}</span> : null}
            </div>
          </section>
          <section className="builder">
            <div className="builder-head" onClick={() => setBuilderOpen((value) => !value)}>
              <div>
                <h3>Auto Prompt Builder</h3>
                <p className="muted">Generate a system prompt from files, instructions, or a call script.</p>
              </div>
              <span className="muted">{builderOpen ? "Hide" : "Show"}</span>
            </div>
            {builderOpen ? (
              <div className="body" style={{ padding: 20 }}>
                <div className="methods">
                  {METHODS.map((item) => (
                    <button key={item.id} type="button" className={item.id === method ? "method on" : "method"} onClick={() => setMethod(item.id)}>
                      <strong>{item.label}</strong>
                      <span>{item.desc}</span>
                    </button>
                  ))}
                </div>
                {method === "upload" ? (
                  <div className="dropzone mt-4">Drop recordings or transcripts here, or click to upload.</div>
                ) : null}
                {method === "custom" ? (
                  <textarea className="prompt-box mt-4" placeholder="e.g. Create a friendly support agent for a SaaS company that handles billing questions" />
                ) : null}
                {method === "script" ? (
                  <textarea className="prompt-box mt-4" placeholder="e.g. Agent: Good morning, thank you for calling Sense. How can I help you today?" />
                ) : null}
                <p className="muted mt-4">Conversation Naturalness</p>
                <div className="radio-row mt-2">
                  {["off", "moderate", "full"].map((item) => (
                    <button key={item} type="button" className={item === naturalness ? "on" : ""} onClick={() => setNaturalness(item)}>
                      {item === "full" ? "Full (recommended)" : item[0].toUpperCase() + item.slice(1)}
                    </button>
                  ))}
                </div>
                <button type="button" className="btn-primary w-full mt-4">{method === "upload" ? "Upload and Process" : "Generate Prompt"}</button>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
      {tab !== "basic" && tab !== "training" ? (
        <section className="section-card">
          <header>
            <h2>{EDITOR_TABS.find((item) => item.id === tab).label}</h2>
            <p>Channel settings for this agent. Prompt a redesign to change layout, copy, or controls.</p>
          </header>
          <div className="body">
            <p className="muted">This tab is a fixture of the live Sense agent editor.</p>
          </div>
        </section>
      ) : null}
    </div>
  );
}
'''

PLACEHOLDER_PAGE = r'''export default function Placeholder({ title }) {
  return (
    <div className="page">
      <div className="section-card">
        <header>
          <h2>{title}</h2>
          <p>This is the live Sense shell. Prompt a redesign of this screen; keep the sidebar and top bar.</p>
        </header>
        <div className="body">
          <p className="text-sm">Fixture page so you can prototype on top of the current product, not a blank canvas.</p>
        </div>
      </div>
    </div>
  );
}
'''

APP_JSX = r'''import { useState } from "react";
import SenseShell from "./components/SenseShell";
import Campaigns from "./pages/Campaigns";
import Agents from "./pages/Agents";
import AgentEditor from "./pages/AgentEditor";
import Analytics from "./pages/Analytics";
import Customers from "./pages/Customers";
import Tools from "./pages/Tools";
import KnowledgeBase from "./pages/KnowledgeBase";
import HumanAgent from "./pages/HumanAgent";
import Settings from "./pages/Settings";
import CampaignLeads from "./pages/CampaignLeads";
import AgentAnalysis from "./pages/AgentAnalysis";
import Placeholder from "./pages/Placeholder";

const TITLES = {
  campaigns: "Campaigns",
  analytics: "Analytics",
  customers: "Customers",
  agents: "AI Agents",
  tools: "AI Tools",
  kb: "Knowledge Base",
  human: "Human Agent",
  settings: "Settings",
  "campaign-leads": "Campaigns",
  "agent-edit": "AI Agents",
  "agent-analysis": "AI Agents",
};

const SHELL_ACTIVE = {
  "agent-edit": "agents",
  "agent-analysis": "agents",
  "campaign-leads": "campaigns",
};

export default function App() {
  const [route, setRoute] = useState({ name: "campaigns", agentId: "nova", campaign: "Home Loan Winback" });
  const active = SHELL_ACTIVE[route.name] || route.name;
  const title = TITLES[route.name] || "Sense";

  let page = <Placeholder title={title} />;
  if (route.name === "campaigns") {
    page = (
      <Campaigns
        onOpenLeads={(row) => setRoute({ name: "campaign-leads", campaign: row.name })}
        onOpenAnalytics={() => setRoute({ name: "analytics" })}
        onOpenAnalysis={(row) => setRoute({ name: "agent-analysis", agentId: row.agent })}
      />
    );
  } else if (route.name === "analytics") {
    page = <Analytics />;
  } else if (route.name === "customers") {
    page = <Customers />;
  } else if (route.name === "agents") {
    page = <Agents onOpen={(agentId) => setRoute({ name: "agent-edit", agentId })} />;
  } else if (route.name === "agent-edit") {
    page = <AgentEditor id={route.agentId} onBack={() => setRoute({ name: "agents" })} />;
  } else if (route.name === "agent-analysis") {
    page = <AgentAnalysis name={route.agentId} onBack={() => setRoute({ name: "agents" })} />;
  } else if (route.name === "campaign-leads") {
    page = <CampaignLeads campaign={route.campaign} onBack={() => setRoute({ name: "campaigns" })} />;
  } else if (route.name === "tools") {
    page = <Tools />;
  } else if (route.name === "kb") {
    page = <KnowledgeBase />;
  } else if (route.name === "human") {
    page = <HumanAgent />;
  } else if (route.name === "settings") {
    page = <Settings />;
  }

  return (
    <SenseShell active={active} title={title} onNavigate={(name) => setRoute({ name })}>
      {page}
    </SenseShell>
  );
}
'''


def placeholder_page(slug: str, label: str) -> str:
    return f'''export default function {slug}() {{
  return (
    <div className="page">
      <div className="section-card">
        <header>
          <h2>{label}</h2>
          <p>Prompt a redesign of this Sense screen. Keep the product shell; change this page.</p>
        </header>
        <div className="body">
          <button className="btn-primary" type="button">Primary</button>
        </div>
      </div>
    </div>
  );
}}
'''


def app_for(slug: str, title: str, active: str = "campaigns") -> str:
    return f'''import SenseShell from "./components/SenseShell";
import Screen from "./pages/{slug}";

export default function App() {{
  return (
    <SenseShell active="{active}" title="{title}" onNavigate={{() => {{}}}}>
      <Screen />
    </SenseShell>
  );
}}
'''
