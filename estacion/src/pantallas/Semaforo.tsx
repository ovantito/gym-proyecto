import { Aviso } from '../componentes/Aviso'
import { Boton } from '../componentes/Boton'
import { Marco } from '../componentes/Marco'
import { LucesSemaforo } from '../componentes/Semaforo'
import { useFlujo } from '../estado/flujo'
import { motivoSimple, SUBTITULO_SEMAFORO, TITULO_SEMAFORO } from '../estado/textos'

/** Pantalla 4. Rojo = fin del flujo; verde/amarillo siguen a la rutina. */
export function PantallaSemaforo() {
  const { estado, verRutina, reiniciar, limpiarError } = useFlujo()
  const ficha = estado.ficha
  if (!ficha) return null
  const rojo = ficha.semaforo === 'rojo'
  return (
    <Marco
      paso={3}
      pie={
        <>
          {estado.error && <Aviso onCerrar={limpiarError}>{estado.error}</Aviso>}
          <div className="ml-auto">
            {rojo ? (
              <Boton variante="secundario" onClick={reiniciar}>
                Terminar
              </Boton>
            ) : (
              <Boton disabled={estado.cargando} onClick={verRutina}>
                {estado.cargando ? 'Armando tu rutina…' : 'Ver mi rutina'}
              </Boton>
            )}
          </div>
        </>
      }
    >
      <div className="flex h-full items-center gap-16">
        <LucesSemaforo color={ficha.semaforo} />
        <div className="flex-1">
          <h1 className="text-[48px] font-extrabold leading-tight">{TITULO_SEMAFORO[ficha.semaforo]}</h1>
          <p className="mt-3 text-[28px] font-semibold text-naranja">{SUBTITULO_SEMAFORO[ficha.semaforo]}</p>
          <ul className="mt-5 space-y-2 text-[24px] text-suave">
            {ficha.motivos.map((m) => (
              <li key={m}>• {motivoSimple(m)}</li>
            ))}
          </ul>
          <p className="mt-8 rounded-2xl bg-tarjeta px-5 py-4 text-[19px] text-suave">
            El semáforo usa reglas fijas de salud, no inteligencia artificial.
          </p>
        </div>
      </div>
    </Marco>
  )
}
