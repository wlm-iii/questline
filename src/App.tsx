import { Stamp } from '@dendelion/paper-ui'
import { QuestCard } from './components/QuestCard'
import './App.css'

function App() {
  return (
    <main className="journal">
      <header className="journal-header">
        <a className="wordmark" href="#">Questline</a>
        <span className="preview-label">Component preview · Demo data</span>
      </header>
      <section className="journal-intro" aria-labelledby="journal-title">
        <p className="eyebrow">A little adventure, on paper</p>
        <h1 id="journal-title">Every stop has a story.</h1>
        <p>Familiar quest cards, dressed in parchment, warm frames, and a little old-world character.</p>
      </section>
      <section aria-labelledby="quests-title">
        <div className="section-heading">
          <h2 id="quests-title">The quest journal</h2>
          <span>01 — Cards & materials</span>
        </div>
        <div className="quest-grid">
          <QuestCard />
          <QuestCard title="A coastal detour" category="Explore" kind="side" number="02" contested={false} />
        </div>
      </section>
      <section className="field-notes" aria-labelledby="marks-title">
        <div>
          <p className="eyebrow">Room for every word</p>
          <h2 id="marks-title">Marks in the margin</h2>
          <p>Soft rings frame the label, with space for the lettering to breathe.</p>
        </div>
        <div className="stamp-samples">
          <Stamp ring={false} textColor="var(--forest)" className="quest-stamp quest-stamp--main">Main Quest</Stamp>
          <Stamp ring={false} textColor="var(--ink)" className="quest-stamp quest-stamp--side">Side Quest</Stamp>
          <Stamp ring={false} textColor="var(--forest)" className="quest-stamp quest-stamp--info">Along the water</Stamp>
          <Stamp ring={false} textColor="var(--ink)" className="quest-stamp quest-stamp--danger">Contested</Stamp>
        </div>
      </section>
      <footer className="journal-footer">Made for the journey <span>Questline · Material study</span></footer>
    </main>
  )
}

export default App
