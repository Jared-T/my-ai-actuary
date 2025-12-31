import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { AccountSettingsForm } from "@/components/account-settings-form";
import { SettingsSkeleton } from "@/components/settings-skeleton";
import { Suspense } from "react";

async function AccountSettingsContent() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/auth/login");
  }

  return (
    <AccountSettingsForm
      email={user.email || ""}
      displayName={user.user_metadata?.display_name}
    />
  );
}

export default function AccountSettingsPage() {
  return (
    <Suspense fallback={<SettingsSkeleton heights={["h-64", "h-48", "h-32"]} />}>
      <AccountSettingsContent />
    </Suspense>
  );
}
