import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variante?: 'primario' | 'secundario' | 'peligro' }

const ESTILOS = {
  primario: 'bg-naranja text-[#1a1208] hover:brightness-110',
  secundario: 'bg-tarjeta2 text-texto border border-borde hover:bg-borde',
  peligro: 'bg-sem-rojo text-white',
}

export function Boton({ variante = 'primario', className = '', ...p }: Props) {
  return (
    <button
      type="button"
      {...p}
      className={`min-h-[72px] rounded-2xl px-8 text-[26px] font-bold transition disabled:cursor-not-allowed disabled:opacity-40 ${ESTILOS[variante]} ${className}`}
    />
  )
}
