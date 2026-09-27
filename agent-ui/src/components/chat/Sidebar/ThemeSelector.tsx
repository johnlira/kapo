'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger
} from '@/components/ui/select'

const themes = [
  { value: 'light', label: 'Claro', icon: Sun },
  { value: 'dark', label: 'Escuro', icon: Moon },
  { value: 'system', label: 'Sistema', icon: Monitor }
]

export function ThemeSelector() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])
  const selected = themes.find(({ value }) => value === theme) ?? themes[2]
  const ThemeIcon = selected.icon

  return (
    <Select
      value={mounted ? theme : 'system'}
      onValueChange={setTheme}
      disabled={!mounted}
    >
      <SelectTrigger
        aria-label={`Tema: ${mounted ? selected.label : 'Sistema'}`}
        title="Alterar tema"
        className="h-9 !w-9 shrink-0 justify-center rounded-lg border border-border bg-background p-0 text-primary shadow-none [&>svg:last-child]:hidden"
      >
        {mounted ? (
          <ThemeIcon className="size-4" />
        ) : (
          <Monitor className="size-4" />
        )}
      </SelectTrigger>
      <SelectContent className="border-border bg-primaryAccent font-geist shadow-lg">
        {themes.map(({ value, label, icon: OptionIcon }) => (
          <SelectItem key={value} value={value} className="cursor-pointer">
            <span className="flex items-center gap-2 text-xs font-medium">
              <OptionIcon className="size-4" />
              {label}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
