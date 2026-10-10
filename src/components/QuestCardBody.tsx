export function QuestCardBody({ title, description }: { title: string; description: string }) {
  return <div className="quest-card-body"><h3>{title}</h3><p className="quest-description">{description}</p></div>
}
