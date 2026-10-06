import type { Standup, StandupItem } from "@/lib/api";

const TZ = "Asia/Kolkata";

export type Pulse = {
  name: string;
  period: "morning" | "afternoon" | "evening" | "night";
  timeLabel: string;
  greeting: string;
  mindset: string;
  thisWeek: number;
  other: number;
  uat: number;
  blockers: number;
  missingTickets: number;
};

export type WeekView = "week" | "other" | "uat" | "none";

export const WEEK_TABS: { id: WeekView; label: string }[] = [
  { id: "week", label: "This week" },
  { id: "other", label: "Other" },
  { id: "uat", label: "UAT" },
  { id: "none", label: "No ticket" },
];

export function itemKind(item: StandupItem) {
  return (item.kind || item.flag || "").toLowerCase();
}

export function itemTicketKey(item: StandupItem) {
  if (item.issue_key) return item.issue_key;
  const match = (item.title || "").match(/\b([A-Z][A-Z0-9]+-\d+)\b/);
  return match?.[1] || "";
}

export function weekBuckets(standup: Standup | null) {
  const thisWeek = standup?.this_week?.length
    ? standup.this_week
    : (standup?.week_actions || []).filter((item) => ["week_plan", "create_ticket"].includes(itemKind(item)));
  const other = standup?.other_actions?.length
    ? standup.other_actions
    : (standup?.week_actions || []).filter((item) => !["week_plan", "create_ticket"].includes(itemKind(item)));
  const pool = [...thisWeek, ...other];
  return {
    week: thisWeek,
    other,
    uat: pool.filter((item) => itemKind(item) === "uat"),
    none: pool.filter((item) => itemKind(item) === "create_ticket" || !itemTicketKey(item)),
  };
}

function hourIst() {
  const raw = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "numeric", hourCycle: "h23" }).format(new Date());
  return Number(raw);
}

function periodFor(hour: number): Pulse["period"] {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  if (hour >= 17 && hour <= 23) return "evening";
  return "night";
}

function firstNamed(items: StandupItem[]) {
  for (const item of items) {
    const key = itemTicketKey(item);
    if (key) return key;
  }
  return items[0]?.title?.replace(/^AC-\d+:\s*/i, "").slice(0, 42) || "";
}

export function buildPulse(standup: Standup | null, name = "Arsalaan"): Pulse {
  const hour = hourIst();
  const period = periodFor(hour);
  const timeLabel =
    new Intl.DateTimeFormat("en-GB", {
      timeZone: TZ,
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
      .format(new Date())
      .replace(",", "") + " IST";

  const buckets = weekBuckets(standup);
  const thisWeek = buckets.week;
  const other = buckets.other;
  const pool = [...thisWeek, ...other];
  const uat = buckets.uat.length;
  const blockers = pool.filter((item) => itemKind(item) === "blocker" || item.flag === "conflict").length;
  const missingTickets = buckets.none.length;
  const lead = firstNamed(thisWeek.length ? thisWeek : pool);

  const greetings: Record<Pulse["period"], string> = {
    morning: `Morning, ${name}.`,
    afternoon: `Afternoon, ${name}.`,
    evening: `Evening, ${name}.`,
    night: `Still in it, ${name}.`,
  };

  let mindset = "Protect the calendar. One real close before you open another thread.";
  if (period === "morning") {
    if (uat) mindset = lead ? `UAT first. Unblock ${lead} before the rest of the board gets a vote.` : "UAT is the bottleneck. Clear it before you collect more work.";
    else if (blockers) mindset = "A blocker is sitting on the board. Kill it before standup finds you.";
    else if (missingTickets) mindset = "A few items still have no ticket. Write them down or they aren't real.";
    else if (thisWeek.length >= 6) mindset = `Heavy week. Cut it to three. Start with ${lead || "the first card"}.`;
    else if (thisWeek.length) mindset = lead ? `Quiet confidence. Finish ${lead} before Slack eats the morning.` : "Quiet confidence. One ticket to done before noon.";
    else mindset = "Clean board. Use the morning to write, not to hover.";
  } else if (period === "afternoon") {
    if (uat) mindset = "Midday is for unblocking, not starting. Push UAT through.";
    else if (thisWeek.length >= 5) mindset = "Triage, don't collect. Close a loop before you add another.";
    else if (thisWeek.length) mindset = lead ? `Keep ${lead} moving. Decisions now, polish later.` : "Keep the list moving. Decisions now, polish later.";
    else mindset = "List is light. Steal the afternoon for the roadmap, not inbox zero.";
  } else if (period === "evening") {
    if (thisWeek.length) mindset = lead ? `Leave ${lead} cleaner than you found it. Park the rest for tomorrow.` : "Leave the board cleaner than you found it. Park the rest.";
    else mindset = "Board's quiet. Close Cliq loops and walk.";
  } else if (uat) mindset = "UAT is not a 1am problem. Park the board. Morning you handles it.";
  else if (thisWeek.length) mindset = "Park it. Tomorrow's morning version of you is the actual PM.";
  else mindset = "Nothing burning. Sleep is a product decision.";

  return {
    name,
    period,
    timeLabel,
    greeting: greetings[period],
    mindset,
    thisWeek: thisWeek.length,
    other: other.length,
    uat,
    blockers,
    missingTickets,
  };
}
