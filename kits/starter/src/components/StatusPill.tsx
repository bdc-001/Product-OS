import clsx from "clsx";
import type { Status } from "../data/fixtures";

const TONE: Record<Status, string> = {
  active: "bg-ok/10 text-ok",
  draft: "bg-muted/10 text-muted",
  paused: "bg-warn/10 text-warn",
  failed: "bg-bad/10 text-bad",
};

export default function StatusPill({ status }: { status: Status }) {
  return <span className={clsx("rounded-full px-2 py-0.5 text-xs font-medium capitalize", TONE[status])}>{status}</span>;
}
