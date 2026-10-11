type TimePickerProps = { value: string; onChange: (value: string) => void }
export function TimePicker({ value, onChange }: TimePickerProps) {
  const [rawHour, rawMinute] = value.split(':').map(Number)
  const hour = Number.isFinite(rawHour) ? rawHour : 18
  const minute = Number.isFinite(rawMinute) ? rawMinute : 0
  const period = hour >= 12 ? 'PM' : 'AM'
  function update(nextHour: number, nextMinute: number, nextPeriod: string) {
    onChange(`${String(nextHour % 12 + (nextPeriod === 'PM' ? 12 : 0)).padStart(2, '0')}:${String(nextMinute).padStart(2, '0')}`)
  }
  return <div className="modern-time-picker" role="group" aria-label="Return time"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2" strokeLinecap="round"/></svg><select aria-label="Return hour" value={hour % 12 || 12} onChange={e => update(Number(e.target.value), minute, period)}>{Array.from({ length: 12 }, (_, i) => i + 1).map(h => <option key={h} value={h}>{String(h).padStart(2, '0')}</option>)}</select><span className="time-colon">:</span><select aria-label="Return minute" value={minute} onChange={e => update(hour, Number(e.target.value), period)}>{Array.from({ length: 60 }, (_, i) => i).map(m => <option key={m} value={m}>{String(m).padStart(2, '0')}</option>)}</select><div className="time-period">{['AM','PM'].map(p => <button key={p} type="button" aria-pressed={period === p} onClick={() => update(hour, minute, p)}>{p}</button>)}</div></div>
}
