'use client'

import { useTheme } from 'next-themes'
import { Toaster as Sonner } from 'sonner'

type ToasterProps = React.ComponentProps<typeof Sonner>

const Toaster = ({ ...props }: ToasterProps) => {
  const { resolvedTheme } = useTheme()

  return (
    <Sonner
      theme={(resolvedTheme ?? 'system') as ToasterProps['theme']}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:bg-background group-[.toaster]:text-secondary group-[.toaster]:border-border group-[.toaster]:shadow-lg',
          description: 'group-[.toast]:text-muted',
          actionButton:
            'group-[.toast]:bg-primary group-[.toast]:text-primaryAccent',
          cancelButton: 'group-[.toast]:bg-accent group-[.toast]:text-primary'
        }
      }}
      {...props}
    />
  )
}

export { Toaster }
