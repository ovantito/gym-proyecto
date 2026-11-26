"""Qué video del bucket de Cloudflare R2 corresponde a cada ejercicio (máquina) de la sala.

Los videos están organizados por grupo muscular. Los marcados con (~) son el video MÁS PARECIDO disponible,
porque en el bucket no hay uno específico de esa máquina; conviene reemplazarlos cuando se grabe el exacto.
Si un ejercicio no está en esta tabla, se usa <R2_PREFIJO><id>.mp4.
"""
VIDEOS: dict[str, str] = {
    'E-M-01': 'pierna_cuadriceps/Prensa-de-pierna.mp4',                                      # Prensa 45°
    'E-M-02': 'gluteo_pierna_cuadriceps/Sentadilla-con-barra.mp4',                           # Sentadilla en Smith (~)
    'E-M-03': 'pierna_cuadriceps/Sentadilla-con-barra-landmine-en-talones-elevados.mp4',     # Hack squat (~)
    'E-M-04': 'pierna_isquios/Curl-de-isquiotibiales.mp4',                                   # Curl femoral
    'E-M-05': 'gluteo_pierna_isquios/hip-thrust-en-máquina.mp4',                             # Hip thrust
    'E-M-06': 'gluteo/peso-muerto-rumano-con-barra.mp4',                                     # Peso muerto rumano
    'E-M-07': 'pecho/Press-con-mancuernas-sentado.mp4',                                      # Press de pecho (~)
    'E-M-08': 'pecho/press-de-banca-con-barra.mp4',                                          # Press banca
    'E-M-09': 'pecho/aperturas-en-máquina.mp4',                                              # Aperturas en máquina
    'E-M-10': 'espalda/Jalón-al-pecho.mp4',                                                  # Jalón al pecho
    'E-M-11': 'espalda/dominadas.mp4',                                                       # Dominadas asistidas (~)
    'E-M-12': 'espalda/remo-en-polea-baja.mp4',                                              # Remo en polea
    'E-M-13': 'hombro_anterior/Press-de-hombros-con-mancuernas.mp4',                         # Press de hombro
    'E-M-14': 'hombro_anterior/press-militar.mp4',                                           # Press militar
    'E-M-15': 'hombro_lateral/elevaciones-laterales-con-mancuernas.mp4',                     # Elevaciones laterales
    'E-M-16': 'abdomen/crunches-en-polea-de-rodillas.mp4',                                   # Crunch en máquina (~)
    'E-M-17': 'abdomen/plancha-abdominal.mp4',                                               # Plancha en banco (~)
    'E-M-18': 'abdomen/Abdominales-con-rueda.mp4',                                           # Rueda abdominal
}
