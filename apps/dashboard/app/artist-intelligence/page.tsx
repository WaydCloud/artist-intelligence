import type { Metadata } from "next";
import reports from "@/data/reports.json";
import { Dashboard } from "@/components/Dashboard";
import type { Report } from "@/lib/report";

export const metadata: Metadata = {
  title: "Artist Intelligence — 리포트 대시보드",
};

export default function ArtistIntelligencePage() {
  return <Dashboard reports={reports as Report[]} />;
}
