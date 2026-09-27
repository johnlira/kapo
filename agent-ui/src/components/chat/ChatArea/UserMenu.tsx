'use client'

import { signOut } from 'next-auth/react'
import { useEffect, useRef, useState } from 'react'

export function UserMenu({
  name,
  email,
  image
}: {
  name?: string | null
  email: string
  image?: string | null
}) {
  const [open, setOpen] = useState(false)
  const [imageFailed, setImageFailed] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeEscape)
    }
  }, [open])

  return (
    <div ref={menuRef} className="relative font-geist">
      <button
        type="button"
        aria-label="Abrir menu do usuário"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
        className="flex size-9 items-center justify-center rounded-full bg-brand/15 text-sm font-semibold text-brand ring-offset-background hover:bg-brand/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        {image && !imageFailed ? (
          // The Google profile image URL is supplied by the authenticated session.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt=""
            referrerPolicy="no-referrer"
            onError={() => setImageFailed(true)}
            className="size-full rounded-full object-cover"
          />
        ) : (
          (name?.trim() || email).charAt(0).toUpperCase()
        )}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-64 rounded-xl border border-border bg-background p-3 text-sm text-secondary shadow-lg"
        >
          {name && (
            <p className="truncate font-semibold" title={name}>
              {name}
            </p>
          )}
          <p className="truncate text-muted" title={email}>
            {email}
          </p>
          <div className="mt-3 border-t border-border pt-2">
            <button
              type="button"
              role="menuitem"
              className="w-full rounded-lg px-2 py-2 text-left hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
              onClick={() => signOut({ callbackUrl: '/login' })}
            >
              Sair
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
