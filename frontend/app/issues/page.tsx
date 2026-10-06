import { redirect } from "next/navigation";

export default async function IssuesRedirect({
  searchParams,
}: {
  searchParams: Promise<{ board?: string }>;
}) {
  const params = await searchParams;
  const board = (params.board || "").toUpperCase();
  redirect(board ? `/jira?board=${encodeURIComponent(board)}` : "/jira");
}
