import { notFound, redirect } from "next/navigation";

const MOVED: Record<string, string> = {
  integrations: "/settings/connections",
  models: "/settings/connections?provider=llm",
  content: "/settings/connections",
  mail: "/settings/connections?provider=smtp",
};

export default async function SettingsSection({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const target = MOVED[section];
  if (!target) notFound();
  redirect(target);
}
