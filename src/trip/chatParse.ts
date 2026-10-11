// Mirrors parse_chat in backend/src/questline/services/persistence.py so the preview matches what the
// backend will store. The backend stays the authority; this only previews.

export type ParsedMessage = { author: string; text: string }

export type ChatPreview = {
  messages: ParsedMessage[]
  authors: string[]
  /** Why the backend would reject this text, or null when it parses. */
  error: string | null
}

export function parseChat(text: string): ChatPreview {
  const messages: ParsedMessage[] = []
  const lines = text.split(/\r\n|\r|\n/)
  for (const [index, line] of lines.entries()) {
    if (!line.trim()) continue
    const colon = line.indexOf(':')
    if (colon >= 0 && !/^\s/.test(line)) {
      const author = line.slice(0, colon).trim()
      const body = line.slice(colon + 1).trim()
      if (!author || !body) return invalid(messages, `Line ${index + 1} needs a name and a message, like "Alex: Let's go".`)
      messages.push({ author, text: body })
    } else if (messages.length > 0) {
      const last = messages[messages.length - 1]
      last.text = `${last.text}\n${line.trim()}`
    } else {
      return invalid(messages, `Line ${index + 1} needs a name first, like "Alex: Let's go".`)
    }
  }
  return {
    messages,
    authors: [...new Set(messages.map(message => message.author))],
    error: messages.length === 0 && text.trim() ? 'No messages found.' : null,
  }
}

function invalid(messages: ParsedMessage[], error: string): ChatPreview {
  return { messages, authors: [...new Set(messages.map(message => message.author))], error }
}
