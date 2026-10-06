import type { ElementType } from "react";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import BadgeOutlinedIcon from "@mui/icons-material/BadgeOutlined";
import CableOutlinedIcon from "@mui/icons-material/CableOutlined";
import CalendarTodayOutlinedIcon from "@mui/icons-material/CalendarTodayOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import CodeOutlinedIcon from "@mui/icons-material/CodeOutlined";
import ConfirmationNumberOutlinedIcon from "@mui/icons-material/ConfirmationNumberOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import ForkRightOutlinedIcon from "@mui/icons-material/ForkRightOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import MailOutlineRoundedIcon from "@mui/icons-material/MailOutlineRounded";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import MenuBookOutlinedIcon from "@mui/icons-material/MenuBookOutlined";
import NewReleasesOutlinedIcon from "@mui/icons-material/NewReleasesOutlined";
import NotesOutlinedIcon from "@mui/icons-material/NotesOutlined";
import PaletteOutlinedIcon from "@mui/icons-material/PaletteOutlined";
import RecentActorsOutlinedIcon from "@mui/icons-material/RecentActorsOutlined";
import TravelExploreOutlinedIcon from "@mui/icons-material/TravelExploreOutlined";
import TuneOutlinedIcon from "@mui/icons-material/TuneOutlined";
import VideoCameraFrontOutlinedIcon from "@mui/icons-material/VideoCameraFrontOutlined";
import ViewQuiltOutlinedIcon from "@mui/icons-material/ViewQuiltOutlined";
import type { Category } from "@/app/ui/tokens";

export type NavLink = {
  href: string;
  label: string;
  Icon: ElementType;
  group: string;
  category?: Category;
  /** Pipelines whose output this page shows; the link hides when all of them are turned off. */
  pipelines?: string[];
  /** Extra path prefixes that count as this page. */
  also?: string[];
  keywords?: string;
};

/** Platform surfaces: always present. */
export const PRIMARY: NavLink[] = [
  { href: "/", group: "Workspace", label: "Home", Icon: HomeOutlinedIcon, category: "system", keywords: "overview dashboard" },
];

/** Where pipeline output lives, grouped the same way as the pipeline catalog. */
export const OUTPUTS: NavLink[] = [
  { href: "/week", group: "Product", label: "This week", Icon: CalendarTodayOutlinedIcon, category: "product", pipelines: ["briefing", "daily-sync"], keywords: "standup briefing" },
  { href: "/jira", group: "Product", label: "Jira", Icon: ConfirmationNumberOutlinedIcon, category: "product", pipelines: ["jira-sync", "copilot"], also: ["/issues", "/support"], keywords: "tickets issues board" },
  { href: "/cliq", group: "Product", label: "Cliq", Icon: ChatBubbleOutlineRoundedIcon, category: "product", pipelines: ["cliq-sync"], also: ["/signals"], keywords: "chat messages" },
  { href: "/codebase", group: "Product", label: "Codebase", Icon: CodeOutlinedIcon, category: "product", pipelines: ["codebase"], keywords: "code index modules ask" },
  { href: "/releases", group: "Product", label: "Releases", Icon: NewReleasesOutlinedIcon, category: "product", pipelines: ["release-notes"], keywords: "release notes branches" },
  { href: "/prototype", group: "Product", label: "Prototypes", Icon: ViewQuiltOutlinedIcon, category: "product", pipelines: ["prototypes"], keywords: "prototype ui" },
  { href: "/prd", group: "Product", label: "PRDs", Icon: DescriptionOutlinedIcon, category: "product", pipelines: ["prd"], keywords: "requirements spec" },
  { href: "/roadmap", group: "Product", label: "Roadmap", Icon: MapOutlinedIcon, category: "product", pipelines: ["roadmap"], keywords: "epics quarter" },
  { href: "/marketing", group: "Marketing", label: "Features", Icon: CampaignOutlinedIcon, category: "marketing", pipelines: ["feature-discovery", "campaigns", "launch-films"], keywords: "campaigns mastersheet films posts" },
  { href: "/avatar", group: "Marketing", label: "Avatar videos", Icon: VideoCameraFrontOutlinedIcon, category: "marketing", pipelines: ["avatar-videos"], keywords: "heygen presenter voice" },
  { href: "/artifacts", group: "Marketing", label: "Artifacts", Icon: Inventory2OutlinedIcon, category: "marketing", pipelines: ["artifacts"], keywords: "one-pager battlecard pdf" },
  { href: "/comms", group: "Marketing", label: "Comms", Icon: MailOutlineRoundedIcon, category: "marketing", pipelines: ["comms"], keywords: "newsletter release notes whatsapp" },
  { href: "/competitors", group: "Marketing", label: "Market watch", Icon: TravelExploreOutlinedIcon, category: "marketing", pipelines: ["market-watch"], keywords: "competitors news pricing" },
  { href: "/notes", group: "Knowledge", label: "Notes", Icon: NotesOutlinedIcon, category: "knowledge", pipelines: ["notes"], keywords: "daily notes learnings" },
  { href: "/lms", group: "Knowledge", label: "Library", Icon: MenuBookOutlinedIcon, category: "knowledge", pipelines: ["library"], keywords: "documents pdf lms" },
];

export const LINKS: NavLink[] = [...PRIMARY, ...OUTPUTS];

export const SETTINGS_LINKS: NavLink[] = [
  { href: "/settings", group: "Workspace", label: "General", Icon: TuneOutlinedIcon, keywords: "name timezone theme" },
  { href: "/settings/profile", group: "Workspace", label: "Product profile", Icon: BadgeOutlinedIcon, keywords: "product description brand tone jira scope" },
  { href: "/settings/people", group: "Workspace", label: "People", Icon: RecentActorsOutlinedIcon, keywords: "team roster developers qa" },
  { href: "/settings/pipelines", group: "Automation", label: "Pipelines", Icon: AccountTreeOutlinedIcon, keywords: "runs schedules automation" },
  { href: "/settings/connections", group: "Automation", label: "Connections", Icon: CableOutlinedIcon, keywords: "integrations api keys jira cliq llm google" },
  { href: "/settings/repositories", group: "Automation", label: "Repositories", Icon: ForkRightOutlinedIcon, keywords: "git branches bitbucket github gitlab" },
  { href: "/settings/members", group: "Access", label: "Members & roles", Icon: GroupOutlinedIcon, keywords: "invite owner admin member" },
  { href: "/settings/security", group: "Access", label: "Security & audit", Icon: AdminPanelSettingsOutlinedIcon, keywords: "audit log activity" },
  { href: "/settings/design", group: "Platform", label: "Design system", Icon: PaletteOutlinedIcon, keywords: "tokens components" },
];

function matches(href: string, path: string) {
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}

export function isActive(link: Pick<NavLink, "href" | "also">, path: string): boolean {
  return matches(link.href, path) || (link.also || []).some((prefix) => matches(prefix, path));
}

/** The settings section a path belongs to; General only owns `/settings` itself. */
export function settingsSection(path: string): NavLink | undefined {
  return SETTINGS_LINKS.find((link) => link.href === path) || SETTINGS_LINKS.find((link) => link.href !== "/settings" && isActive(link, path));
}

export function pageTitle(path: string): string {
  if (path.startsWith("/settings")) return settingsSection(path)?.label || "Settings";
  if (path.startsWith("/issues/")) return "Ticket details";
  if (path.startsWith("/onboarding")) return "Set up your workspace";
  if (path.startsWith("/design")) return "Design system";
  return LINKS.find((link) => isActive(link, path))?.label || "Workspace";
}

/** Links hidden because every pipeline that feeds them is turned off. */
export function visibleOutputs(enabled: Record<string, boolean> | null): NavLink[] {
  if (!enabled) return OUTPUTS;
  return OUTPUTS.filter((link) => !link.pipelines?.length || link.pipelines.some((id) => enabled[id] !== false));
}
