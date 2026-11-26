import { useState } from 'react'
import type { FichaIn, FichaPrevia } from '../api/cliente'
import { Aviso } from '../componentes/Aviso'
import { Boton } from '../componentes/Boton'
import { Chip } from '../componentes/Chip'
import { Marco } from '../componentes/Marco'
import { useFlujo } from '../estado/flujo'
import { ANIMOS, LESIONES, nombreLesion, PREGUNTAS_PARQ, type SintomaHoy } from '../estado/textos'

/** Síntomas de hoy a partir del chip elegido (no se guardan en la ficha permanente). */
const sintomasDe = (animo: string): SintomaHoy[] => {
  const a = ANIMOS.find((x) => x.id === animo)
  return a?.sintoma ? [a.sintoma] : []
}

function Animos({ animo, alCambiar }: { animo: string; alCambiar: (id: string) => void }) {
  return (
    <>
      <h2 className="mt-6 text-[26px] font-bold">¿Cómo te sientes hoy?</h2>
      <div className="mt-3 flex flex-wrap gap-3">
        {ANIMOS.map((a) => (
          <Chip key={a.id} activo={animo === a.id} onClick={() => alCambiar(a.id)}>
            {a.texto}
          </Chip>
        ))}
      </div>
    </>
  )
}
const TEXTO_BLOQUEO = 'Para quitarla, habla con tu coach'

/** Pantalla 3: ficha de salud. Si el socio ya tiene una, primero se le pregunta si sigue igual. */
export function Salud() {
  const { estado, enviarFicha, limpiarError } = useFlujo()
  const previa = estado.fichaPrevia
  const [actualizando, setActualizando] = useState(false)
  const [animo, setAnimo] = useState<string>('bien')
  const [lesiones, setLesiones] = useState<FichaIn['lesiones']>(previa?.lesiones ?? [])
  const [parq, setParq] = useState<boolean[]>(previa?.parq ?? Array(PREGUNTAS_PARQ.length).fill(false))

  if (previa && !actualizando)
    return (
      <Confirmar
        previa={previa}
        cargando={estado.cargando}
        error={estado.error}
        alCerrarError={limpiarError}
        animo={animo}
        alCambiarAnimo={setAnimo}
        alSeguirIgual={() => {
          const respuestas = [...previa.parq]
          const a = ANIMOS.find((x) => x.id === animo)
          if (a?.parq !== null && a?.parq !== undefined) respuestas[a.parq] = true
          return enviarFicha({ parq: respuestas, lesiones: previa.lesiones, sintomas_hoy: sintomasDe(animo) })
        }}
        alActualizar={() => setActualizando(true)}
      />
    )

  // Lo que ya estaba registrado no se puede quitar desde la estación (el backend también lo exige).
  const lesionBloqueada = (id: string) => previa?.lesiones.includes(id) ?? false
  const parqBloqueada = (i: number) => previa?.parq[i] ?? false
  const opcionesLesion = [
    ...LESIONES.map((l) => ({ id: l.id as string, texto: l.texto as string })),
    ...(previa?.lesiones ?? []).filter((id) => !LESIONES.some((l) => l.id === id)).map((id) => ({ id, texto: nombreLesion(id) })),
  ]

  const alternar = (id: string) => {
    if (lesionBloqueada(id)) return
    setLesiones((x) => (x.includes(id) ? x.filter((y) => y !== id) : [...x, id]))
  }

  const enviar = () => {
    const respuestas = [...parq]
    const a = ANIMOS.find((x) => x.id === animo)
    if (a?.parq !== null && a?.parq !== undefined) respuestas[a.parq] = true // mareo / dolor de pecho cuentan en el PAR-Q+
    return enviarFicha({ parq: respuestas, lesiones, sintomas_hoy: sintomasDe(animo) })
  }

  return (
    <Marco
      paso={3}
      pie={
        <>
          <Boton className="ml-auto" disabled={estado.cargando} onClick={enviar}>
            {estado.cargando ? 'Calculando…' : 'Ver mi semáforo'}
          </Boton>
        </>
      }
    >
      <div className="grid h-full grid-cols-[0.8fr_1.2fr] gap-8">
        <div>
          <h1 className="text-[44px] font-extrabold">Antes de entrenar</h1>
          <Animos animo={animo} alCambiar={setAnimo} />
          <h2 className="mt-6 text-[26px] font-bold">¿Tienes alguna lesión?</h2>
          <div className="mt-3 flex flex-wrap gap-3">
            {opcionesLesion.map((l) => (
              <Chip key={l.id} activo={lesiones.includes(l.id)} disabled={lesionBloqueada(l.id)} onClick={() => alternar(l.id)} className="disabled:opacity-100">
                {l.texto}
                {lesionBloqueada(l.id) && ' 🔒'}
              </Chip>
            ))}
          </div>
          {(previa?.lesiones.length ?? 0) > 0 && <p className="mt-3 text-[18px] text-suave">🔒 Ya registrada. {TEXTO_BLOQUEO}.</p>}
          {estado.error && (
            <div className="mt-5">
              <Aviso onCerrar={limpiarError}>{estado.error}</Aviso>
            </div>
          )}
        </div>
        <div className="space-y-2 overflow-hidden rounded-3xl bg-tarjeta p-4">
          <h2 className="px-2 text-[22px] font-bold text-suave">Cuestionario PAR-Q+</h2>
          {PREGUNTAS_PARQ.map((q, i) => (
            <div key={q} className="flex items-center gap-4 px-2" role="group" aria-label={`Pregunta ${i + 1}`}>
              <p className="flex-1 text-[18px] leading-snug">
                {i + 1}. {q}
                {parqBloqueada(i) && <span className="block text-[16px] text-suave">🔒 {TEXTO_BLOQUEO}</span>}
              </p>
              <Chip className="!min-h-[48px] !px-5 !text-[20px]" activo={!parq[i]} disabled={parqBloqueada(i)} onClick={() => setParq((p) => p.map((v, j) => (j === i ? false : v)))}>
                No
              </Chip>
              <Chip className="!min-h-[48px] !px-5 !text-[20px]" activo={parq[i]} onClick={() => setParq((p) => p.map((v, j) => (j === i ? true : v)))}>
                Sí
              </Chip>
            </div>
          ))}
        </div>
      </div>
    </Marco>
  )
}

/** «¿Sigues igual que la última vez?»: muestra lo que ya está registrado y deja reutilizarlo o actualizarlo. */
function Confirmar({
  previa, cargando, error, alCerrarError, animo, alCambiarAnimo, alSeguirIgual, alActualizar,
}: {
  previa: FichaPrevia
  cargando: boolean
  error: string | null
  alCerrarError: () => void
  animo: string
  alCambiarAnimo: (id: string) => void
  alSeguirIgual: () => void
  alActualizar: () => void
}) {
  const registradas = [
    ...previa.lesiones.map((l) => `Lesión de ${nombreLesion(l).toLowerCase()}`),
    ...PREGUNTAS_PARQ.filter((_, i) => previa.parq[i]),
  ]
  return (
    <Marco
      paso={3}
      pie={
        <>
          <Boton variante="secundario" className="ml-auto" disabled={cargando} onClick={alActualizar}>
            Actualizar
          </Boton>
          <Boton disabled={cargando} onClick={alSeguirIgual}>
            {cargando ? 'Calculando…' : 'Sí, sigo igual'}
          </Boton>
        </>
      }
    >
      <div className="mx-auto flex h-full max-w-3xl flex-col justify-center">
        <h1 className="text-[44px] font-extrabold">¿Sigues igual que la última vez?</h1>
        <div className="mt-6 rounded-3xl bg-tarjeta p-6">
          <h2 className="text-[22px] font-bold text-suave">Esto es lo que tenemos registrado</h2>
          {registradas.length === 0 ? (
            <p className="mt-3 text-[22px]">Sin lesiones ni molestias.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-[22px]">
              {registradas.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          )}
        </div>
        <Animos animo={animo} alCambiar={alCambiarAnimo} />
        {error && (
          <div className="mt-5">
            <Aviso onCerrar={alCerrarError}>{error}</Aviso>
          </div>
        )}
      </div>
    </Marco>
  )
}
