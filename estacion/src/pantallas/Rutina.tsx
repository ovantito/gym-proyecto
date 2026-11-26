import { useState } from 'react'
import { obtenerVideo, type Ejercicio } from '../api/cliente'
import { Boton } from '../componentes/Boton'
import { Marco } from '../componentes/Marco'
import { useFlujo } from '../estado/flujo'

type Video = { id: string; nombre: string; estado: 'cargando' | 'ok' | 'error'; url?: string }

/** Pantalla 5: rutina ordenada por A*. Al tocar un ejercicio se pide su video firmado a R2. */
export function Rutina() {
  const { estado, irA } = useFlujo()
  const [video, setVideo] = useState<Video | null>(null)
  const rutina = estado.rutina
  if (!rutina) return null
  const ejercicios: Ejercicio[] = rutina.dias.flatMap((d) => d.ejercicios)
  const det = rutina.detalle
  const pendiente = rutina.estado === 'pendiente_aprobacion'

  const abrir = async (e: Ejercicio) => {
    setVideo({ id: e.id, nombre: e.nombre, estado: 'cargando' })
    try {
      const v = await obtenerVideo(e.id)
      setVideo((x) => (x?.id === e.id ? { ...x, estado: 'ok', url: v.url } : x))
    } catch {
      setVideo((x) => (x?.id === e.id ? { ...x, estado: 'error' } : x)) // sin romper la pantalla
    }
  }

  return (
    <Marco
      paso={4}
      pie={
        <>
          {pendiente && <p className="flex-1 text-[20px] font-semibold text-sem-amarillo">Tu coach revisará y aprobará esta rutina.</p>}
          <Boton className="ml-auto" onClick={() => irA('ticket')}>
            Imprimir mi ticket
          </Boton>
        </>
      }
    >
      <div className="grid h-full grid-cols-[1.1fr_0.9fr] gap-8">
        <div className="flex min-h-0 flex-col">
          <h1 className="text-[38px] font-extrabold">Tu rutina de hoy</h1>
          <p className="text-[20px] text-suave">
            {ejercicios.length} ejercicios · {pendiente ? 'pendiente de aprobación del coach' : 'lista para empezar'}
          </p>
          <ol className="mt-3 flex-1 space-y-1.5 overflow-y-auto pr-1">
            {ejercicios.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => abrir(e)}
                  aria-label={`${e.nombre}, ver video`}
                  className={`flex w-full items-center gap-4 rounded-2xl px-5 py-2 text-left transition ${
                    video?.id === e.id ? 'bg-tarjeta2 ring-2 ring-naranja' : 'bg-tarjeta'
                  }`}
                >
                  <span className="rounded-lg bg-white px-3 py-1 text-[20px] font-extrabold text-fondo">{e.maquina}</span>
                  <span className="flex-1">
                    <span className="block text-[22px] font-bold leading-tight">{e.nombre}</span>
                    <span className="block text-[17px] leading-tight text-suave">
                      {e.series} × {e.repeticiones} · descanso {e.descansoSeg} s
                    </span>
                  </span>
                  <span className="text-[19px] font-bold text-teal">
                    espera {Math.round(estado.espera[e.maquina] ?? 0)} min
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>
        <div className="flex min-h-0 flex-col gap-4">
          <div className="rounded-2xl border-2 border-naranja bg-naranja/10 px-5 py-4">
            <p className="text-[22px] font-bold text-naranja">
              Orden optimizado por el motor ({det?.algoritmo === 'hill_climbing' ? 'modo respaldo' : 'A*'})
            </p>
            {det && (
              <p className="mt-1 text-[18px]">
                {det.sociosEnSala} socios en sala ahora. Este orden te hace perder ~{Math.round(det.tiempoPerdidoEstimadoMin)} min entre traslados y esperas.
              </p>
            )}
          </div>
          <div className="flex flex-1 items-center justify-center overflow-hidden rounded-2xl bg-[#2a4a7f]" data-testid="panel-video">
            {!video && <p className="px-6 text-center text-[22px] text-white/80">Toca un ejercicio para ver su video</p>}
            {video?.estado === 'cargando' && <p className="text-[22px]">Cargando video…</p>}
            {video?.estado === 'error' && <p className="text-[24px] font-semibold">Video no disponible</p>}
            {video?.estado === 'ok' && video.url && (
              <video key={video.url} src={video.url} controls autoPlay loop muted className="h-full w-full object-contain" aria-label={`Video de ${video.nombre}`} />
            )}
          </div>
          {rutina.alertas.map((a) => (
            <p key={a} className="text-[18px] font-semibold text-sem-amarillo">
              {a}
            </p>
          ))}
        </div>
      </div>
    </Marco>
  )
}
