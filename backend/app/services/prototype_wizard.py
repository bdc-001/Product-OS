"""Campaign create wizard for the prototype sandbox. Do not import go_services."""

CAMPAIGN_WIZARD = r'''import { useMemo, useState } from "react";

const WIZ_TABS = [
  { id: "details", label: "Campaign Details" },
  { id: "entities", label: "Lead Entities" },
  { id: "metrics", label: "Lead Metrics" },
  { id: "channels", label: "Channel Config" },
  { id: "state", label: "Campaign State" },
  { id: "intake", label: "Lead Intake" },
  { id: "crm", label: "CRM" },
  { id: "dispositions", label: "Dispositions" },
  { id: "variables", label: "Custom Variables" },
  { id: "handoff", label: "AI ↔ Human Handoff" },
  { id: "webhooks", label: "Webhooks" },
];

const WIZ_AGENTS = [
  { name: "Nova Sales Assistant", langs: ["English", "Hindi"], channels: ["ai_call", "whatsapp", "sms"] },
  { name: "Atlas Collections Agent", langs: ["English"], channels: ["ai_call", "human_call"] },
  { name: "Iris Support Concierge", langs: ["English", "Spanish"], channels: ["whatsapp", "sms", "widget"] },
  { name: "Orion Renewal Agent", langs: ["English", "Hindi", "Marathi"], channels: ["ai_call", "sms", "whatsapp"] },
];

const WIZ_CHANNEL_LABELS = {
  ai_call: "AI Call",
  human_call: "Human Call",
  whatsapp: "WhatsApp",
  sms: "SMS",
  widget: "Website Widget",
};

const WIZ_TIMEZONES = ["Asia/Kolkata", "Asia/Dubai", "America/New_York", "Europe/London"];
const WIZ_HOURS = ["08:00", "09:00", "10:00", "18:00", "20:00", "21:00"];
const WIZ_ENTITIES = ["Full name", "Phone", "Email", "City", "Loan amount", "EMI due date", "Policy number", "Preferred language"];
const WIZ_METRICS = ["Interest level", "Lead state", "Qualification", "Goal achieved", "Talk time", "Attempts"];
const WIZ_DISPOSITIONS = ["Interested", "Callback", "Not interested", "Wrong number", "DND", "Payment promised", "Already paid"];
const WIZ_VARS = ["{{customer_name}}", "{{campaign_name}}", "{{due_amount}}", "{{callback_slot}}", "{{agent_name}}"];

function WizardCard({ title, subtitle, children }) {
  return (
    <section className="section-card">
      <header>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </header>
      <div className="body">{children}</div>
    </section>
  );
}

export default function CampaignWizard({ type = "smart_ai", onBack, onSave }) {
  const smart = type === "smart_ai";
  const [tab, setTab] = useState("details");
  const [form, setForm] = useState({
    name: smart ? "Home Loan Winback" : "Missed Payment Recovery",
    description: "Re-engage customers who dropped after quoting and convert interested leads.",
    agent: smart ? "Nova Sales Assistant" : "Atlas Collections Agent",
    language: "English",
    timezone: "Asia/Kolkata",
    dndFrom: "21:00",
    dndTo: "08:00",
    days: 14,
    inbound: true,
    firstTouch: "ai_call",
    systemMessage: "You are calling on behalf of Sense to help the customer complete an unfinished application.",
    crm: "Salesforce",
    webhook: "https://hooks.sense.example/campaigns",
  });
  const [picked, setPicked] = useState(WIZ_ENTITIES.slice(0, 5));
  const [metrics, setMetrics] = useState(WIZ_METRICS.slice(0, 4));
  const [disps, setDisps] = useState(WIZ_DISPOSITIONS.slice(0, 5));
  const [vars, setVars] = useState(WIZ_VARS.slice(0, 3));
  const [handoff, setHandoff] = useState(true);
  const agent = WIZ_AGENTS.find((item) => item.name === form.agent) || WIZ_AGENTS[0];
  const idx = WIZ_TABS.findIndex((item) => item.id === tab);

  function set(key, value) {
    setForm((cur) => Object.assign({}, cur, { [key]: value }));
  }

  function toggleList(list, setList, item) {
    setList(list.includes(item) ? list.filter((row) => row !== item) : list.concat([item]));
  }

  const errors = useMemo(() => {
    const next = {};
    if (!form.name.trim()) next.name = "Campaign name is required.";
    if (!form.agent) next.agent = "Pick an AI agent.";
    if (!form.systemMessage.trim()) next.systemMessage = "Add a system message.";
    return next;
  }, [form]);

  return (
    <div className="page">
      <div className="editor-head">
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost" aria-label="Back to campaigns" onClick={() => onBack && onBack()}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div>
            <h1>{form.name || "New campaign"}</h1>
            <p className="muted">{smart ? "Smart AI Campaign" : "Rule Based Campaign"}</p>
          </div>
        </div>
        <div className="editor-actions">
          <button type="button" className="btn-secondary" onClick={() => onBack && onBack()}>Cancel</button>
          <button type="button" className="btn-blue" onClick={() => onSave && onSave(form)}>Create Campaign</button>
        </div>
      </div>
      <div className="wizard-layout">
        <aside className="wizard-rail">
          {WIZ_TABS.map((item, i) => (
            <button
              key={item.id}
              type="button"
              className={item.id === tab ? "on" : ""}
              onClick={() => setTab(item.id)}
            >
              <span className="step">{i + 1}</span>
              {item.label}
            </button>
          ))}
        </aside>
        <div>
          {tab === "details" ? (
            <WizardCard title="Campaign Details" subtitle="Name, agent, language and when this campaign is allowed to reach leads.">
              <div className="field-grid">
                <div className="field">
                  <label>Campaign name <span className="req">*</span></label>
                  <input className="field-input" value={form.name} onChange={(e) => set("name", e.target.value)} />
                  {errors.name ? <p className="hint" style={{ color: "#b91c1c" }}>{errors.name}</p> : null}
                </div>
                <div className="field">
                  <label>AI agent <span className="req">*</span></label>
                  <select className="field-input" value={form.agent} onChange={(e) => set("agent", e.target.value)}>
                    {WIZ_AGENTS.map((item) => (
                      <option key={item.name}>{item.name}</option>
                    ))}
                  </select>
                </div>
                <div className="field" style={{ gridColumn: "1 / -1" }}>
                  <label>Description</label>
                  <textarea className="field-input" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
                </div>
                <div className="field">
                  <label>Language</label>
                  <select className="field-input" value={form.language} onChange={(e) => set("language", e.target.value)}>
                    {agent.langs.map((lang) => <option key={lang}>{lang}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Timezone</label>
                  <select className="field-input" value={form.timezone} onChange={(e) => set("timezone", e.target.value)}>
                    {WIZ_TIMEZONES.map((tz) => <option key={tz}>{tz}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>DND from</label>
                  <select className="field-input" value={form.dndFrom} onChange={(e) => set("dndFrom", e.target.value)}>
                    {WIZ_HOURS.map((h) => <option key={h}>{h}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>DND to</label>
                  <select className="field-input" value={form.dndTo} onChange={(e) => set("dndTo", e.target.value)}>
                    {WIZ_HOURS.map((h) => <option key={"to" + h}>{h}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Engagement window (days)</label>
                  <input className="field-input" type="number" value={form.days} onChange={(e) => set("days", e.target.value)} />
                </div>
                <div className="field">
                  <label>First touch</label>
                  <select className="field-input" value={form.firstTouch} onChange={(e) => set("firstTouch", e.target.value)}>
                    {agent.channels.map((ch) => <option key={ch} value={ch}>{WIZ_CHANNEL_LABELS[ch]}</option>)}
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 mt-4">
                <input type="checkbox" checked={form.inbound} onChange={(e) => set("inbound", e.target.checked)} />
                Allow inbound replies on WhatsApp and SMS
              </label>
              <div className="field mt-4">
                <label>System message <span className="req">*</span></label>
                <textarea className="prompt-box" value={form.systemMessage} onChange={(e) => set("systemMessage", e.target.value)} />
              </div>
            </WizardCard>
          ) : null}
          {tab === "entities" ? (
            <WizardCard title="Lead Entities" subtitle="Fields the agent can read and write on every lead in this campaign.">
              <div className="chip-wrap">
                {WIZ_ENTITIES.map((item) => (
                  <button key={item} type="button" className={picked.includes(item) ? "chip on" : "chip"} onClick={() => toggleList(picked, setPicked, item)}>
                    {item}
                  </button>
                ))}
              </div>
              <p className="muted mt-4">{picked.length} entities attached.</p>
            </WizardCard>
          ) : null}
          {tab === "metrics" ? (
            <WizardCard title="Lead Metrics" subtitle="Outcomes and scores this campaign should compute.">
              <div className="chip-wrap">
                {WIZ_METRICS.map((item) => (
                  <button key={item} type="button" className={metrics.includes(item) ? "chip on" : "chip"} onClick={() => toggleList(metrics, setMetrics, item)}>
                    {item}
                  </button>
                ))}
              </div>
            </WizardCard>
          ) : null}
          {tab === "channels" ? (
            <WizardCard title="Channel Config" subtitle="How this campaign uses the agent's available channels.">
              {agent.channels.map((ch) => (
                <div key={ch} className="field-card">
                  <div className="flex justify-between items-center">
                    <strong>{WIZ_CHANNEL_LABELS[ch]}</strong>
                    <span className="badge badge-live">Enabled</span>
                  </div>
                  <p className="hint">Max 4 attempts per lead · retry after 4 hours · stop on DND.</p>
                  <div className="field-grid mt-3">
                    <div className="field">
                      <label>Max attempts</label>
                      <input className="field-input" defaultValue="4" />
                    </div>
                    <div className="field">
                      <label>Retry after</label>
                      <input className="field-input" defaultValue="4 hours" />
                    </div>
                  </div>
                </div>
              ))}
            </WizardCard>
          ) : null}
          {tab === "state" ? (
            <WizardCard title="Campaign State" subtitle="Start, pause and complete rules.">
              <div className="radio-row">
                {["Draft", "Scheduled", "Active on create"].map((item) => (
                  <button key={item} type="button" className={item === "Active on create" ? "on" : ""}>{item}</button>
                ))}
              </div>
              <div className="field-grid mt-4">
                <div className="field">
                  <label>Start date</label>
                  <input className="field-input" defaultValue="19/09/2026" />
                </div>
                <div className="field">
                  <label>End date</label>
                  <input className="field-input" defaultValue="19/10/2026" />
                </div>
              </div>
            </WizardCard>
          ) : null}
          {tab === "intake" ? (
            <WizardCard title="Lead Intake" subtitle="How leads enter this campaign.">
              <div className="kind-grid">
                <div className="kind-card on">
                  <strong>CSV / Excel upload</strong>
                  <span>Bulk upload phone, name and custom columns.</span>
                </div>
                <div className="kind-card">
                  <strong>API / webhook</strong>
                  <span>Push leads from your CRM as they qualify.</span>
                </div>
                <div className="kind-card">
                  <strong>Manual add</strong>
                  <span>Operators add a single lead from Customers.</span>
                </div>
              </div>
              <div className="dropzone mt-4">Drop a CSV here, or click to browse. Required: phone.</div>
            </WizardCard>
          ) : null}
          {tab === "crm" ? (
            <WizardCard title="CRM" subtitle="Sync lead state back to your system of record.">
              <div className="field-grid">
                <div className="field">
                  <label>CRM</label>
                  <select className="field-input" value={form.crm} onChange={(e) => set("crm", e.target.value)}>
                    <option>Salesforce</option>
                    <option>HubSpot</option>
                    <option>Zoho CRM</option>
                    <option>None</option>
                  </select>
                </div>
                <div className="field">
                  <label>Object</label>
                  <input className="field-input" defaultValue="Lead" />
                </div>
              </div>
              <label className="flex items-center gap-2 mt-4">
                <input type="checkbox" defaultChecked />
                Push dispositions and interest level on every conversation close
              </label>
            </WizardCard>
          ) : null}
          {tab === "dispositions" ? (
            <WizardCard title="Dispositions" subtitle="Outcomes agents can mark when a conversation ends.">
              <div className="chip-wrap">
                {WIZ_DISPOSITIONS.map((item) => (
                  <button key={item} type="button" className={disps.includes(item) ? "chip on" : "chip"} onClick={() => toggleList(disps, setDisps, item)}>
                    {item}
                  </button>
                ))}
              </div>
            </WizardCard>
          ) : null}
          {tab === "variables" ? (
            <WizardCard title="Custom Variables" subtitle="Prompt tokens available to this campaign's agent.">
              <div className="chip-wrap">
                {WIZ_VARS.map((item) => (
                  <button key={item} type="button" className={vars.includes(item) ? "chip on" : "chip"} onClick={() => toggleList(vars, setVars, item)}>
                    {item}
                  </button>
                ))}
              </div>
              <p className="hint mt-4">Type {"{"} in the system prompt to insert a variable.</p>
            </WizardCard>
          ) : null}
          {tab === "handoff" ? (
            <WizardCard title="AI ↔ Human Handoff" subtitle="When the AI should transfer a live conversation to a human agent.">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={handoff} onChange={(e) => setHandoff(e.target.checked)} />
                Enable live handoff to Human Agent queue
              </label>
              <div className="field mt-4">
                <label>Handoff when</label>
                <select className="field-input" defaultValue="ask">
                  <option value="ask">Customer asks for a human</option>
                  <option value="hot">Interest is Hot and amount &gt; ₹5L</option>
                  <option value="dispute">Payment dispute or complaint</option>
                </select>
              </div>
              <div className="info-banner mt-4">
                Humans see campaign context, transcript and suggested next step before they take the call.
              </div>
            </WizardCard>
          ) : null}
          {tab === "webhooks" ? (
            <WizardCard title="Webhooks" subtitle="Notify your systems when leads change state.">
              <div className="field">
                <label>Endpoint URL</label>
                <input className="field-input" value={form.webhook} onChange={(e) => set("webhook", e.target.value)} />
              </div>
              <div className="chip-wrap mt-4">
                {["lead.created", "lead.updated", "call.completed", "handoff.requested"].map((item) => (
                  <span key={item} className="chip on">{item}</span>
                ))}
              </div>
              <button type="button" className="btn-secondary mt-4">Send test event</button>
            </WizardCard>
          ) : null}
          <div className="wizard-nav">
            <button type="button" className="btn-secondary" disabled={idx === 0} onClick={() => setTab(WIZ_TABS[Math.max(0, idx - 1)].id)}>
              Back
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                if (idx === WIZ_TABS.length - 1) {
                  if (onSave) onSave(form);
                } else {
                  setTab(WIZ_TABS[idx + 1].id);
                }
              }}
            >
              {idx === WIZ_TABS.length - 1 ? "Create Campaign" : "Continue"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
'''
