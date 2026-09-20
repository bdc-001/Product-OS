"""Lovable Sense screens for the prototype sandbox. Do not import go_services."""

ANALYTICS_PAGE = r'''import { useState } from "react";

const ANALYTICS_TABS = ["Outcome", "Activity", "Spend", "Reports"];

const OUTCOME_KPIS = [
  { label: "Attempted Leads", value: "12,480", trend: "+6.2%", up: true },
  { label: "Connected Leads", value: "7,214", trend: "+3.1%", up: true },
  { label: "% Goal Achieved", value: "41.8%", sub: "3,018 leads", trend: "-1.4%", up: false },
  { label: "% Interested Leads", value: "28.6%", sub: "2,064 leads", trend: "+2.0%", up: true },
];

const OUTCOME_BARS = [
  { title: "Lead state", rows: [{ n: "Active", v: 42 }, { n: "Completed", v: 28 }, { n: "Paused", v: 18 }, { n: "Opted out", v: 12 }] },
  { title: "Qualification", rows: [{ n: "Qualified", v: 54 }, { n: "Pending", v: 31 }, { n: "Unqualified", v: 15 }] },
  { title: "Interest", rows: [{ n: "Hot", v: 22 }, { n: "Warm", v: 31 }, { n: "Cold", v: 27 }, { n: "Not interested", v: 20 }] },
];

const ACTIVITY_KPIS = [
  { label: "Attempted Leads", value: "9,102" },
  { label: "Connected Leads", value: "5,440" },
  { label: "Lead Connectivity", value: "59.8%" },
  { label: "Avg Talk Time", value: "84s", sub: "Per connected call" },
  { label: "No Answer", value: "1,266", sub: "Unanswered dials" },
];

const ACTIVITY_CHANNELS = [
  { ch: "AI Call", attempts: 6200, connected: 3410, rate: "55%" },
  { ch: "WhatsApp", attempts: 2100, connected: 1480, rate: "70%" },
  { ch: "SMS", attempts: 980, connected: 410, rate: "42%" },
  { ch: "Human Call", attempts: 420, connected: 140, rate: "33%" },
];

const HEAT = [12, 18, 22, 40, 55, 70, 64, 48, 36, 28, 20, 14];

const SPEND_KPIS = [
  { label: "Total Spend", value: "₹4.82L", trend: "+4.8%", up: true },
  { label: "Cost / Connected Lead", value: "₹66.80", trend: "-2.1%", up: true },
  { label: "Cost / Goal Achieved", value: "₹159.70", trend: "+1.2%", up: false },
  { label: "Cost / Interested Lead", value: "₹233.40", trend: "-0.6%", up: true },
];

const USAGE_ROWS = [
  { n: "Call pulses", v: "1.24M", pct: 78 },
  { n: "WhatsApp messages", v: "186k", pct: 54 },
  { n: "SMS", v: "92k", pct: 31 },
  { n: "LLM tokens", v: "48.2M", pct: 61 },
];

const REPORT_ITEMS = [
  { name: "Lead analytics", desc: "Outcomes, interest and qualification across campaigns." },
  { name: "Call analytics", desc: "Connectivity, talk time and disconnect reasons." },
  { name: "WhatsApp analytics", desc: "Template delivery, reads and replies." },
  { name: "Campaign performance", desc: "Reach, cost and goal completion by campaign." },
  { name: "Spend & billing", desc: "Channel cost, pulses and invoice-ready usage." },
  { name: "Compliance audit", desc: "DND, opt-outs and recording consent." },
];

function MetricCard({ item }) {
  return (
    <article className="metric-card">
      <p className="metric-label">{item.label}</p>
      <p className="metric-value">{item.value}</p>
      {item.sub ? <p className="muted">{item.sub}</p> : null}
      {item.trend ? <p className={item.up ? "trend up" : "trend down"}>{item.trend} vs last period</p> : null}
    </article>
  );
}

function BarBlock({ block }) {
  return (
    <article className="chart-card">
      <h3>{block.title}</h3>
      {block.rows.map((row) => (
        <div key={row.n} className="bar-row">
          <span>{row.n}</span>
          <div className="bar-track"><span style={{ width: row.v + "%" }} /></div>
          <strong>{row.v}%</strong>
        </div>
      ))}
    </article>
  );
}

export default function Analytics() {
  const [tab, setTab] = useState("Outcome");
  return (
    <div className="page">
      <div className="seg-tabs">
        {ANALYTICS_TABS.map((item) => (
          <button key={item} type="button" className={item === tab ? "on" : ""} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </div>
      <div className="toolbar mt-4">
        <select className="field-input" defaultValue="all" style={{ maxWidth: 220 }}>
          <option value="all">All campaigns</option>
          <option>Home Loan Winback</option>
          <option>Q3 Renewal Drive</option>
        </select>
        <select className="field-input" defaultValue="30" style={{ maxWidth: 180 }}>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>
      </div>
      {tab === "Outcome" ? (
        <div>
          <h2 className="section-title">Lead Outcomes</h2>
          <p className="muted">Reach, connectivity and goal completion for the selected filters.</p>
          <div className="metric-grid mt-4">
            {OUTCOME_KPIS.map((item) => <MetricCard key={item.label} item={item} />)}
          </div>
          <h2 className="section-title mt-4">Lead Distribution</h2>
          <div className="chart-grid mt-4">
            {OUTCOME_BARS.map((block) => <BarBlock key={block.title} block={block} />)}
          </div>
        </div>
      ) : null}
      {tab === "Activity" ? (
        <div>
          <h2 className="section-title">Engagement Overview</h2>
          <div className="metric-grid five mt-4">
            {ACTIVITY_KPIS.map((item) => <MetricCard key={item.label} item={item} />)}
          </div>
          <h2 className="section-title mt-4">Channel Performance</h2>
          <div className="data-table">
            <table>
              <thead><tr><th>Channel</th><th>Attempts</th><th>Connected</th><th>Rate</th></tr></thead>
              <tbody>
                {ACTIVITY_CHANNELS.map((row) => (
                  <tr key={row.ch}><td>{row.ch}</td><td>{row.attempts.toLocaleString()}</td><td>{row.connected.toLocaleString()}</td><td>{row.rate}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2 className="section-title mt-4">Best time to connect</h2>
          <div className="heatmap">
            {HEAT.map((v, i) => (
              <span key={i} style={{ opacity: 0.25 + v / 100 }} title={v + "%"} />
            ))}
          </div>
        </div>
      ) : null}
      {tab === "Spend" ? (
        <div>
          <h2 className="section-title">Cost Efficiency</h2>
          <div className="metric-grid mt-4">
            {SPEND_KPIS.map((item) => <MetricCard key={item.label} item={item} />)}
          </div>
          <h2 className="section-title mt-4">Usage Tracking</h2>
          <div className="chart-grid mt-4">
            {USAGE_ROWS.map((row) => (
              <article key={row.n} className="chart-card">
                <h3>{row.n}</h3>
                <p className="metric-value">{row.v}</p>
                <div className="bar-track mt-2"><span style={{ width: row.pct + "%" }} /></div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
      {tab === "Reports" ? (
        <div className="agent-grid" style={{ marginTop: 24 }}>
          {REPORT_ITEMS.map((item) => (
            <article key={item.name} className="section-card">
              <header>
                <h2>{item.name}</h2>
                <p>{item.desc}</p>
              </header>
              <div className="body">
                <button type="button" className="btn-secondary">Download CSV</button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}
'''

CUSTOMERS_PAGE = r'''import { useMemo, useState } from "react";

const CUSTOMER_ROWS = [
  { id: "L-1021", name: "Meera Iyer", phone: "+91 98200 44117", campaign: "Home Loan Winback", state: "active", interest: "hot", owner: "AI", last: "2h ago" },
  { id: "L-1022", name: "Rohit Khanna", phone: "+91 99301 77842", campaign: "Q3 Renewal Drive", state: "completed", interest: "warm", owner: "Human", last: "Yesterday" },
  { id: "L-1023", name: "Sana Qureshi", phone: "+91 90040 12665", campaign: "Personal Loan Top Up", state: "snoozed", interest: "cold", owner: "AI", last: "3d ago" },
  { id: "L-1024", name: "Arjun Patel", phone: "+91 88795 30214", campaign: "Credit Card Upgrade", state: "paused", interest: "not_interested", owner: "Human", last: "5d ago" },
  { id: "L-1025", name: "Nikita Rao", phone: "+91 80471 20011", campaign: "Insurance Renewal Reminder", state: "active", interest: "hot", owner: "AI", last: "12m ago" },
  { id: "L-1026", name: "Vikram Shah", phone: "+91 80675 41190", campaign: "Fresh Lead Qualification", state: "opted_out", interest: "not_connected", owner: "AI", last: "1w ago" },
  { id: "L-1027", name: "Pooja Nair", phone: "+91 98211 33420", campaign: "Home Loan Winback", state: "active", interest: "warm", owner: "Human", last: "4h ago" },
  { id: "L-1028", name: "Farhan Ali", phone: "+91 98190 22014", campaign: "Q3 Renewal Drive", state: "archived", interest: "cold", owner: "AI", last: "2w ago" },
];

function LeadStatePill({ state }) {
  return <span className={"lead-pill state-" + state}>{state.replace("_", " ")}</span>;
}

function InterestPill({ value }) {
  return <span className={"lead-pill interest-" + value}>{value.replace("_", " ")}</span>;
}

export default function Customers() {
  const [q, setQ] = useState("");
  const [menu, setMenu] = useState(false);
  const rows = useMemo(
    () => CUSTOMER_ROWS.filter((row) => (row.name + row.phone + row.campaign).toLowerCase().includes(q.toLowerCase())),
    [q],
  );
  return (
    <div className="page">
      <div className="toolbar">
        <div className="search-field">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" /></svg>
          <input value={q} placeholder="Search customers" onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="relative">
          <button type="button" className="btn-primary" onClick={() => setMenu((v) => !v)}>Add Leads</button>
          {menu ? (
            <div className="menu-pop" style={{ right: 0, top: 40 }}>
              <button type="button">Single Lead</button>
              <button type="button">Bulk Upload</button>
            </div>
          ) : null}
        </div>
      </div>
      <div className="data-table">
        <table>
          <thead>
            <tr>
              <th>Customer</th>
              <th>Phone</th>
              <th>Campaign</th>
              <th>State</th>
              <th>Interest</th>
              <th>Owner</th>
              <th>Last interaction</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="name">{row.name}<div className="muted">{row.id}</div></td>
                <td>{row.phone}</td>
                <td>{row.campaign}</td>
                <td><LeadStatePill state={row.state} /></td>
                <td><InterestPill value={row.interest} /></td>
                <td>{row.owner}</td>
                <td>{row.last}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
'''

TOOLS_PAGE = r'''import { useMemo, useState } from "react";

const TOOL_ITEMS = [
  { id: "crm_lookup", name: "CRM Lookup", desc: "Fetch customer records and past interactions.", method: "GET", cat: "Custom Actions" },
  { id: "order_status", name: "Order Status", desc: "Check live order and shipment status.", method: "GET", cat: "Custom Actions" },
  { id: "payment_link", name: "Send Payment Link", desc: "Generate and share a secure payment link.", method: "POST", cat: "Custom Actions" },
  { id: "knowledge_base", name: "Knowledge Base Search", desc: "Answer questions from your uploaded documents.", method: "GET", cat: "Custom Actions" },
  { id: "transfer_agent", name: "Transfer to Human Agent", desc: "Hand the live call over to a human representative.", method: "TRANSFER", cat: "Call Transfer Tools" },
  { id: "transfer_supervisor", name: "Escalate to Supervisor", desc: "Transfer the call to a supervisor queue.", method: "TRANSFER", cat: "Call Transfer Tools" },
  { id: "emi_calculator", name: "EMI Calculator", desc: "Calculate monthly instalments during the conversation.", method: "POST", cat: "Calculation Tools" },
  { id: "discount_calculator", name: "Discount Calculator", desc: "Compute eligible discounts on the current order.", method: "POST", cat: "Calculation Tools" },
  { id: "send_sms", name: "Send SMS", desc: "Send an SMS message to the lead.", method: "SMS", cat: "SMS Tools" },
  { id: "send_whatsapp", name: "Send WhatsApp Message", desc: "Send a templated WhatsApp message post-call.", method: "WHATSAPP", cat: "WhatsApp Tools" },
  { id: "calendar_booking", name: "Calendar Booking", desc: "Book a callback on the advisor calendar.", method: "POST", cat: "Custom Actions" },
];

export default function Tools() {
  const [q, setQ] = useState("");
  const groups = useMemo(() => {
    const rows = TOOL_ITEMS.filter((item) => (item.name + item.desc).toLowerCase().includes(q.toLowerCase()));
    const map = {};
    rows.forEach((item) => {
      map[item.cat] = map[item.cat] || [];
      map[item.cat].push(item);
    });
    return Object.keys(map).map((cat) => ({ cat, items: map[cat] }));
  }, [q]);
  return (
    <div className="page">
      <div className="toolbar">
        <div className="search-field">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" /></svg>
          <input value={q} placeholder="Search tools" onChange={(e) => setQ(e.target.value)} />
        </div>
        <button type="button" className="btn-primary">Create Tool</button>
      </div>
      {groups.map((group) => (
        <section key={group.cat} className="mt-4">
          <h2 className="section-title">{group.cat}</h2>
          <div className="agent-grid" style={{ marginTop: 16 }}>
            {group.items.map((item) => (
              <article key={item.id} className="tool-card">
                <div className="flex items-center justify-between gap-2">
                  <h3>{item.name}</h3>
                  <span className="method-badge">{item.method}</span>
                </div>
                <p className="muted mt-2">{item.desc}</p>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
'''

KNOWLEDGE_PAGE = r'''import { useState } from "react";

const KB_FOLDERS = [
  {
    id: "policies",
    name: "Policies",
    files: ["DND handling.md", "Collections compliance.md", "Recording consent.md"],
  },
  {
    id: "scripts",
    name: "Call scripts",
    files: ["Home loan opener.md", "Renewal objection handling.md", "Payment reminder.md"],
  },
  {
    id: "product",
    name: "Product docs",
    files: ["EMI calculator FAQ.md", "Insurance riders.md", "Credit card upgrade matrix.md"],
  },
];

export default function KnowledgeBase() {
  const [open, setOpen] = useState("policies");
  const folder = KB_FOLDERS.find((item) => item.id === open) || KB_FOLDERS[0];
  return (
    <div className="page">
      <div className="toolbar">
        <div className="search-field">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" /></svg>
          <input placeholder="Search knowledge base" />
        </div>
        <button type="button" className="btn-primary">Upload file</button>
      </div>
      <div className="kb-layout">
        <aside className="kb-tree">
          {KB_FOLDERS.map((item) => (
            <button key={item.id} type="button" className={item.id === open ? "on" : ""} onClick={() => setOpen(item.id)}>
              {item.name}
              <span className="muted">{item.files.length}</span>
            </button>
          ))}
        </aside>
        <div className="section-card" style={{ margin: 0 }}>
          <header>
            <h2>{folder.name}</h2>
            <p>Documents the agent can retrieve during a conversation.</p>
          </header>
          <div className="body">
            {folder.files.map((file) => (
              <div key={file} className="kb-file">{file}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
'''

HUMAN_PAGE = r'''import { useState } from "react";

const HUMAN_QUEUE = [
  { id: "L-1021", name: "Meera Iyer", campaign: "Home Loan Winback", interest: "Hot", wait: "00:42", reason: "Asked for a human advisor" },
  { id: "L-1027", name: "Pooja Nair", campaign: "Home Loan Winback", interest: "Warm", wait: "01:18", reason: "Payment dispute" },
  { id: "L-1022", name: "Rohit Khanna", campaign: "Q3 Renewal Drive", interest: "Warm", wait: "02:05", reason: "High-value renewal" },
  { id: "L-1030", name: "Kabir Das", campaign: "Collections Recovery", interest: "Cold", wait: "03:11", reason: "Requested callback" },
];

export default function HumanAgent() {
  const [inShift, setInShift] = useState(true);
  const [active, setActive] = useState(HUMAN_QUEUE[0]);
  return (
    <div className="page">
      <div className="toolbar">
        <span className={inShift ? "status-pill status-active" : "status-pill status-inactive"}>
          <span className="dot" />
          {inShift ? "Checked in" : "Offline"}
        </span>
        <button type="button" className={inShift ? "btn-secondary" : "btn-primary"} onClick={() => setInShift((v) => !v)}>
          {inShift ? "Check out" : "Check in"}
        </button>
      </div>
      {!inShift ? (
        <div className="empty">
          <h2 className="font-semibold">Start your shift</h2>
          <p className="muted mt-2">Check in to receive AI-to-human handoffs and work the lead queue.</p>
        </div>
      ) : (
        <div className="human-layout">
          <aside className="human-queue">
            {HUMAN_QUEUE.map((row) => (
              <button key={row.id} type="button" className={row.id === active.id ? "on" : ""} onClick={() => setActive(row)}>
                <strong>{row.name}</strong>
                <span className="muted">{row.campaign}</span>
                <span className="muted">{row.wait}</span>
              </button>
            ))}
          </aside>
          <section className="section-card" style={{ margin: 0 }}>
            <header>
              <h2>{active.name}</h2>
              <p>{active.campaign} · {active.interest} · {active.id}</p>
            </header>
            <div className="body">
              <p className="muted">Handoff reason</p>
              <p className="mt-2">{active.reason}</p>
              <div className="flex gap-2 mt-4">
                <button type="button" className="btn-primary">Start call</button>
                <button type="button" className="btn-secondary">Disposition</button>
                <button type="button" className="btn-secondary">Snooze</button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
'''

SETTINGS_PAGE = r'''import { useState } from "react";

const SETTINGS_NAV = [
  { group: "Organization", items: ["General", "Profile", "Billing", "Infrastructure"] },
  { group: "Administration", items: ["User Management", "Roles & Permissions", "Team Management", "PII Masking"] },
  { group: "Platform Config", items: ["Phone Numbers", "Voice Cloning", "Text normalization", "Dispositions", "Lead Stages", "Lead Routing", "Entities", "Variables", "Custom Metrics"] },
  { group: "Integrations", items: ["Integrations", "API Credentials"] },
];

const PHONE_ROWS = [
  { number: "+91 80471 20011", type: "Landline", connectivity: 96 },
  { number: "+91 98200 44117", type: "Mobile", connectivity: 74 },
  { number: "1800 266 0134", type: "Toll Free", connectivity: 99 },
  { number: "+91 99301 77842", type: "Mobile", connectivity: 42 },
  { number: "1860 500 9042", type: "Special Series", connectivity: 78 },
];

const USER_ROWS = [
  { name: "Aarav Sharma", email: "aarav@sense.io", role: "Administrator", active: true },
  { name: "Diana Fernandes", email: "diana@sense.io", role: "Campaign Manager", active: true },
  { name: "Marcus Lee", email: "marcus@sense.io", role: "Agent", active: true },
  { name: "Priya Nair", email: "priya@sense.io", role: "Analyst", active: false },
];

export default function Settings() {
  const [section, setSection] = useState("General");
  return (
    <div className="page settings-layout">
      <aside className="settings-nav">
        {SETTINGS_NAV.map((group) => (
          <div key={group.group}>
            <p className="sense-nav-label">{group.group}</p>
            {group.items.map((item) => (
              <button
                key={item}
                type="button"
                className={item === section ? (["User Management", "Roles & Permissions", "Team Management", "PII Masking"].includes(item) ? "on admin" : "on") : ""}
                onClick={() => setSection(item)}
              >
                {item}
              </button>
            ))}
          </div>
        ))}
      </aside>
      <div>
        {section === "General" ? (
          <section className="section-card">
            <header>
              <h2>General</h2>
              <p>Workspace identity and defaults.</p>
            </header>
            <div className="body field-grid">
              <div className="field">
                <label>Organization name</label>
                <input className="field-input" defaultValue="Sense" />
              </div>
              <div className="field">
                <label>Timezone</label>
                <input className="field-input" defaultValue="Asia/Kolkata" />
              </div>
            </div>
          </section>
        ) : null}
        {section === "Phone Numbers" ? (
          <section className="section-card">
            <header>
              <h2>Phone Numbers</h2>
              <p>Numbers used for outbound AI and human calls.</p>
            </header>
            <div className="body">
              <div className="data-table" style={{ marginTop: 0 }}>
                <table>
                  <thead><tr><th>Number</th><th>Type</th><th>Connectivity</th></tr></thead>
                  <tbody>
                    {PHONE_ROWS.map((row) => (
                      <tr key={row.number}><td>{row.number}</td><td>{row.type}</td><td>{row.connectivity}%</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        ) : null}
        {section === "User Management" ? (
          <section className="section-card">
            <header>
              <h2>User Management</h2>
              <p>People who can operate this workspace.</p>
            </header>
            <div className="body">
              <div className="data-table" style={{ marginTop: 0 }}>
                <table>
                  <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead>
                  <tbody>
                    {USER_ROWS.map((row) => (
                      <tr key={row.email}>
                        <td>{row.name}</td>
                        <td>{row.email}</td>
                        <td>{row.role}</td>
                        <td>{row.active ? "Active" : "Inactive"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        ) : null}
        {section === "Billing" ? (
          <section className="section-card">
            <header>
              <h2>Billing</h2>
              <p>Current plan and usage.</p>
            </header>
            <div className="body">
              <p className="metric-value">Growth</p>
              <p className="muted mt-2">Includes AI calling, WhatsApp, SMS and 12k connected leads / month.</p>
              <button type="button" className="btn-primary mt-4">Manage plan</button>
            </div>
          </section>
        ) : null}
        {section === "PII Masking" ? (
          <section className="section-card">
            <header>
              <h2>PII Masking</h2>
              <p>Hide sensitive values from agent transcripts and lead views.</p>
            </header>
            <div className="body">
              <label className="flex items-center gap-2">
                <input type="checkbox" defaultChecked />
                Mask phone numbers, PAN and account IDs
              </label>
            </div>
          </section>
        ) : null}
        {section !== "General" && section !== "Phone Numbers" && section !== "User Management" && section !== "Billing" && section !== "PII Masking" ? (
          <section className="section-card">
            <header>
              <h2>{section}</h2>
              <p>This module is part of the Sense settings suite.</p>
            </header>
            <div className="body">
              <div className="empty" style={{ marginTop: 0 }}>
                <p className="muted">Nothing configured yet for this workspace.</p>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
'''

CAMPAIGN_LEADS_PAGE = r'''export default function CampaignLeads({ campaign = "Home Loan Winback", onBack }) {
  const rows = [
    { name: "Meera Iyer", state: "active", interest: "hot", owner: "AI" },
    { name: "Pooja Nair", state: "active", interest: "warm", owner: "Human" },
    { name: "Farhan Ali", state: "paused", interest: "cold", owner: "AI" },
  ];
  return (
    <div className="page">
      <div className="editor-head">
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost" onClick={() => onBack && onBack()} aria-label="Back to campaigns">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M15 19l-7-7 7-7" /></svg>
          </button>
          <h1>{campaign} leads</h1>
        </div>
        <button type="button" className="btn-primary">Add Leads</button>
      </div>
      <div className="data-table">
        <table>
          <thead><tr><th>Customer</th><th>State</th><th>Interest</th><th>Owner</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name}><td className="name">{row.name}</td><td>{row.state}</td><td>{row.interest}</td><td>{row.owner}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
'''

AGENT_ANALYSIS_PAGE = r'''export default function AgentAnalysis({ name = "Nova Sales Assistant", onBack }) {
  const scores = [
    { n: "Intent & Context Understanding", v: 86 },
    { n: "Conversation Management", v: 78 },
    { n: "Response Quality", v: 81 },
    { n: "Knowledge & Grounding", v: 74 },
    { n: "Workflow Execution", v: 69 },
    { n: "Tone & Empathy", v: 88 },
  ];
  return (
    <div className="page">
      <div className="editor-head">
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost" onClick={() => onBack && onBack()} aria-label="Back to agents">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M15 19l-7-7 7-7" /></svg>
          </button>
          <h1>{name} analysis</h1>
        </div>
        <button type="button" className="btn-secondary">Last 30 days</button>
      </div>
      <div className="metric-grid">
        <article className="metric-card"><p className="metric-label">Overall score</p><p className="metric-value">79</p></article>
        <article className="metric-card"><p className="metric-label">Interactions</p><p className="metric-value">1,248</p></article>
        <article className="metric-card"><p className="metric-label">Goal rate</p><p className="metric-value">41.8%</p></article>
        <article className="metric-card"><p className="metric-label">Handoffs</p><p className="metric-value">6.2%</p></article>
      </div>
      <h2 className="section-title mt-4">Parameter scores</h2>
      <div className="chart-card mt-4">
        {scores.map((row) => (
          <div key={row.n} className="bar-row">
            <span>{row.n}</span>
            <div className="bar-track"><span style={{ width: row.v + "%" }} /></div>
            <strong>{row.v}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
'''
