import type { ButtonHTMLAttributes } from 'react'
export function QuestButton({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`quest-button ${className}`} {...props}/>
}
