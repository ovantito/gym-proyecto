"""Entrena los 4 modelos de la Estación TNT Fit y los guarda en ml/modelos/.

Mismos hiperparámetros y semilla que el Colab. Uso:  python ml/entrenar.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans, MeanShift, estimate_bandwidth
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
from datos import SEED, generar_datos  # noqa: E402

warnings.filterwarnings('ignore')

VERSION = '1.0.0'
DIR_MODELOS = Path(__file__).parent / 'modelos'

# Variables de cada modelo. OJO: var_grasa_pct es un dato de salud y NO puede estar en abandono.
VARS_AFLUENCIA = ['hora', 'dia_semana', 'mes', 'feriado']
VARS_ABANDONO_NUM = ['edad', 'antiguedad_meses', 'visitas_semana', 'dias_ultima_visita', 'hora_preferida',
                     'racha_semanas', 'sesiones_estacion', 'coach_contacto_30d']
VARS_ABANDONO_CAT = ['plan', 'semaforo']
VARS_ABANDONO = VARS_ABANDONO_NUM + VARS_ABANDONO_CAT
VARS_KMEANS = ['visitas_semana', 'dias_ultima_visita', 'antiguedad_meses', 'hora_preferida', 'edad']
VARS_MEANSHIFT = ['delta_peso_kg', 'delta_grasa_pct', 'presion_sistolica', 'duracion_seg']
K_KMEANS = 3


def entrenar_afluencia(afluencia: pd.DataFrame) -> tuple[RandomForestRegressor, dict]:
    X, y = afluencia[VARS_AFLUENCIA], afluencia['ocupacion']
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=SEED)
    rf = RandomForestRegressor(n_estimators=200, random_state=SEED).fit(Xtr, ytr)
    p = rf.predict(Xte)
    return rf, {'r2': round(r2_score(yte, p), 3), 'mae_socios': round(mean_absolute_error(yte, p), 2)}


def _rf_abandono(socios: pd.DataFrame, num: list[str], cat: list[str]):
    X, y = socios[num + cat], socios['abandono_30d']
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    prep = ColumnTransformer([('num', StandardScaler(), num), ('cat', OneHotEncoder(handle_unknown='ignore'), cat)])
    pipe = Pipeline([('prep', prep), ('m', RandomForestClassifier(
        n_estimators=300, min_samples_leaf=5, class_weight='balanced', random_state=SEED))]).fit(Xtr, ytr)
    pr = pipe.predict_proba(Xte)[:, 1]
    pred = (pr >= 0.5).astype(int)
    met = {'f1': round(f1_score(yte, pred), 3), 'roc_auc': round(roc_auc_score(yte, pr), 3),
           'precision': round(precision_score(yte, pred), 3), 'recall': round(recall_score(yte, pred), 3),
           'matriz_confusion': confusion_matrix(yte, pred).tolist()}
    return pipe, met


def entrenar_abandono(socios: pd.DataFrame):
    """Modelo de producción (sin var_grasa_pct) + referencia con las 9 variables del Colab."""
    pipe, met = _rf_abandono(socios, VARS_ABANDONO_NUM, VARS_ABANDONO_CAT)
    _, met_colab = _rf_abandono(socios, VARS_ABANDONO_NUM + ['var_grasa_pct'], VARS_ABANDONO_CAT)
    return pipe, met, met_colab


def entrenar_kmeans(socios: pd.DataFrame):
    scaler = StandardScaler().fit(socios[VARS_KMEANS])
    Z = scaler.transform(socios[VARS_KMEANS])
    km = KMeans(n_clusters=K_KMEANS, n_init=10, random_state=SEED).fit(Z)
    sil = silhouette_score(Z, km.labels_, sample_size=2000, random_state=SEED)
    # Nombre del segmento según su comportamiento medio (el orden de las etiquetas depende del ajuste)
    perfil = socios.assign(seg=km.labels_).groupby('seg')[VARS_KMEANS].mean()
    nombres = {}
    for seg, fila in perfil.iterrows():
        if fila['visitas_semana'] >= 3.5:
            nombres[int(seg)] = 'constante_manana'
        elif fila['antiguedad_meses'] >= 15:
            nombres[int(seg)] = 'veterano_fin_de_semana'
        else:
            nombres[int(seg)] = 'nocturno_nuevo'
    return km, scaler, {'k': K_KMEANS, 'silueta': round(float(sil), 3), 'nombres_segmentos': nombres,
                        'perfil': perfil.round(1).reset_index().to_dict('records')}


def entrenar_meanshift(ses: pd.DataFrame):
    muestra = ses.sample(3000, random_state=SEED).reset_index(drop=True)
    scaler = StandardScaler().fit(muestra[VARS_MEANSHIFT])
    Zs = scaler.transform(muestra[VARS_MEANSHIFT])
    bw = estimate_bandwidth(Zs, quantile=0.3, random_state=SEED)
    ms = MeanShift(bandwidth=bw, bin_seeding=True).fit(Zs)
    grandes = pd.Series(ms.labels_).value_counts()
    ids_normales = set(int(i) for i in grandes[grandes >= 0.03 * len(muestra)].index)   # grupos diminutos = atípicos
    atip = ~pd.Series(ms.labels_).isin(ids_normales).values
    met = {'grupos': int(ms.cluster_centers_.shape[0]), 'marcadas': int(atip.sum()),
           'precision': round(precision_score(muestra.defectuosa, atip), 3),
           'recall': round(recall_score(muestra.defectuosa, atip), 3),
           'f1': round(f1_score(muestra.defectuosa, atip), 3), 'clusters_normales': sorted(ids_normales)}
    return ms, scaler, met


def main() -> dict:
    d = generar_datos(SEED)
    DIR_MODELOS.mkdir(exist_ok=True)

    rf_afl, m_afl = entrenar_afluencia(d['afluencia'])
    pipe_ab, m_ab, m_ab_colab = entrenar_abandono(d['socios'])
    km, sc_km, m_km = entrenar_kmeans(d['socios'])
    ms, sc_ms, m_ms = entrenar_meanshift(d['sesiones'])

    joblib.dump(rf_afl, DIR_MODELOS / 'afluencia.joblib')
    joblib.dump(pipe_ab, DIR_MODELOS / 'abandono.joblib')
    joblib.dump(km, DIR_MODELOS / 'kmeans.joblib')
    joblib.dump(sc_km, DIR_MODELOS / 'kmeans_scaler.joblib')
    joblib.dump(ms, DIR_MODELOS / 'meanshift.joblib')
    joblib.dump(sc_ms, DIR_MODELOS / 'meanshift_scaler.joblib')

    meta = {
        'version': VERSION,
        'fecha_entrenamiento': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'semilla': SEED,
        'scikit_learn': sklearn.__version__,
        'numpy': np.__version__,
        'pandas': pd.__version__,
        'afluencia': {'tipo': 'RandomForestRegressor', 'variables': VARS_AFLUENCIA, 'metricas': m_afl},
        'abandono': {'tipo': 'RandomForestClassifier', 'variables': VARS_ABANDONO, 'metricas': m_ab,
                     'metricas_referencia_colab_con_var_grasa_pct': m_ab_colab},
        'kmeans': {'tipo': 'KMeans', 'variables': VARS_KMEANS, 'metricas': m_km},
        'meanshift': {'tipo': 'MeanShift', 'variables': VARS_MEANSHIFT, 'metricas': m_ms,
                      'clusters_normales': m_ms['clusters_normales']},
    }
    (DIR_MODELOS / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: meta[k] for k in ('afluencia', 'abandono')}, ensure_ascii=False, indent=1))
    print('K-Means:', {k: v for k, v in m_km.items() if k != 'perfil'})
    print('Mean-Shift:', {k: v for k, v in m_ms.items() if k != 'clusters_normales'})
    return meta


if __name__ == '__main__':
    main()
