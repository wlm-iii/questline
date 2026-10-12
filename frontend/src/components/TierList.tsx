import { useState } from 'react'
import { tiers, type Tier } from './tiers'

const demoCrew = ['Jerry', 'Alex', 'Morgan', 'Sam']
const demoChoices = ['I’m in', 'Maybe', 'Skip']

export type TierListProps<I extends string | number> = {
  options: { id: I; name: string }[]
  ranks: Partial<Record<I, Tier>>
  onRank: (id: I, tier: Tier) => void
  /** The member whose votes are highlighted. */
  voter: string
  /** Shows the "Voting as" picker (the demo's local member switcher). */
  onVoter?: (name: string) => void
  votes: Partial<Record<I, Record<string, string>>>
  onVote: (id: I, choice: string) => void
  /** Names listed under each place's votes. Defaults to the demo crew. */
  crew?: string[]
  /** Vote button labels. Defaults to the demo's I’m in / Maybe / Skip. */
  choices?: string[]
  /** Shows places without a tier in an Unranked row. */
  showUnranked?: boolean
  intro?: string
  hint?: string
  votesHint?: string
}

export function TierList<I extends string | number>({
  options, ranks, onRank, voter, onVoter, votes, onVote,
  crew = demoCrew,
  choices = demoChoices,
  showUnranked = false,
  intro = 'Drag a place into a tier. Higher tiers come first in your questline. S–B are main quests; C–F stay as side quests.',
  hint = 'Use each place’s tier selector for keyboard or touch. Places in the same tier keep their current order. Changes save on this device.',
  votesHint = 'Vote on every place independently of its tier. Tap your selection again to clear it. Tier placements control the route; votes help the party decide.',
}: TierListProps<I>) {
  const [dragged, setDragged] = useState<I | null>(null)
  const [over, setOver] = useState<Tier | null>(null)
  const unranked = options.filter(option => ranks[option.id] === undefined)
  const optionRow = (option: { id: I; name: string }, tier: Tier | null) => (
    <div className={`tier-option ${dragged === option.id ? 'dragging' : ''}`} key={option.id} draggable onDragStart={e => { setDragged(option.id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(option.id)) }} onDragEnd={() => { setDragged(null); setOver(null) }}>
      <span className="drag-handle" aria-hidden="true">⠿</span>
      <strong>{option.name}</strong>
      <select aria-label={`Tier for ${option.name}`} value={tier ?? ''} onChange={e => { if (e.target.value) onRank(option.id, e.target.value as Tier) }}>
        {tier === null && <option value="">–</option>}
        {tiers.map(t => <option key={t} value={t}>{t}</option>)}
      </select>
    </div>
  )
  return <article className="desk-card tier-card">
    <div className="section-title"><h3>Party tier list</h3><span>Rank each stop</span></div>
    <p className="desk-copy">{intro}</p>
    {onVoter && <div className="party-voter"><label>Voting as<select value={voter} onChange={e => onVoter(e.target.value)}>{crew.map(name => <option key={name}>{name}</option>)}</select></label><span>Local demo · switch members to try individual votes</span></div>}
    <div className="tier-board">
      {tiers.map(tier => <section key={tier} className={`tier-row tier-${tier.toLowerCase()} ${over === tier ? 'drop-active' : ''}`} aria-label={`${tier} tier`} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setOver(tier) }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null) }} onDrop={e => { e.preventDefault(); const raw = e.dataTransfer.getData('text/plain'); const option = options.find(o => String(o.id) === raw); if (option) onRank(option.id, tier); setDragged(null); setOver(null) }}>
        <div className="tier-label">{tier}<small>TIER</small></div>
        <div className="tier-items">
          {options.filter(option => ranks[option.id] === tier).map(option => optionRow(option, tier))}
          {!options.some(option => ranks[option.id] === tier) && <span className="tier-empty">Drop a place here</span>}
        </div>
      </section>)}
      {showUnranked && unranked.length > 0 && <section className="tier-row tier-unranked" aria-label="Unranked">
        <div className="tier-label">–<small>UNRANKED</small></div>
        <div className="tier-items">{unranked.map(option => optionRow(option, null))}</div>
      </section>}
    </div>
    <p className="tier-hint">{hint}</p>
    <section className="individual-votes">
      <h4>Party votes</h4>
      <p className="tier-hint">{votesHint}</p>
      {options.map(option => {
        const cast = votes[option.id] ?? {}
        const values = Object.values(cast)
        return <div className="option-voting" key={option.id}>
          <strong>{option.name}</strong>
          <div className="party-vote-actions">{choices.map(choice => <button key={choice} aria-pressed={cast[voter] === choice} className={cast[voter] === choice ? 'selected-vote' : ''} onClick={() => onVote(option.id, choice)}>{choice} <span>{values.filter(v => v === choice).length}</span></button>)}</div>
          <details><summary>{values.filter(Boolean).length} of {crew.length} voted{values.includes(choices[0]) && values.includes(choices[2]) ? ' · Split vote' : ''}</summary>
            <div className="member-votes">{crew.map(name => <span key={name}><b>{name}</b>{cast[name] || 'Not voted'}</span>)}</div>
          </details>
        </div>
      })}
    </section>
  </article>
}
