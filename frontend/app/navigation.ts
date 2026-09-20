import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import type { ElementType } from "react";
import CalendarTodayOutlinedIcon from "@mui/icons-material/CalendarTodayOutlined";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import CodeOutlinedIcon from "@mui/icons-material/CodeOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import MailOutlineRoundedIcon from "@mui/icons-material/MailOutlineRounded";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import MenuBookOutlinedIcon from "@mui/icons-material/MenuBookOutlined";
import NotesOutlinedIcon from "@mui/icons-material/NotesOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import ConfirmationNumberOutlinedIcon from "@mui/icons-material/ConfirmationNumberOutlined";
import TravelExploreOutlinedIcon from "@mui/icons-material/TravelExploreOutlined";
import ViewQuiltOutlinedIcon from "@mui/icons-material/ViewQuiltOutlined";

export const LINKS: { href: string; label: string; Icon: ElementType; group: string }[] = [
  { href: "/", group: "Product Management", label: "This week", Icon: CalendarTodayOutlinedIcon },
  { href: "/jira", group: "Product Management", label: "Jira", Icon: ConfirmationNumberOutlinedIcon },
  { href: "/cliq", group: "Product Management", label: "Cliq", Icon: ChatBubbleOutlineRoundedIcon },
  { href: "/codebase", group: "Product Management", label: "Codebase", Icon: CodeOutlinedIcon },
  { href: "/prototype", group: "Product Management", label: "Prototype", Icon: ViewQuiltOutlinedIcon },
  { href: "/prd", group: "Product Management", label: "PRD", Icon: DescriptionOutlinedIcon },
  { href: "/roadmap", group: "Product Management", label: "Roadmap", Icon: MapOutlinedIcon },
  { href: "/marketing", group: "Product Marketing", label: "Features", Icon: CampaignOutlinedIcon },
  { href: "/artifacts", group: "Product Marketing", label: "Artifacts", Icon: Inventory2OutlinedIcon },
  { href: "/comms", group: "Product Marketing", label: "Comms", Icon: MailOutlineRoundedIcon },
  { href: "/competitors", group: "Product Marketing", label: "Competitors", Icon: TravelExploreOutlinedIcon },
  { href: "/notes", group: "Knowledge", label: "Notes", Icon: NotesOutlinedIcon },
  { href: "/lms", group: "Knowledge", label: "LMS Library", Icon: MenuBookOutlinedIcon },
  { href: "/settings", group: "Manage", label: "Settings", Icon: SettingsOutlinedIcon },
];
