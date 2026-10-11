import type { ReactNode } from 'react'
import { SetupHeader } from '../../components/AppHeader'

export type SetupPageProps = {
  children: ReactNode
  onBuildPlan: () => void
  eyebrow?: string
  title?: string
  description?: ReactNode
  /** Links or notes shown under the intro, such as "Try the demo". */
  actions?: ReactNode
  /** Leave validation to the caller so it can show its own per-field messages. */
  noValidate?: boolean
}
export function SetupPage({
  children,
  onBuildPlan,
  eyebrow = 'A LITTLE PLANNING. A BETTER ADVENTURE.',
  title = 'Where will your quest take you?',
  description = 'Set the essentials first. Then explore your route, rank the possibilities, and let everyone weigh in.',
  actions,
  noValidate,
}: SetupPageProps) {
  return (
    <main className="setup-page">
      <SetupHeader />
      <section className="setup-intro">
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
        {actions}
      </section>
      <form
        className="setup-grid"
        noValidate={noValidate}
        onSubmit={(e) => {
          e.preventDefault()
          onBuildPlan()
        }}
      >
        {children}
      </form>
    </main>
  )
}
