interface FlowStep {
  label: string;
  value: string;
}

const withoutSteps: FlowStep[] = [
  { label: "Step 1", value: "Attend Meeting" },
  { label: "Step 2", value: "Scramble for Your Notes" },
  { label: "Step 3", value: "Copy Them to Your Agent\u2019s Prompt" },
  { label: "Step 4", value: "Hope You Got It All" },
];

const withSteps: FlowStep[] = [
  { label: "Real-time", value: "Your Agent Joins the Meeting" },
  { label: "Real-time", value: "Your Agent Actively Participates" },
  { label: "Real-time", value: "Your Agent Extracts Tasks in Real-Time" },
  { label: "Post-meeting", value: "Your Agent Leaves Ready to Execute" },
];

function StepItem({
  step,
  index,
  variant,
}: {
  step: FlowStep;
  index: number;
  variant: "old" | "new";
}) {
  const circleColor =
    variant === "old"
      ? "bg-red-400/20 text-red-400"
      : "bg-green-600/20 text-green-500";

  return (
    <div className="flex items-center gap-4">
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 font-bold text-sm ${circleColor}`}
      >
        {index + 1}
      </div>
      <div className="flex flex-col">
        <span className="text-xs text-slate-400 uppercase tracking-wider">
          {step.label}
        </span>
        <span className="font-medium text-white">{step.value}</span>
      </div>
    </div>
  );
}

export default function ContextSection() {
  return (
    <section className="px-6 py-24">
      <div className="max-w-[1000px] mx-auto">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12 text-white">
          Stop Being the Middleman Between Meeting Context &amp; Your{" "}
          <span className="whitespace-nowrap">AI Agents</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
          {/* Without Kutana */}
          <div className="bg-slate-800/80 border border-red-400/30 rounded-2xl p-8">
            <h3 className="text-xl font-bold text-red-400 mb-6">
              Without Kutana
            </h3>
            <div className="flex flex-col gap-4">
              {withoutSteps.map((step, i) => (
                <StepItem key={i} step={step} index={i} variant="old" />
              ))}
            </div>
          </div>

          {/* With Kutana */}
          <div className="bg-slate-800/80 border border-green-600/30 rounded-2xl p-8">
            <h3 className="text-xl font-bold text-green-500 mb-6">
              With Kutana
            </h3>
            <div className="flex flex-col gap-4">
              {withSteps.map((step, i) => (
                <StepItem key={i} step={step} index={i} variant="new" />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
