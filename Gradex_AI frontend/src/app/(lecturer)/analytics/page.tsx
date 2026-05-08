"use client";

import dynamic from "next/dynamic";

const AnalyticsPage = dynamic(
  () => import("@/components/AnalyticsPage").then((m) => m.AnalyticsPage),
  { ssr: false }
);

export default function AnalyticsPageComponent() {
  return <AnalyticsPage />;
}
