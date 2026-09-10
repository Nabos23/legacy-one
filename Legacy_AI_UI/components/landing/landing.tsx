'use client'

import { useLenis } from '@/hooks/use-lenis'
import { ScrollProgress } from './scroll-progress'
import { SideField } from './side-field'
import { Nav } from './nav'
import { Hero } from './hero'
import { LogosBand } from './logos-band'
import { Orchestration } from './orchestration'
import { Features } from './features'
import { Connectors } from './connectors'
import { Bento } from './bento'
import { HowItWorks } from './how-it-works'
import { Statement } from './statement'
import { Showcase } from './showcase'
import { TraceReplay } from './trace-replay'
import { Stats } from './stats'
import { Testimonials } from './testimonials'
import { Pricing } from './pricing'
import { Faq } from './faq'
import { CallToAction } from './cta'
import { Footer } from './footer'
import { HelpWidget } from './help-widget'

export function Landing() {
  useLenis()

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-background text-foreground">
      <ScrollProgress />
      <SideField />
      <Nav />
      <HelpWidget />
      <main>
        <Hero />
        <LogosBand />
        <Orchestration />
        <Features />
        <Connectors />
        <Bento />
        <HowItWorks />
        <Statement />
        <Showcase />
        <TraceReplay />
        <Stats />
        <Testimonials />
        <Pricing />
        <Faq />
        <CallToAction />
      </main>
      <Footer />
    </div>
  )
}
