import { useState, type FormEvent } from 'react'
import * as api from '../api/cliente'
import type { CambioFicha, FichaSocioOut, Lesion, MedicionSocio } from '../api/cliente'
import { useSesion } from '../estado/sesion'
import { Boton, Etiqueta, motivoSimple, Tarjeta, Titulo } from '../componentes/ui'

const LESIONES: { id: Lesion; texto: string }[] = [
  { id: 'rodilla', texto: 'Rodilla' },
  { id: 'hombro', texto: 'Hombro' },
  { id: 'espalda_baja', texto: 'Espalda baja' },
  { id: 'cadera', texto: 'Cadera' },
]
const NOMBRE_LESION = Object.fromEntries(LESIONES.map((l) => [l.id, l.texto.toLowerCase()]))

/** PAR-Q+ (las mismas 7 preguntas de la estación). Las 3 primeras son críticas: un «sí» es semáforo rojo. */
const PARQ = [
  'Condición del corazón o actividad solo supervisada',
  'Dolor en el pecho al hacer actividad',
  'Dolor de pecho en reposo el último mes',
  'Pierde el equilibrio por mareos o el conocimiento',
  'Problema de huesos o articulaciones que empeora',
  'Toma medicamentos para la presión o el corazón',
  'Otra razón para no hacer actividad física',
]
const MOTIVOS_RAPIDOS = ['Presentó apto médico', 'Error al registrar']

const fecha = (iso: string) => new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })

/** Resume en palabras simples qué cambió entre dos estados de la ficha. */
function resumenCambio(c: CambioFicha['cambio']): string[] {
  const { antes, despues } = c
  const out: string[] = []
  for (const l of antes.lesiones) if (!despues.lesiones.includes(l)) out.push(`Quitó la lesión de ${NOMBRE_LESION[l] ?? l}`)
  for (const l of despues.lesiones) if (!antes.lesiones.includes(l)) out.push(`Agregó la lesión de ${NOMBRE_LESION[l] ?? l}`)
  PARQ.forEach((q, i) => {
    if (antes.parq[i] && !despues.parq[i]) out.push(`Quitó el «sí» de: ${q}`)
    if (!antes.parq[i] && despues.parq[i]) out.push(`Agregó el «sí» de: ${q}`)
  })
  if (antes.bloqueado && !despues.bloqueado) out.push('Liberó el bloqueo por semáforo rojo')
  if (!antes.bloqueado && despues.bloqueado) out.push('Bloqueó por semáforo rojo')
  if (antes.semaforo !== despues.semaforo) out.push(`Semáforo: ${antes.semaforo} → ${despues.semaforo}`)
  return out
}

export function Fichas() {
  const { coachVista } = useSesion()
  const [dni, setDni] = useState('')
  const [buscando, setBuscando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [datos, setDatos] = useState<FichaSocioOut | null>(null)

  const buscar = async (e: FormEvent) => {
    e.preventDefault()
    setBuscando(true)
    setError(null)
    setDatos(null)
    try {
      setDatos(await api.buscarFicha(dni, coachVista))
    } catch (err) {
      setError(err instanceof api.ErrorApi ? err.message : 'No se pudo buscar el socio.')
    } finally {
      setBuscando(false)
    }
  }

  return (
    <>
      <Titulo
        titulo="Fichas de salud"
        sub="Busca a un socio por DNI para ver su ficha. Solo tú puedes quitar o corregir condiciones: el socio desde la estación únicamente puede agregarlas."
      />
      <form onSubmit={buscar} className="mb-5 flex items-end gap-3" aria-label="Buscar socio">
        <label className="text-[14px] font-semibold text-suave">
          DNI del socio
          <input
            className="mt-1 block w-[220px] rounded-xl border border-borde bg-fondo px-4 py-3 text-[17px] text-texto outline-none focus:border-naranja"
            inputMode="numeric"
            maxLength={8}
            placeholder="8 dígitos"
            value={dni}
            onChange={(e) => setDni(e.target.value.replace(/\D/g, ''))}
          />
        </label>
        <Boton type="submit" disabled={buscando || dni.length !== 8} className="!py-3">
          {buscando ? 'Buscando…' : 'Buscar'}
        </Boton>
      </form>
      {error && (
        <p role="alert" className="rounded-2xl border border-sem-rojo/60 bg-sem-rojo/10 p-4 text-[#ffb4b6]">
          {error}
        </p>
      )}
      {datos && <Detalle key={datos.socio.id} datos={datos} alCambiar={setDatos} />}
    </>
  )
}

/** Categoría OMS del IMC. */
const categoriaImc = (imc: number) => (imc < 18.5 ? 'bajo peso' : imc < 25 ? 'normal' : imc < 30 ? 'sobrepeso' : 'obesidad')

function UltimaMedicion({ m }: { m: MedicionSocio | null | undefined }) {
  if (!m) return <Tarjeta className="text-suave">Este socio aún no tiene mediciones válidas en la estación.</Tarjeta>
  const dato = (etiqueta: string, valor: string | null) => (
    <div>
      <p className="text-[13px] text-suave">{etiqueta}</p>
      <p className="text-[20px] font-bold">{valor ?? '—'}</p>
    </div>
  )
  return (
    <Tarjeta>
      <div className="flex items-baseline justify-between">
        <h3 className="text-[18px] font-bold">Última medición</h3>
        <span className="text-[13px] text-suave">{fecha(m.fecha)}</span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-4">
        {dato('Peso', m.pesoKg != null ? `${m.pesoKg} kg` : null)}
        {dato('Talla', m.tallaCm != null ? `${m.tallaCm} cm` : null)}
        {dato('IMC', m.imc != null ? `${m.imc.toFixed(1)} · ${categoriaImc(m.imc)}` : null)}
        {dato('Grasa', m.grasaPct != null ? `${m.grasaPct} %` : null)}
        {dato('Presión', m.sistolica != null && m.diastolica != null ? `${m.sistolica}/${m.diastolica} mmHg` : null)}
        {dato('Pulso', m.pulso != null ? `${m.pulso} lpm` : null)}
      </div>
    </Tarjeta>
  )
}

const MOTIVOS_LIBERAR = ['Lo evalué en persona', 'Presentó apto médico']

/** Aviso rojo + formulario para liberar a un socio bloqueado por semáforo rojo. */
function Bloqueo({ socioId, desde, alCambiar }: { socioId: string; desde: string | null; alCambiar: (d: FichaSocioOut) => void }) {
  const [motivo, setMotivo] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const liberar = async (e: FormEvent) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    try {
      alCambiar(await api.liberarSocio(socioId, motivo.trim()))
    } catch (err) {
      setError(err instanceof api.ErrorApi ? err.message : 'No se pudo liberar al socio.')   // el 409 del backend, tal cual
    } finally {
      setOcupado(false)
    }
  }
  return (
    <section aria-label="Socio bloqueado" className="rounded-2xl border border-sem-rojo/60 bg-sem-rojo/10 p-5">
      <p role="alert" className="text-[17px] font-bold text-[#ffb4b6]">
        Bloqueado por semáforo rojo{desde ? ` desde ${fecha(desde)}` : ''}. No puede entrenar hasta que lo liberes.
      </p>
      <form onSubmit={liberar} aria-label="Liberar socio" className="mt-3">
        <h3 className="text-[16px] font-bold">Liberar socio</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {MOTIVOS_LIBERAR.map((m) => (
            <Boton key={m} variante="secundario" onClick={() => setMotivo(m)}>
              {m}
            </Boton>
          ))}
        </div>
        <input
          aria-label="Motivo de la liberación"
          className="mt-2 w-full rounded-xl border border-borde bg-fondo px-4 py-3 text-[16px] text-texto outline-none focus:border-naranja"
          maxLength={200}
          placeholder="Ej.: Lo evalué en persona"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
        />
        {error && (
          <p role="alert" className="mt-3 text-[#ffb4b6]">
            {error}
          </p>
        )}
        <Boton type="submit" disabled={ocupado || motivo.trim().length < 3} className="mt-3">
          {ocupado ? 'Liberando…' : 'Liberar socio'}
        </Boton>
      </form>
    </section>
  )
}

function Detalle({ datos, alCambiar }: { datos: FichaSocioOut; alCambiar: (d: FichaSocioOut) => void }) {
  const { socio, ficha, historial, medicion } = datos
  const [parq, setParq] = useState<boolean[]>(ficha?.parq ?? [])
  const [lesiones, setLesiones] = useState<api.Lesion[]>(ficha?.lesiones ?? [])
  const [motivo, setMotivo] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [guardado, setGuardado] = useState(false)

  const hayCambio =
    !!ficha && (ficha.parq.some((v, i) => v !== parq[i]) || ficha.lesiones.length !== lesiones.length || ficha.lesiones.some((l) => !lesiones.includes(l)))
  const puedeGuardar = hayCambio && motivo.trim().length >= 3 && !ocupado

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    setGuardado(false)
    try {
      const nuevo = await api.corregirFicha(socio.id, { parq, lesiones, motivo: motivo.trim() })
      setMotivo('')
      setGuardado(true)
      setParq(nuevo.ficha?.parq ?? parq)
      setLesiones(nuevo.ficha?.lesiones ?? lesiones)
      alCambiar({ ...nuevo })
    } catch (err) {
      setError(err instanceof api.ErrorApi ? err.message : 'No se pudo guardar el cambio.')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="space-y-4">
      <Tarjeta>
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="text-[22px] font-bold">{socio.nombre}</h3>
          <span className="text-[14px] text-suave">DNI {socio.dni}</span>
          <Etiqueta tipo={socio.semaforo}>{socio.semaforo}</Etiqueta>
          {ficha?.actualizada && <span className="ml-auto text-[13px] text-suave">Ficha actualizada: {fecha(ficha.actualizada)}</span>}
        </div>
        {ficha && ficha.motivos.length > 0 && (
          <ul className="mt-2 list-disc pl-5 text-[15px] text-suave">
            {ficha.motivos.map((m) => (
              <li key={m}>{motivoSimple(m)}</li>
            ))}
          </ul>
        )}
      </Tarjeta>

      {ficha?.bloqueado && <Bloqueo socioId={socio.id} desde={ficha.bloqueadoDesde} alCambiar={alCambiar} />}

      <UltimaMedicion m={medicion} />

      {!ficha ? (
        <Tarjeta className="text-suave">Este socio aún no llenó su ficha de salud en la estación.</Tarjeta>
      ) : (
        <form onSubmit={guardar} aria-label="Corregir ficha">
          <Tarjeta>
            <h3 className="text-[18px] font-bold">Lesiones</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {LESIONES.map((l) => (
                <label
                  key={l.id}
                  className={`cursor-pointer rounded-full border-2 px-4 py-2 text-[15px] font-semibold ${lesiones.includes(l.id) ? 'border-naranja bg-naranja/20 text-naranja' : 'border-borde bg-tarjeta2'}`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={lesiones.includes(l.id)}
                    onChange={() => setLesiones((x) => (x.includes(l.id) ? x.filter((y) => y !== l.id) : [...x, l.id]))}
                  />
                  {l.texto}
                </label>
              ))}
            </div>
            <h3 className="mt-5 text-[18px] font-bold">Cuestionario PAR-Q+ (marcado = respondió «sí»)</h3>
            <ul className="mt-2 space-y-1">
              {PARQ.map((q, i) => (
                <li key={q}>
                  <label className="flex items-center gap-3 text-[15px]">
                    <input type="checkbox" checked={!!parq[i]} onChange={() => setParq((p) => p.map((v, j) => (j === i ? !v : v)))} />
                    <span>
                      {i + 1}. {q}
                    </span>
                  </label>
                </li>
              ))}
            </ul>

            <h3 className="mt-5 text-[18px] font-bold">Motivo del cambio (obligatorio)</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {MOTIVOS_RAPIDOS.map((m) => (
                <Boton key={m} variante="secundario" onClick={() => setMotivo(m)}>
                  {m}
                </Boton>
              ))}
            </div>
            <input
              aria-label="Motivo del cambio"
              className="mt-2 w-full rounded-xl border border-borde bg-fondo px-4 py-3 text-[16px] text-texto outline-none focus:border-naranja"
              maxLength={200}
              placeholder="Ej.: Presentó apto médico"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
            {error && (
              <p role="alert" className="mt-3 text-[#ffb4b6]">
                {error}
              </p>
            )}
            {guardado && (
              <p role="status" className="mt-3 font-semibold text-sem-verde">
                Cambio guardado. El semáforo se recalculó y quedó en el historial.
              </p>
            )}
            <Boton type="submit" disabled={!puedeGuardar} className="mt-4">
              {ocupado ? 'Guardando…' : 'Guardar cambio'}
            </Boton>
          </Tarjeta>
        </form>
      )}

      <Tarjeta>
        <h3 className="text-[18px] font-bold">Historial de cambios</h3>
        {historial.length === 0 ? (
          <p className="mt-2 text-suave">Sin cambios hechos por el coach.</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {historial.map((h) => (
              <li key={h.id} className="rounded-xl bg-tarjeta2 p-3">
                <p className="text-[13px] text-suave">{fecha(h.fecha)}</p>
                <p className="text-[15px] font-semibold">Motivo: {h.motivo}</p>
                <ul className="mt-1 list-disc pl-5 text-[14px] text-suave">
                  {resumenCambio(h.cambio).map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </Tarjeta>
    </div>
  )
}
