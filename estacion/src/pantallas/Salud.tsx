import { useState } from 'react'
import type { FichaIn } from '../api/cliente'
import { Aviso } from '../componentes/Aviso'
import { Boton } from '../componentes/Boton'
import { Chip } from '../componentes/Chip'
import { Marco } from '../componentes/Marco'
import { useFlujo } from '../estado/flujo'
import { ANIMOS, LESIONES, PREGUNTAS_PARQ } from '../estado/textos'

/** Pantalla 3: ficha de salud (PAR-Q+, ánimo del día y lesiones). */
export function Salud() {
  const { estado, enviarFicha, limpiarError } = useFlujo()
  const [animo, setAnimo] = useState<string>('bien')
  const [lesiones, setLesiones] = useState<FichaIn['lesiones']>([])
  const [parq, setParq] = useState<boolean[]>(Array(PREGUNTAS_PARQ.length).fill(false))

  const alternar = (id: FichaIn['lesiones'][number]) =>
    setLesiones((x) => (x.includes(id) ? x.filter((y) => y !== id) : [...x, id]))

  const enviar = () => {
    const respuestas = [...parq]
    const a = ANIMOS.find((x) => x.id === animo)
    if (a?.parq !== null && a?.parq !== undefined) respuestas[a.parq] = true // mareo / dolor de pecho cuentan en el PAR-Q+
    return enviarFicha({ parq: respuestas, lesiones })
  }

  return (
    <Marco
      paso={3}
      pie={
        <>
          <p className="flex-1 rounded-2xl border border-naranja/50 bg-naranja/10 px-5 py-3 text-[19px] text-naranja">
            🔒 La IA solo recibe el color de tu semáforo, no tus datos de salud.
          </p>
          <Boton disabled={estado.cargando} onClick={enviar}>
            {estado.cargando ? 'Calculando…' : 'Ver mi semáforo'}
          </Boton>
        </>
      }
    >
      <div className="grid h-full grid-cols-[0.8fr_1.2fr] gap-8">
        <div>
          <h1 className="text-[44px] font-extrabold">Antes de entrenar</h1>
          <h2 className="mt-6 text-[26px] font-bold">¿Cómo te sientes hoy?</h2>
          <div className="mt-3 flex flex-wrap gap-3">
            {ANIMOS.map((a) => (
              <Chip key={a.id} activo={animo === a.id} onClick={() => setAnimo(a.id)}>
                {a.texto}
              </Chip>
            ))}
          </div>
          <h2 className="mt-6 text-[26px] font-bold">¿Tienes alguna lesión?</h2>
          <div className="mt-3 flex flex-wrap gap-3">
            {LESIONES.map((l) => (
              <Chip key={l.id} activo={lesiones.includes(l.id)} onClick={() => alternar(l.id)}>
                {l.texto}
              </Chip>
            ))}
          </div>
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
              </p>
              <Chip className="!min-h-[48px] !px-5 !text-[20px]" activo={!parq[i]} onClick={() => setParq((p) => p.map((v, j) => (j === i ? false : v)))}>
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
