import type { ButtonHTMLAttributes } from 'react'

export function Chip({ activo, className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { activo?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={!!activo}
      {...p}
      className={`min-h-[60px] rounded-full border-2 px-6 text-[22px] font-semibold transition ${
        activo ? 'border-naranja bg-naranja/20 text-naranja' : 'border-borde bg-tarjeta2 text-texto'
      } ${className}`}
    />
  )
}
