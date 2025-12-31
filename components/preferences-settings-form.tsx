"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { SettingsMessage } from "@/components/settings-message";
import { ChevronDown } from "lucide-react";
import { useState } from "react";

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
] as const;

const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "America/New_York", label: "Eastern Time (ET)" },
  { value: "America/Chicago", label: "Central Time (CT)" },
  { value: "America/Denver", label: "Mountain Time (MT)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  { value: "Europe/London", label: "London (GMT)" },
  { value: "Europe/Paris", label: "Paris (CET)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
] as const;

export function PreferencesSettingsForm() {
  const [language, setLanguage] = useState("en");
  const [timezone, setTimezone] = useState("UTC");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Simulate saving to backend
      await new Promise((resolve) => setTimeout(resolve, 500));

      setSuccess("Preferences saved successfully");
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
          <CardTitle>Language & Region</CardTitle>
          <CardDescription>
            Set your preferred language and timezone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave}>
            <div className="flex flex-col gap-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label id="language-label" className="text-base">
                    Language
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Select your preferred language.
                  </p>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-[160px] justify-between"
                      aria-labelledby="language-label"
                    >
                      {LANGUAGES.find((l) => l.value === language)?.label}
                      <ChevronDown className="h-4 w-4 opacity-50" aria-hidden="true" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-[160px]">
                    <DropdownMenuRadioGroup
                      value={language}
                      onValueChange={setLanguage}
                    >
                      {LANGUAGES.map((lang) => (
                        <DropdownMenuRadioItem
                          key={lang.value}
                          value={lang.value}
                        >
                          {lang.label}
                        </DropdownMenuRadioItem>
                      ))}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <div className="border-t pt-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label id="timezone-label" className="text-base">
                      Timezone
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Set your local timezone for accurate time display.
                    </p>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="w-[200px] justify-between"
                        aria-labelledby="timezone-label"
                      >
                        {TIMEZONES.find((t) => t.value === timezone)?.label}
                        <ChevronDown className="h-4 w-4 opacity-50" aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="w-[200px]">
                      <DropdownMenuRadioGroup
                        value={timezone}
                        onValueChange={setTimezone}
                      >
                        {TIMEZONES.map((tz) => (
                          <DropdownMenuRadioItem key={tz.value} value={tz.value}>
                            {tz.label}
                          </DropdownMenuRadioItem>
                        ))}
                      </DropdownMenuRadioGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>

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
