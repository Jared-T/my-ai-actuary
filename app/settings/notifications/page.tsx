import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { NotificationSettingsForm } from "@/components/notification-settings-form";
import { SettingsSkeleton } from "@/components/settings-skeleton";
import { Suspense } from "react";

async function NotificationSettingsContent() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/auth/login");
  }

  // In a real app, you would fetch the user's notification preferences from the database
  const initialSettings = user.user_metadata?.notification_settings || {};

  return <NotificationSettingsForm initialSettings={initialSettings} />;
}

export default function NotificationSettingsPage() {
  return (
    <Suspense fallback={<SettingsSkeleton heights={["h-96"]} />}>
      <NotificationSettingsContent />
    </Suspense>
  );
}
