import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { PreferencesSettingsForm } from "@/components/preferences-settings-form";
import { SettingsSkeleton } from "@/components/settings-skeleton";
import { Suspense } from "react";

async function PreferencesSettingsContent() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/auth/login");
  }

  return <PreferencesSettingsForm />;
}

export default function PreferencesSettingsPage() {
  return (
    <Suspense fallback={<SettingsSkeleton heights={["h-48", "h-64"]} />}>
      <PreferencesSettingsContent />
    </Suspense>
  );
}
