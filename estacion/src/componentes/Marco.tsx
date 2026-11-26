import type { ReactNode } from 'react'

const PASOS = ['Identificación', 'Medición', 'Salud', 'Rutina']

/** Marco común de las pantallas: barra superior con progreso de 4 pasos, contenido y pie. `paso` 1–4 (0 = sin barra). */
export function Marco({ paso, children, pie }: { paso: 0 | 1 | 2 | 3 | 4; children: ReactNode; pie?: ReactNode }) {
  return (
    <main className="mx-auto flex h-full w-full max-w-[1280px] flex-col px-14 py-8">
      <header>
        <div className="flex items-center justify-between text-[18px] font-bold tracking-[0.18em] text-naranja">
          <span>TNT FIT · ESTACIÓN</span>
          {paso > 0 && (
            <span className="tracking-normal text-suave">
              Paso {paso} de 4 · {PASOS[paso - 1]}
            </span>
          )}
        </div>
        {paso > 0 && (
          <div className="mt-3 flex gap-3" role="progressbar" aria-valuemin={1} aria-valuemax={4} aria-valuenow={paso} aria-label="Progreso">
            {PASOS.map((p, i) => (
              <div key={p} title={p} className={`h-2 flex-1 rounded-full ${i < paso ? 'bg-naranja' : 'bg-borde'}`} />
            ))}
          </div>
        )}
      </header>
      <section className="mt-6 min-h-0 flex-1">{children}</section>
      {pie && <footer className="mt-4 flex items-center gap-6">{pie}</footer>}
    </main>
  )
}
