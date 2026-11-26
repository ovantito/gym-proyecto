import { Aviso } from '../componentes/Aviso'
import { Boton } from '../componentes/Boton'
import { Marco } from '../componentes/Marco'
import { useFlujo } from '../estado/flujo'

function Metrica({ valor, unidad, nombre }: { valor?: number; unidad: string; nombre: string }) {
  return (
    <div className="rounded-3xl bg-tarjeta px-6 py-5">
      <p className="text-[46px] font-extrabold leading-none">
        {valor === undefined ? '—' : valor} <span className="text-[24px] font-semibold text-suave">{unidad}</span>
      </p>
      <p className="mt-2 text-[20px] text-suave">{nombre}</p>
    </div>
  )
}

/** Pantalla 2. Báscula simulada; si el backend dice "atípica", la lectura no se usa. */
export function Medicion() {
  const { estado, medir, irA, limpiarError } = useFlujo()
  const l = estado.lectura ?? undefined
  const imc = l ? Math.round((l.peso / (l.talla / 100) ** 2) * 10) / 10 : undefined
  return (
    <Marco
      paso={2}
      pie={
        <>
          <Boton variante="secundario" className="!px-5 !text-[21px]" disabled={estado.cargando} onClick={() => medir('normal')}>
            Simular báscula
          </Boton>
          <Boton variante="secundario" className="!px-5 !text-[21px]" disabled={estado.cargando} onClick={() => medir('imposible')}>
            Simular lectura imposible
          </Boton>
          <Boton variante="secundario" className="!px-5 !text-[21px]" disabled={estado.cargando} onClick={() => medir('presion_alta')}>
            Simular presión alta
          </Boton>
          <Boton className="ml-auto" disabled={!estado.medicionValida || estado.cargando} onClick={() => irA('salud')}>
            Continuar
          </Boton>
        </>
      }
    >
      <h1 className="text-[48px] font-extrabold">Hola, {estado.socio?.nombre}</h1>
      <p className="mt-1 text-[24px] text-suave">Párate derecho en la báscula, bajo el tallímetro, y sostén los sensores de las manos.</p>
      <div className="mt-6 grid grid-cols-3 gap-4">
        <Metrica valor={l?.peso} unidad="kg" nombre="Peso" />
        <Metrica valor={l?.talla} unidad="cm" nombre="Talla" />
        <Metrica valor={imc} unidad="" nombre="IMC" />
        <Metrica valor={l?.grasa} unidad="%" nombre="Grasa corporal" />
        <Metrica valor={l?.musculo} unidad="kg" nombre="Masa muscular" />
        <Metrica valor={l?.pulso} unidad="lpm" nombre="Pulso" />
      </div>
      <div className="mt-4 rounded-3xl bg-tarjeta px-6 py-5">
        <p className="text-[40px] font-extrabold leading-none">
          {l ? `${l.sistolica} / ${l.diastolica}` : '— / —'} <span className="text-[24px] font-semibold text-suave">mmHg</span>
        </p>
        <p className="mt-2 text-[20px] text-suave">Presión arterial</p>
      </div>
      <div className="mt-5 space-y-3">
        {estado.cargando && <p className="text-[22px] text-suave">Midiendo…</p>}
        {estado.atipica && <Aviso>Medición no válida, avisamos al personal. Vuelve a medirte.</Aviso>}
        {estado.medicionValida && <p className="text-[22px] font-semibold text-teal">✓ Medición registrada</p>}
        {estado.error && <Aviso onCerrar={limpiarError}>{estado.error}</Aviso>}
      </div>
    </Marco>
  )
}
