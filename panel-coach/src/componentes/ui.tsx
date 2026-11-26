import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Carga } from '../hooks'

type BotonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variante?: 'primario' | 'secundario' | 'peligro' }
const ESTILOS = {
  primario: 'bg-naranja text-[#1a1208] hover:brightness-110',
  secundario: 'bg-tarjeta2 text-texto border border-borde hover:bg-borde',
  peligro: 'bg-sem-rojo/15 text-[#ffb4b6] border border-sem-rojo/60 hover:bg-sem-rojo/30',
}

export function Boton({ variante = 'primario', className = '', ...p }: BotonProps) {
  return (
    <button
      type="button"
      {...p}
      className={`rounded-xl px-4 py-2 text-[15px] font-bold transition disabled:opacity-40 ${ESTILOS[variante]} ${className}`}
    />
  )
}

export function Tarjeta({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl bg-tarjeta p-5 ${className}`}>{children}</div>
}

const COLOR_NIVEL: Record<string, string> = {
  alto: 'bg-sem-rojo/20 text-[#ffb4b6]',
  medio: 'bg-sem-amarillo/20 text-sem-amarillo',
  bajo: 'bg-sem-verde/20 text-sem-verde',
  rojo: 'bg-sem-rojo/20 text-[#ffb4b6]',
  amarillo: 'bg-sem-amarillo/20 text-sem-amarillo',
  verde: 'bg-sem-verde/20 text-sem-verde',
}

export function Etiqueta({ tipo, children }: { tipo: string; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-3 py-1 text-[13px] font-bold uppercase ${COLOR_NIVEL[tipo] ?? 'bg-borde'}`}>{children}</span>
}

/** Estados comunes de carga/error/vacío para que ninguna sección quede en blanco. */
export function Estado<T>({ carga, vacio, children }: { carga: Carga<T>; vacio?: (d: T) => string | null; children: (d: T) => ReactNode }) {
  if (carga.error)
    return (
      <div role="alert" className="flex items-center justify-between gap-4 rounded-2xl border border-sem-rojo/60 bg-sem-rojo/10 p-5 text-[#ffb4b6]">
        <span>{carga.error}</span>
        <Boton variante="secundario" onClick={carga.recargar}>
          Reintentar
        </Boton>
      </div>
    )
  if (carga.datos === null) return <p className="text-suave">Cargando…</p>
  const msg = vacio?.(carga.datos)
  if (msg) return <Tarjeta className="text-suave">{msg}</Tarjeta>
  return <>{children(carga.datos)}</>
}

export function Titulo({ titulo, sub }: { titulo: string; sub?: string }) {
  return (
    <div className="mb-5">
      <h2 className="text-[28px] font-extrabold">{titulo}</h2>
      {sub && <p className="mt-1 max-w-3xl text-[15px] text-suave">{sub}</p>}
    </div>
  )
}

export const PERFILES: Record<string, { nombre: string; descripcion: string }> = {
  constante_manana: { nombre: 'Constantes de la mañana', descripcion: 'Vienen muy seguido, temprano y casi no se ausentan.' },
  nocturno_nuevo: { nombre: 'Nocturnos nuevos', descripcion: 'Socios recientes que entrenan de noche y vienen poco: los que más se van.' },
  veterano_fin_de_semana: { nombre: 'Veteranos de fin de semana', descripcion: 'Llevan mucho tiempo, vienen pocas veces pero con regularidad.' },
}
export const nombrePerfil = (s: string | null) => (s ? (PERFILES[s]?.nombre ?? s) : '—')

/** Mismos ids y nombres que backend/app/core/lesiones.py. */
export const LESIONES = [
  { id: 'rodilla', texto: 'Rodilla' },
  { id: 'hombro', texto: 'Hombro' },
  { id: 'espalda_baja', texto: 'Espalda baja (lumbar)' },
  { id: 'cuello', texto: 'Cuello (cervical)' },
  { id: 'muneca_codo', texto: 'Muñeca o codo' },
  { id: 'tobillo', texto: 'Tobillo' },
  { id: 'cadera', texto: 'Cadera' },
] as const
export const nombreLesion = (id: string) => LESIONES.find((l) => l.id === id)?.texto ?? id

/** Motivo técnico del semáforo → palabras simples. */
export function motivoSimple(m: string): string {
  if (m.startsWith('Presión')) return 'Presión alta'
  if (m.startsWith('Pulso')) return 'Pulso en reposo acelerado'
  if (m.startsWith('PAR-Q+ con respuesta crítica')) return 'Respuesta crítica en el cuestionario PAR-Q+'
  if (m.startsWith('PAR-Q+')) return 'Marcó una molestia en el cuestionario PAR-Q+'
  if (m.startsWith('Lesión declarada')) return `Lesión declarada: ${(m.split(': ')[1] ?? '').split(', ').filter(Boolean).map(nombreLesion).join(', ')}`
  return m
}
