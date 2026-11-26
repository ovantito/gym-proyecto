import * as api from '../api/cliente'
import { Estado, Tarjeta, Titulo } from '../componentes/ui'
import { useCarga } from '../hooks'

function Metrica({ nombre, valor, explica }: { nombre: string; valor: string; explica: string }) {
  return (
    <Tarjeta>
      <p className="text-[13px] font-bold uppercase text-suave">{nombre}</p>
      <p className="mt-1 text-[36px] font-extrabold leading-none text-naranja">{valor}</p>
      <p className="mt-3 text-[14px] text-suave">{explica}</p>
    </Tarjeta>
  )
}

export function Modelo({ clave }: { clave: number }) {
  const carga = useCarga(api.modelo, clave)
  return (
    <>
      <Titulo titulo="Modelo de IA" />
      <p role="note" className="mb-5 rounded-2xl border border-naranja/60 bg-naranja/10 px-5 py-3 text-[16px] font-semibold text-naranja">
        El semáforo de salud usa reglas fijas, no IA.
      </p>
      <Estado carga={carga}>
        {(m) => (
          <>
            <Tarjeta className="mb-4 flex gap-10">
              <div>
                <p className="text-[13px] uppercase text-suave">Versión</p>
                <p className="text-[24px] font-bold">{m.version}</p>
              </div>
              <div>
                <p className="text-[13px] uppercase text-suave">Entrenado el</p>
                <p className="text-[24px] font-bold">{new Date(m.fechaEntrenamiento).toLocaleDateString('es-PE', { dateStyle: 'long' })}</p>
              </div>
            </Tarjeta>
            <div className="grid grid-cols-3 gap-4">
              <Metrica
                nombre="ROC-AUC · abandono"
                valor={m.metricas.abandono.rocAuc.toFixed(3)}
                explica="Qué tan bien separa a quien se va de quien se queda. 1.0 es perfecto; 0.5 es como tirar una moneda."
              />
              <Metrica
                nombre="F1 · abandono"
                valor={m.metricas.abandono.f1.toFixed(3)}
                explica="Equilibrio entre no dejar escapar a quien se va y no llamar de más. Más cerca de 1, mejor."
              />
              <Metrica
                nombre="R² · afluencia"
                valor={m.metricas.afluencia.r2.toFixed(3)}
                explica="Qué tanto acierta al predecir cuánta gente habrá en la sala a cada hora. 1.0 sería perfecto."
              />
              <Metrica
                nombre="Silueta · perfiles"
                valor={m.metricas.kmeans.silueta.toFixed(3)}
                explica="Qué tan bien separados quedan los 3 perfiles de socios. Más alto significa grupos más claros."
              />
              <Metrica
                nombre="F1 · lecturas atípicas"
                valor={m.metricas.meanshift.f1.toFixed(3)}
                explica="Qué tan bien detecta una báscula o sensor fallando sin dar falsas alarmas."
              />
            </div>
          </>
        )}
      </Estado>
    </>
  )
}
