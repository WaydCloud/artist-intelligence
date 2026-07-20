import reports from "@/data/reports.json";
import { Dashboard } from "@/components/Dashboard";
import type { Report } from "@/lib/report";

export default function ArtistIntelligencePage() {
  return <Dashboard reports={reports as Report[]} />;
}
