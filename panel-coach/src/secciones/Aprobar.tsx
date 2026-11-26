import { useState } from 'react'
import * as api from '../api/cliente'
import type { RutinaPendiente } from '../api/cliente'
import { Boton, Estado, Etiqueta, motivoSimple, Tarjeta, Titulo } from '../componentes/ui'
import { useCarga } from '../hooks'

function Fila({ r, alResolver }: { r: RutinaPendiente; alResolver: () => void }) {
  const [rechazando, setRechazando] = useState(false)
  const [motivo, setMotivo] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ejecutar = async (fn: () => Promise<unknown>) => {
    setOcupado(true)
    setError(null)
    try {
      await fn()
      alResolver()
    } catch (e) {
      setError(e instanceof api.ErrorApi ? e.message : 'No se pudo completar la acción.')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <Tarjeta>
      <article aria-label={`Rutina de ${r.socioNombre}`}>
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-[20px] font-bold">{r.socioNombre}</h3>
          <Etiqueta tipo={r.semaforo}>{r.semaforo}</Etiqueta>
          <span className="ml-auto text-[13px] text-suave">{new Date(r.creada).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })}</span>
        </div>
        <ul className="mt-2 list-disc pl-5 text-[15px] text-suave">
          {r.motivos.map((m) => (
            <li key={m}>{motivoSimple(m)}</li>
          ))}
        </ul>
        {r.maquinasExcluidas.length > 0 && (
          <p className="mt-2 text-[14px] text-sem-amarillo">Máquinas excluidas: {r.maquinasExcluidas.join(', ')}</p>
        )}
        <ol className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[15px]">
          {r.dias.flatMap((d) => d.ejercicios).map((e, i) => (
            <li key={e.id}>
              <span className="mr-2 inline-block w-5 text-suave">{i + 1}.</span>
              <span className="mr-2 rounded bg-white px-1.5 text-[13px] font-extrabold text-fondo">{e.maquina}</span>
              {e.nombre} <span className="text-suave">· {e.series}×{e.repeticiones}</span>
            </li>
          ))}
        </ol>
        {error && (
          <p role="alert" className="mt-3 text-[#ffb4b6]">
            {error}
          </p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {!rechazando ? (
            <>
              <Boton disabled={ocupado} onClick={() => ejecutar(() => api.aprobarRutina(r.id))}>
                Aprobar
              </Boton>
              <Boton variante="peligro" disabled={ocupado} onClick={() => setRechazando(true)}>
                Rechazar
              </Boton>
            </>
          ) : (
            <>
              <input
                aria-label="Motivo del rechazo"
                autoFocus
                value={motivo}
                maxLength={200}
                onChange={(e) => setMotivo(e.target.value)}
                placeholder="Motivo (el socio lo verá en la estación)"
                className="min-w-[320px] flex-1 rounded-xl border border-borde bg-fondo px-4 py-2 text-[15px] outline-none focus:border-naranja"
              />
              <Boton variante="peligro" disabled={ocupado || motivo.trim().length < 3} onClick={() => ejecutar(() => api.rechazarRutina(r.id, motivo.trim()))}>
                Confirmar rechazo
              </Boton>
              <Boton variante="secundario" onClick={() => setRechazando(false)}>
                Cancelar
              </Boton>
            </>
          )}
        </div>
      </article>
    </Tarjeta>
  )
}

export function Aprobar({ clave }: { clave: number }) {
  // se refresca solo cada 5 s: una rutina nueva en la estación aparece sin recargar
  const carga = useCarga(api.rutinasPendientes, clave, 5000)
  return (
    <>
      <Titulo titulo="Rutinas por aprobar" sub="Rutinas en amarillo: el socio tiene una restricción (lesión, presión o respuesta en el PAR-Q+). La estación espera tu decisión." />
      <Estado carga={carga} vacio={(d) => (d.length === 0 ? 'No hay rutinas por aprobar. 🎉' : null)}>
        {(d) => (
          <div className="space-y-4">
            {d.map((r) => (
              <Fila key={r.id} r={r} alResolver={carga.recargar} />
            ))}
          </div>
        )}
      </Estado>
    </>
  )
}
