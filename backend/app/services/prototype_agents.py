"""AI Agents list and editor for the prototype sandbox. Do not import go_services."""

AGENTS_PAGE = r'''import { useMemo, useState } from "react";
import SenseFilterBar from "../components/FilterBar";

const AGENT_CHANNELS = {
  ai_call: "AI Call",
  human_call: "Human Call",
  whatsapp: "WhatsApp",
  sms: "SMS",
  widget: "Website Widget",
  whatsapp_call: "AI WhatsApp Call",
};

const AGENTS = [
  { id: "nova", name: "Nova Sales Assistant", active: true, owner: "Arsalaan Mohammed", languages: ["English", "Hindi"], voice: "Aria (Neural)", channels: ["ai_call", "whatsapp", "sms"], gender: "F", goal: "Recover abandoned home-loan applications and book a counsellor slot.", convos: 4280, success: 41, archived: false },
  { id: "atlas", name: "Atlas Collections Agent", active: true, owner: "Priya Nair", languages: ["English"], voice: "Marcus (Neural)", channels: ["ai_call", "human_call"], gender: "M", goal: "Recover overdue EMIs and capture a payment promise.", convos: 3120, success: 36, archived: false },
  { id: "iris", name: "Iris Support Concierge", active: false, owner: "Diego Ruiz", languages: ["English", "Spanish"], voice: "Sofia (Neural)", channels: ["whatsapp", "sms", "widget"], gender: "F", goal: "Resolve billing questions and share knowledge-base answers.", convos: 2190, success: 74, archived: false },
  { id: "orion", name: "Orion Renewal Agent", active: true, owner: "Arsalaan Mohammed", languages: ["English", "Hindi", "Marathi"], voice: "Orion (Neural)", channels: ["ai_call", "sms", "whatsapp_call"], gender: "M", goal: "Present renewal quotes 30 days before policy expiry.", convos: 5602, success: 23, archived: false },
  { id: "lyra", name: "Lyra Feedback Agent", active: false, owner: "Priya Nair", languages: ["English", "Tamil", "Hindi"], voice: "Sana (Neural)", channels: ["sms", "whatsapp"], gender: "F", goal: "Collect post-service feedback and summarise complaints.", convos: 1120, success: 58, archived: true },
  { id: "vega", name: "Vega Winback Agent", active: false, owner: "Diego Ruiz", languages: ["English", "Spanish"], voice: "Kai (Neural)", channels: ["ai_call", "sms", "whatsapp", "widget"], gender: "M", goal: "Re-engage churned customers with a limited-time offer.", convos: 640, success: 19, archived: true },
];

const AGENT_FILTER_FIELDS = [
  { key: "status", label: "Status", group: "Agent", primary: true, options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }] },
  { key: "channel", label: "Channel", group: "Capabilities", primary: true, options: Object.keys(AGENT_CHANNELS).map((id) => ({ value: id, label: AGENT_CHANNELS[id] })) },
  { key: "language", label: "Language", group: "Agent", primary: true, options: ["English", "Hindi", "Spanish", "Tamil", "Marathi"].map((n) => ({ value: n, label: n })) },
  { key: "owner", label: "Created by", group: "Agent", options: ["Arsalaan Mohammed", "Priya Nair", "Diego Ruiz"].map((n) => ({ value: n, label: n })) },
  { key: "archive", label: "Archive", group: "Agent", options: [{ value: "live", label: "Live" }, { value: "archived", label: "Archived" }] },
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

export default function Agents({ q = "", onOpen, onCreate }) {
  const [view, setView] = useState("grid");
  const [menu, setMenu] = useState("");
  const [filters, setFilters] = useState({ archive: ["live"] });
  const rows = useMemo(() => {
    const query = (q || "").toLowerCase();
    const status = filters.status || [];
    const channels = filters.channel || [];
    const langs = filters.language || [];
    const owners = filters.owner || [];
    const archive = filters.archive || [];
    return AGENTS.filter((row) => {
      if (query && !(row.name + row.owner + row.goal).toLowerCase().includes(query)) return false;
      if (status.includes("active") && !status.includes("inactive") && !row.active) return false;
      if (status.includes("inactive") && !status.includes("active") && row.active) return false;
      if (channels.length && !channels.some((ch) => row.channels.includes(ch))) return false;
      if (langs.length && !langs.some((lang) => row.languages.includes(lang))) return false;
      if (owners.length && !owners.includes(row.owner)) return false;
      if (archive.includes("live") && !archive.includes("archived") && row.archived) return false;
      if (archive.includes("archived") && !archive.includes("live") && !row.archived) return false;
      return true;
    });
  }, [q, filters]);

  return (
    <div className="page">
      <SenseFilterBar
        fields={AGENT_FILTER_FIELDS}
        values={filters}
        onChange={setFilters}
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
            <button className="btn-primary" type="button" onClick={() => onCreate && onCreate()}>Create Agent</button>
          </div>
        )}
      />
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
                <th>Success</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((agent) => (
                <tr key={agent.id}>
                  <td className="name" onClick={() => onOpen && onOpen(agent.id)}>
                    {agent.name}
                    {agent.archived ? <div className="muted">Archived</div> : null}
                  </td>
                  <td><AgentStatusPill agent={agent} /></td>
                  <td>{agent.owner}</td>
                  <td>{agent.languages.join(", ")}</td>
                  <td>{agent.voice}</td>
                  <td><AgentChannelChips ids={agent.channels} max={2} /></td>
                  <td>{agent.success}%</td>
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
              </div>
              {menu === agent.id ? (
                <div className="menu-pop" style={{ right: 16, top: 56 }}>
                  <button type="button" onClick={() => onOpen && onOpen(agent.id)}>Edit</button>
                  <button type="button">Clone</button>
                  <button type="button" className="danger">{agent.archived ? "Restore" : "Archive"}</button>
                </div>
              ) : null}
              <div className="card-body">
                <p className="muted">{agent.goal}</p>
                <dl className="meta-grid mt-4">
                  <div className="meta-cell"><dt>Created by</dt><dd>{agent.owner}</dd></div>
                  <div className="meta-cell"><dt>Languages</dt><dd>{agent.languages.join(", ")}</dd></div>
                  <div className="meta-cell"><dt>Voice</dt><dd>{agent.voice}</dd></div>
                  <div className="meta-cell"><dt>Conversations</dt><dd>{agent.convos.toLocaleString()}</dd></div>
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
  lyra: "Lyra Feedback Agent",
  vega: "Vega Winback Agent",
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

const EDITOR_CAPABILITIES = [
  { id: "ai_call", label: "AI Call", inPlan: true },
  { id: "whatsapp_call", label: "AI WhatsApp Call", inPlan: true },
  { id: "human_call", label: "Human Call", inPlan: true },
  { id: "whatsapp", label: "WhatsApp", inPlan: true },
  { id: "sms", label: "SMS", inPlan: true },
  { id: "widget", label: "Website Widget", inPlan: false },
];

const EDITOR_LANGS = ["English", "Hindi", "Tamil", "Marathi", "Spanish", "Arabic"];
const EDITOR_TOOLS = [
  { id: "crm_lookup", name: "CRM Lookup" },
  { id: "payment_link", name: "Send Payment Link" },
  { id: "transfer_agent", name: "Transfer to Human Agent" },
  { id: "emi_calculator", name: "EMI Calculator" },
];
const LLM_MODELS = ["GPT-4o mini", "GPT-4.1", "Claude Sonnet", "Gemini Flash"];
const STT_MODELS = ["Deepgram Nova-3", "Whisper Large v3", "Google STT"];
const TTS_MODELS = ["ElevenLabs Turbo", "Azure Neural", "Cartesia Sonic"];
const TELEPHONY = ["Exotel", "Plivo", "Twilio", "Elision"];

function AgentFieldCard({ label, required, description, children }) {
  return (
    <div className="field-card">
      <label>{label}{required ? <span className="req"> *</span> : null}</label>
      {description ? <p className="hint">{description}</p> : null}
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default function AgentEditor({ id = "nova", onBack, onAnalyse }) {
  const [tab, setTab] = useState("basic");
  const [section, setSection] = useState("Role & Identity");
  const [prompt, setPrompt] = useState(STARTER_PROMPT);
  const [builderOpen, setBuilderOpen] = useState(true);
  const [method, setMethod] = useState("upload");
  const [naturalness, setNaturalness] = useState("full");
  const [name, setName] = useState(AGENT_NAMES[id] || "Nova Sales Assistant");
  const [description, setDescription] = useState("Hindi Loan Collections Agent");
  const [company, setCompany] = useState("Sense");
  const [industry, setIndustry] = useState("BFSI");
  const [website, setWebsite] = useState("https://sense.convin.ai");
  const [goal, setGoal] = useState("Recover abandoned carts and share the checkout link on WhatsApp");
  const [persona, setPersona] = useState("Salaried home-loan applicants aged 28–45");
  const [pain, setPain] = useState("Unclear EMI, missing documents, delayed callbacks");
  const [channels, setChannels] = useState(["ai_call", "whatsapp", "sms"]);
  const [langs, setLangs] = useState(["English", "Hindi"]);
  const [tools, setTools] = useState(["crm_lookup", "transfer_agent"]);
  const [telephony, setTelephony] = useState("Exotel");
  const [llm, setLlm] = useState("GPT-4o mini");
  const [stt, setStt] = useState("Deepgram Nova-3");
  const [tts, setTts] = useState("ElevenLabs Turbo");
  const chars = prompt.length;

  const warning = useMemo(() => {
    if (chars >= 20000) return "Prompt is at the 20,000 character cap.";
    if (chars >= 18000) return "Approaching the 20,000 character cap.";
    return "";
  }, [chars]);

  function toggleChannel(cid) {
    setChannels((cur) => (cur.includes(cid) ? cur.filter((x) => x !== cid) : cur.concat([cid])));
  }

  function toggleLang(lang) {
    setLangs((cur) => (cur.includes(lang) ? cur.filter((x) => x !== lang) : cur.concat([lang]).slice(0, 2)));
  }

  function toggleTool(tid) {
    setTools((cur) => (cur.includes(tid) ? cur.filter((x) => x !== tid) : cur.concat([tid])));
  }

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
          <button type="button" className="btn-secondary" onClick={() => onAnalyse && onAnalyse(name)}>Analyse Agent</button>
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
        <div>
          <section className="section-card">
            <header>
              <h2>Agent</h2>
              <p>Define your AI agent's identity and communication style.</p>
            </header>
            <div className="body">
              <div className="field-grid">
                <div className="field">
                  <label htmlFor="agentName">Agent Name <span className="req">*</span></label>
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
          <section className="section-card">
            <header>
              <h2>Business</h2>
              <p>Company context the agent should stay grounded in.</p>
            </header>
            <div className="body">
              <div className="field-grid">
                <div className="field">
                  <label>Company name <span className="req">*</span></label>
                  <input className="field-input" value={company} onChange={(e) => setCompany(e.target.value)} />
                </div>
                <div className="field">
                  <label>Industry</label>
                  <select className="field-input" value={industry} onChange={(e) => setIndustry(e.target.value)}>
                    <option>BFSI</option>
                    <option>Insurance</option>
                    <option>SaaS</option>
                    <option>E-commerce</option>
                  </select>
                </div>
                <div className="field">
                  <label>Website</label>
                  <input className="field-input" value={website} onChange={(e) => setWebsite(e.target.value)} />
                </div>
                <div className="field" style={{ gridColumn: "1 / -1" }}>
                  <label>Agent goal <span className="req">*</span></label>
                  <textarea className="field-input" rows={3} value={goal} onChange={(e) => setGoal(e.target.value)} />
                  <p className="hint">Type {"{"} to insert a variable</p>
                </div>
              </div>
            </div>
          </section>
          <section className="section-card">
            <header>
              <h2>Audience</h2>
              <p>Who the agent is speaking with, and what they care about.</p>
            </header>
            <div className="body">
              <div className="field">
                <label>Customer persona</label>
                <input className="field-input" value={persona} onChange={(e) => setPersona(e.target.value)} />
              </div>
              <div className="field mt-4">
                <label>Pain points</label>
                <textarea className="field-input" rows={3} value={pain} onChange={(e) => setPain(e.target.value)} />
              </div>
            </div>
          </section>
          <section className="section-card">
            <header>
              <h2>Capabilities</h2>
              <p>Configure how customers can interact with your AI agent.</p>
            </header>
            <div className="body">
              <p className="field-label">Channels <span className="req">*</span></p>
              <p className="hint">Select the communication channels this AI agent supports.</p>
              <div className="cap-grid">
                {EDITOR_CAPABILITIES.map((channel) => {
                  const selected = channels.includes(channel.id);
                  return (
                    <button
                      key={channel.id}
                      type="button"
                      disabled={!channel.inPlan}
                      className={"cap-tile" + (selected ? " on" : "") + (channel.inPlan ? "" : " off")}
                      onClick={() => channel.inPlan && toggleChannel(channel.id)}
                    >
                      {channel.label}
                      {selected && channel.inPlan ? <span className="check">✓</span> : null}
                      {!channel.inPlan ? <em>Not in plan</em> : null}
                    </button>
                  );
                })}
              </div>
              <p className="field-label mt-4">Languages <span className="req">*</span></p>
              <p className="hint">Choose up to two languages: English, one regional language, or both.</p>
              <div className="chip-wrap">
                {EDITOR_LANGS.map((lang) => (
                  <button key={lang} type="button" className={langs.includes(lang) ? "chip on" : "chip"} onClick={() => toggleLang(lang)}>
                    {lang}
                  </button>
                ))}
              </div>
            </div>
          </section>
          <section className="section-card">
            <header>
              <h2>Agent Tools</h2>
              <p>Connect external tools your AI agent can use during conversations.</p>
            </header>
            <div className="body">
              {EDITOR_TOOLS.map((tool) => (
                <label key={tool.id} className="tool-row">
                  <input type="checkbox" checked={tools.includes(tool.id)} onChange={() => toggleTool(tool.id)} />
                  {tool.name}
                </label>
              ))}
              <button type="button" className="btn-secondary mt-4">Add tool</button>
            </div>
          </section>
        </div>
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
      {tab === "ai_call" ? (
        <div>
          <div className="info-banner">AI Call uses your connected telephony provider. Connectivity is measured over the last 7 days.</div>
          <AgentFieldCard label="Telephony provider" required description="Numbers from this provider appear in Settings → Phone Numbers.">
            <select className="field-input" value={telephony} onChange={(e) => setTelephony(e.target.value)}>
              {TELEPHONY.map((item) => <option key={item}>{item}</option>)}
            </select>
          </AgentFieldCard>
          <AgentFieldCard label="LLM" required description="Model used to generate spoken replies.">
            <select className="field-input" value={llm} onChange={(e) => setLlm(e.target.value)}>
              {LLM_MODELS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </AgentFieldCard>
          <AgentFieldCard label="Speech to text" required>
            <select className="field-input" value={stt} onChange={(e) => setStt(e.target.value)}>
              {STT_MODELS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </AgentFieldCard>
          <AgentFieldCard label="Text to speech" required>
            <select className="field-input" value={tts} onChange={(e) => setTts(e.target.value)}>
              {TTS_MODELS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </AgentFieldCard>
          <AgentFieldCard label="Interruption" description="Allow the customer to barge in while the agent is speaking.">
            <label className="flex items-center gap-2"><input type="checkbox" defaultChecked /> Enable barge-in</label>
          </AgentFieldCard>
        </div>
      ) : null}
      {tab === "whatsapp_call" ? (
        <section className="section-card">
          <header><h2>AI Whatsapp Call</h2><p>Voice over WhatsApp using the same prompt and tools.</p></header>
          <div className="body">
            <AgentFieldCard label="WhatsApp business number" required>
              <input className="field-input" defaultValue="+91 80471 20011" />
            </AgentFieldCard>
            <AgentFieldCard label="Voice"><select className="field-input"><option>Aria (Neural)</option><option>Marcus (Neural)</option></select></AgentFieldCard>
          </div>
        </section>
      ) : null}
      {tab === "human_call" ? (
        <section className="section-card">
          <header><h2>Human Call</h2><p>When this agent hands off, humans dial from these numbers.</p></header>
          <div className="body">
            <AgentFieldCard label="Caller ID"><input className="field-input" defaultValue="+91 98200 44117" /></AgentFieldCard>
            <AgentFieldCard label="Queue"><select className="field-input"><option>Collections desk</option><option>Sales advisors</option><option>Support L2</option></select></AgentFieldCard>
            <label className="flex items-center gap-2 mt-3"><input type="checkbox" defaultChecked /> Whisper campaign context before connecting</label>
          </div>
        </section>
      ) : null}
      {tab === "whatsapp" ? (
        <section className="section-card">
          <header><h2>AI Whatsapp Msg</h2><p>Template + free-form follow-ups after a call or as first touch.</p></header>
          <div className="body">
            <AgentFieldCard label="Default template" required>
              <select className="field-input"><option>loan_winback_v3</option><option>emi_reminder_v2</option><option>renewal_quote_v1</option></select>
            </AgentFieldCard>
            <AgentFieldCard label="Session window"><input className="field-input" defaultValue="24 hours" /></AgentFieldCard>
          </div>
        </section>
      ) : null}
      {tab === "sms" ? (
        <section className="section-card">
          <header><h2>AI SMS</h2><p>Short messages with a payment or booking link.</p></header>
          <div className="body">
            <AgentFieldCard label="Sender ID"><input className="field-input" defaultValue="SENSE" /></AgentFieldCard>
            <AgentFieldCard label="Template"><textarea className="field-input" rows={3} defaultValue="Hi {{customer_name}}, this is {{agent_name}} from Sense. Your EMI of {{due_amount}} is due. Reply YES to pay." /></AgentFieldCard>
          </div>
        </section>
      ) : null}
      {tab === "widget" ? (
        <section className="section-card">
          <header><h2>AI Widget</h2><p>Embed the agent on your website. Not in the current plan unless enabled.</p></header>
          <div className="body">
            <div className="info-banner">Website Widget is marked Not in plan on this workspace. Prompt to enable it for a prototype.</div>
            <AgentFieldCard label="Embed snippet"><textarea className="prompt-box" defaultValue={'<script src="https://sense.example/widget.js" data-agent="nova"></script>'} /></AgentFieldCard>
          </div>
        </section>
      ) : null}
    </div>
  );
}
'''
