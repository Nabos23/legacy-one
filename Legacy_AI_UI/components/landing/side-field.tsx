'use client'

import { AgentField } from './agent-field'

/**
 * Ambient agent-network constellations down the left/right page gutters.
 * Pulled mostly into the gutter (small off-screen bleed) and stacked closely
 * so the side margins feel populated without crowding the centered content.
 * Shown on xl+ where the gutters exist.
 */
export function SideField() {
  return (
    <div className="sentry-block pointer-events-none absolute inset-0 hidden xl:block" aria-hidden>
      {/* left rail */}
      <AgentField variant="a" className="left-[-110px] top-[5%]" />
      <AgentField variant="b" className="left-[-110px] top-[19%]" delay={1.2} />
      <AgentField variant="a" className="left-[-110px] top-[33%]" delay={2.1} />
      <AgentField variant="b" className="left-[-110px] top-[48%]" delay={0.6} />
      <AgentField variant="a" className="left-[-110px] top-[63%]" delay={1.9} />
      <AgentField variant="b" className="left-[-110px] top-[79%]" delay={0.3} />

      {/* right rail */}
      <AgentField variant="b" className="right-[-110px] top-[11%]" delay={0.4} />
      <AgentField variant="a" className="right-[-110px] top-[26%]" delay={1.7} />
      <AgentField variant="b" className="right-[-110px] top-[41%]" delay={2.4} />
      <AgentField variant="a" className="right-[-110px] top-[57%]" delay={0.9} />
      <AgentField variant="b" className="right-[-110px] top-[72%]" delay={2.2} />
      <AgentField variant="a" className="right-[-110px] top-[88%]" delay={1.4} />
    </div>
  )
}
