import { ArrowRight } from "lucide-react";
import { Link } from "react-router";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { AIPageBanner, AIBadgePill } from "./AIBrand";
import type { AgentConfig } from "../routeConfig";

export function AgentOverview({ agent }: { agent: AgentConfig }) {
  const Icon = agent.icon;
  return (
    <div className="p-8 space-y-6">
      <AIPageBanner model={agent.model} />
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Icon className="size-4" /> {agent.name}
          </div>
          <h2 className="tracking-tight text-slate-900 mt-1">{agent.name}</h2>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">{agent.description}</p>
        </div>
        <AIBadgePill model={agent.model} />
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {agent.features.map((feature) => (
          <Link key={feature.path} to={feature.path} className="group">
            <Card className="h-full p-6 border-slate-200 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50 transition-all">
              <div className="tracking-tight text-slate-900">{feature.title}</div>
              {feature.subtitle && (
                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{feature.subtitle}</p>
              )}
              <Button
                variant="ghost"
                className="mt-3 px-0 text-blue-600 hover:text-blue-700 hover:bg-transparent group-hover:translate-x-1 transition-transform"
              >
                Open <ArrowRight className="size-4 ml-1" />
              </Button>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
