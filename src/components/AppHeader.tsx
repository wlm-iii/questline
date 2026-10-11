const wordmark = 'font-heading text-[38px] leading-none text-ink max-md:text-[28px]'
const action = 'whitespace-nowrap rounded-md border border-line bg-transparent px-3 py-1.5 text-sm font-medium text-bark transition-colors hover:bg-parchment-deep focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-ink max-md:px-1.5 max-md:text-xs'

export function SetupHeader() {
  return <header className="flex h-22 items-center justify-between border-b border-line max-md:h-18"><div className={wordmark}>Questline</div><span className="text-xs text-bark-muted">1 · Plan your adventure</span></header>
}

export function PlannerHeader({ onPlanSetup, onExport, onShare }: { onPlanSetup: () => void; onExport: () => void; onShare: () => void }) {
  return <header className="flex h-16 items-center justify-between border-b border-line px-6 max-md:px-3.5">
    <div className={wordmark}>Questline<span className="ml-5 text-sm text-bark-muted max-md:hidden">/</span><span className="ml-4 text-sm text-bark-muted max-md:hidden">Your trips</span></div>
    <div className="flex items-center gap-2.5 max-md:gap-1.5"><span className="mr-1 text-xs tracking-widest text-bark-muted uppercase max-lg:hidden">Saved on this device</span><button className={action} onClick={onPlanSetup}>Plan setup</button><button className={action} onClick={onExport}>Export</button><button className={action} onClick={onShare}>Share trip</button></div>
  </header>
}
