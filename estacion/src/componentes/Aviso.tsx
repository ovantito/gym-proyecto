/** Mensaje de error/aviso visible; nunca deja la pantalla en blanco. */
export function Aviso({ tipo = 'error', children, onCerrar }: { tipo?: 'error' | 'info'; children: React.ReactNode; onCerrar?: () => void }) {
  return (
    <div
      role="alert"
      className={`flex items-center justify-between gap-6 rounded-2xl border-2 px-6 py-4 text-[22px] font-semibold ${
        tipo === 'error' ? 'border-sem-rojo bg-sem-rojo/15 text-[#ffb4b6]' : 'border-naranja bg-naranja/10 text-naranja'
      }`}
    >
      <span>{children}</span>
      {onCerrar && (
        <button type="button" onClick={onCerrar} className="rounded-xl bg-white/10 px-5 py-2 text-[20px]">
          Entendido
        </button>
      )}
    </div>
  )
}
