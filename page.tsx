import { VoiceRehearsalSection } from "@/components/voice/VoiceRehearsalSection";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="mb-8 text-3xl font-bold text-gray-900">SolarReach</h1>
      <VoiceRehearsalSection leadId="demo-lead-001" />
    </main>
  );
}
