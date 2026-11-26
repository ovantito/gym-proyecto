"""Prueba de humo del flujo completo contra un backend YA levantado.

    DEMO_STATION_KEY=... ESTACION_ID=... python backend/scripts/demo_flujo.py [URL]
"""
import json
import os
import sys

import httpx

URL = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000').rstrip('/') + '/v1'
H = {'X-Station-Key': os.environ['DEMO_STATION_KEY']}


def mostrar(titulo, r):
    print(f'\n=== {titulo} -> HTTP {r.status_code}')
    print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:900])
    return r.json()


with httpx.Client(timeout=30) as c:
    mostrar('GET /salud', c.get(f'{URL}/salud'))
    print('\nSin clave ->', c.post(f'{URL}/estaciones/x/sesiones', json={'dni': '10000010'}).status_code)
    est_id = os.environ['ESTACION_ID']   # el backend en modo demo lo imprime al arrancar
    ses = mostrar('POST /estaciones/{id}/sesiones', c.post(f'{URL}/estaciones/{est_id}/sesiones', json={'dni': '10000010'}, headers=H))
    sid = ses['socio']['id']
    mostrar('POST mediciones', c.post(f'{URL}/socios/{sid}/mediciones', headers=H, json={
        'peso_kg': 62.0, 'grasa_pct': 27.5, 'presion_sistolica': 118, 'presion_diastolica': 76, 'pulso_reposo': 72}))
    mostrar('POST mediciones (+6.5 kg, sensor fallando)', c.post(f'{URL}/socios/{sid}/mediciones', headers=H, json={
        'peso_kg': 68.5, 'grasa_pct': 27.5, 'presion_sistolica': 118, 'presion_diastolica': 76, 'pulso_reposo': 72}))
    mostrar('PUT ficha-salud (lesión de rodilla)', c.put(f'{URL}/socios/{sid}/ficha-salud', headers=H, json={
        'parq': [False] * 7, 'lesiones': ['rodilla']}))
    mostrar('POST rutinas/generar (lunes 19:00)', c.post(f'{URL}/socios/{sid}/rutinas/generar', headers=H, json={'hora': 19, 'dia': 0}))
