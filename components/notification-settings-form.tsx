"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { SettingsMessage } from "@/components/settings-message";
import { useState } from "react";

interface NotificationSettings {
  emailNotifications: boolean;
  marketingEmails: boolean;
  securityAlerts: boolean;
  productUpdates: boolean;
  weeklyDigest: boolean;
}

interface NotificationSettingsFormProps {
  initialSettings?: Partial<NotificationSettings>;
}

const NOTIFICATION_OPTIONS: Array<{
  key: keyof NotificationSettings;
  label: string;
  description: string;
  defaultValue: boolean;
}> = [
  {
    key: "emailNotifications",
    label: "Email Notifications",
    description: "Receive emails about your account activity.",
    defaultValue: true,
  },
  {
    key: "securityAlerts",
    label: "Security Alerts",
    description: "Get notified about security events on your account.",
    defaultValue: true,
  },
  {
    key: "productUpdates",
    label: "Product Updates",
    description: "Receive updates about new features and improvements.",
    defaultValue: true,
  },
  {
    key: "weeklyDigest",
    label: "Weekly Digest",
    description: "Get a weekly summary of your account activity.",
    defaultValue: false,
  },
  {
    key: "marketingEmails",
    label: "Marketing Emails",
    description: "Receive promotional offers and marketing messages.",
    defaultValue: false,
  },
];

export function NotificationSettingsForm({
  initialSettings,
}: NotificationSettingsFormProps) {
  const [settings, setSettings] = useState<NotificationSettings>(() => {
    const defaults: NotificationSettings = {
      emailNotifications: true,
      marketingEmails: false,
      securityAlerts: true,
      productUpdates: true,
      weeklyDigest: false,
    };
    return {
      ...defaults,
      ...initialSettings,
    };
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleToggle = (key: keyof NotificationSettings) => {
    setSettings((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Simulate saving to backend
      // In a real app, you would save to Supabase or your API
      await new Promise((resolve) => setTimeout(resolve, 500));

      setSuccess("Notification preferences saved successfully");
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to save preferences"
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Email Notifications</CardTitle>
          <CardDescription>
            Choose what email notifications you want to receive.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave}>
            <div className="flex flex-col gap-4">
              {NOTIFICATION_OPTIONS.map((option, index) => (
                <div
                  key={option.key}
                  className={index > 0 ? "border-t pt-4" : ""}
                >
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor={option.key} className="text-base">
                        {option.label}
                      </Label>
                      <p
                        id={`${option.key}-description`}
                        className="text-sm text-muted-foreground"
                      >
                        {option.description}
                      </p>
                    </div>
                    <Checkbox
                      id={option.key}
                      checked={settings[option.key]}
                      onCheckedChange={() => handleToggle(option.key)}
                      aria-describedby={`${option.key}-description`}
                    />
                  </div>
                </div>
              ))}

              <div className="pt-4">
                <Button type="submit" disabled={isLoading}>
                  {isLoading ? "Saving..." : "Save Preferences"}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      <SettingsMessage type="error" message={error} />
      <SettingsMessage type="success" message={success} />
    </div>
  );
}
