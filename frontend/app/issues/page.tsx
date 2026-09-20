import { redirect } from "next/navigation";

export default async function IssuesRedirect({
  searchParams,
}: {
  searchParams: Promise<{ board?: string }>;
}) {
  const params = await searchParams;
  const board = (params.board || "AC").toUpperCase();
  redirect(board === "PS" ? "/jira?board=PS" : "/jira?board=AC");
}
