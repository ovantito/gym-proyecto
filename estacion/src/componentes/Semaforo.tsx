import type { Semaforo } from '../api/cliente'

const COLOR: Record<Semaforo, string> = { verde: 'bg-sem-verde', amarillo: 'bg-sem-amarillo', rojo: 'bg-sem-rojo' }

/** Tres luces; la activa es grande y brilla. */
export function LucesSemaforo({ color }: { color: Semaforo }) {
  return (
    <div className="flex items-center gap-6" role="img" aria-label={`Semáforo ${color}`} data-color={color}>
      {(['rojo', 'amarillo', 'verde'] as Semaforo[]).map((c) => (
        <div
          key={c}
          className={`rounded-full transition-all ${c === color ? `${COLOR[c]} h-56 w-56 shadow-[0_0_80px_10px] shadow-current` : 'h-32 w-32 bg-borde/60'}`}
          style={c === color ? { color: `var(--color-sem-${c})` } : undefined}
        />
      ))}
    </div>
  )
}
