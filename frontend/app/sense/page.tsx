import { redirect } from "next/navigation";

export default function SensePage() {
  redirect("/jira?board=AC");
}
