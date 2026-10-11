const wordmark = 'font-heading text-[38px] leading-none text-ink max-md:text-[28px]'
const action = 'whitespace-nowrap rounded-md border border-line bg-transparent px-3 py-1.5 text-sm font-medium text-bark transition-colors hover:bg-parchment-deep focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-ink max-md:px-1.5 max-md:text-xs'

export function SetupHeader() {
  return <header className="flex h-22 items-center justify-between border-b border-line max-md:h-18"><div className={wordmark}>Questline</div><span className="text-xs text-bark-muted">1 · Plan your adventure</span></header>
}

export type PlannerHeaderProps = {
  /** Sync status. Defaults to the demo's "Saved on this device". */
  status?: string
  planSetupLabel?: string
  /** The plan setup and export buttons are hidden when their handlers are absent. */
  onPlanSetup?: () => void
  onExport?: () => void
  /** Copies the iMessage link command; hidden when absent, as on the offline demo. */
  onLinkChat?: () => void
  onShare: () => void
}

export function PlannerHeader({ status, planSetupLabel = 'Plan setup', onPlanSetup, onExport, onLinkChat, onShare }: PlannerHeaderProps) {
  return <header className="flex h-16 items-center justify-between border-b border-line px-6 max-md:px-3.5">
    <div className={wordmark}>Questline<span className="ml-5 text-sm text-bark-muted max-md:hidden">/</span><span className="ml-4 text-sm text-bark-muted max-md:hidden">Your trips</span></div>
    <div className="flex items-center gap-2.5 max-md:gap-1.5">{status === undefined ? <span className="mr-1 text-xs tracking-widest text-bark-muted uppercase max-lg:hidden">Saved on this device</span> : <span role="status" className="mr-1 text-xs tracking-widest text-bark-muted uppercase max-md:text-[10px] max-md:tracking-normal">{status}</span>}{onPlanSetup && <button className={action} onClick={onPlanSetup}>{planSetupLabel}</button>}{onExport && <button className={action} onClick={onExport}>Export</button>}{onLinkChat && <button className={action} aria-label="Link iMessage" onClick={onLinkChat}><span className="max-md:hidden">Link </span>iMessage</button>}<button className={action} onClick={onShare}>Share trip</button></div>
  </header>
}
