"""
SIMULADOR SAG - VERSIÓN CON AUTO-AVANCE Y VARIABILIDAD ORIGINAL
Actualización automática + comportamiento aleatorio realista
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import time
import random

# ================= CONFIGURACIÓN INICIAL =================
st.set_page_config(
    page_title="Simulador Planta SAG",
    page_icon="🏭",
    layout="wide"
)

# ================= INICIALIZACIÓN DE ESTADO =================
if 'inicializado' not in st.session_state:
    # Variables de control
    st.session_state.inicializado = True
    st.session_state.simulando = False
    st.session_state.ultima_actualizacion = 0
    st.session_state.semilla_aleatoria = random.randint(1, 10000)
    
    # Parámetros del modelo (iguales a la versión original)
    st.session_state.params = {
        'F_nominal': 45000/(24*0.94),  # ~2000 t/h
        'L_nominal': 0.0072,
        'fraccion_recirculacion': 0.11,
        'humedad_alimentacion': 0.035,
        'humedad_sag': 0.30,
        'humedad_recirculacion': 0.08,
        'k_descarga': 0.5,  # 1/hora - ajustado para estabilidad
        'tau_recirculacion': 1.5,  # horas
        'tau_finos': 0.8,  # horas
        'tau_arranque': 0.5  # horas
    }
    
    # Estado actual del sistema
    st.session_state.estado = {
        'tiempo': 0.0,                    # horas
        'M_sag': 100.0,                   # ton
        'W_sag': 42.86,                   # ton (para 30% humedad)
        'M_cu_sag': 0.72,                 # ton (0.72% de 100 ton)
        'F_chancado': 0.0,                # t/h
        'L_chancado': 0.0072,             # 0.72%
        'F_finos': 0.0,                   # t/h
        'F_sobre_tamano': 0.0,            # t/h
        'H_sag': 0.30,                    # 30%
        'variacion_actual': 0.0,          # para tracking
        'ley_variacion': 0.0              # para tracking
    }
    
    # Objetivos
    st.session_state.objetivos = {
        'F_target': 2000.0,               # t/h
        'L_target': 0.0072                # 0.72%
    }
    
    # Historial para gráficos
    st.session_state.historial = {
        't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
        'F_chancado': [], 'L_chancado': [], 'F_finos': [],
        'F_sobre_tamano': [], 'F_target': [], 'L_target': []
    }

# ================= FUNCIÓN DE SIMULACIÓN CON VARIABILIDAD =================
def simular_paso():
    """Ejecuta un paso de simulación con variabilidad realista"""
    estado = st.session_state.estado
    objetivos = st.session_state.objetivos
    params = st.session_state.params
    
    # Paso de tiempo (1 minuto en horas)
    dt = 1/60.0
    
    # Actualizar tiempo
    estado['tiempo'] += dt
    
    # ========== ARRANQUE GRADUAL (como en el original) ==========
    if estado['tiempo'] > 0:
        factor_arranque = 1 - np.exp(-estado['tiempo'] / params['tau_arranque'])
    else:
        factor_arranque = 0
    
    # ========== VARIABILIDAD ALEATORIA (como en el original) ==========
    # Usar semilla reproducible para consistencia
    np.random.seed(st.session_state.semilla_aleatoria + int(estado['tiempo']*100))
    
    perturbacion = 0
    lenta = media = rapida = 0
    
    if estado['tiempo'] > 2.0:  # Después de 2 horas
        # Componentes de variabilidad (igual que el código original)
        lenta = 0.02 * np.sin(0.3 * estado['tiempo']) + 0.01 * np.sin(0.7 * estado['tiempo'] + 1)
        media = 0.01 * np.sin(2.0 * estado['tiempo'] + 2)
        rapida = 0.005 * np.random.normal(0, 1)
        
        # Perturbaciones aleatorias (ocasionales)
        if np.random.random() < 0.002:  # 0.2% de probabilidad
            perturbacion += np.random.uniform(-0.04, -0.02)
        if np.random.random() < 0.0003:  # 0.03% de probabilidad
            perturbacion += np.random.uniform(-0.1, -0.05)
    
    random_factor = 1 + lenta + media + rapida + perturbacion
    
    # ========== DINÁMICA DE ALIMENTACIÓN ==========
    # Flujo sigue objetivo con dinámica de primer orden
    tau_F = 0.5  # 0.5 horas para cambios
    error_F = objetivos['F_target'] - estado['F_chancado']
    dF_dt = error_F / tau_F
    estado['F_chancado'] += dF_dt * dt
    
    # Aplicar variabilidad y arranque gradual
    estado['F_chancado'] = estado['F_chancado'] * factor_arranque * random_factor
    
    # Limitar valores físicos
    estado['F_chancado'] = np.clip(estado['F_chancado'], 
                                  0.1 * objetivos['F_target'], 
                                  1.5 * objetivos['F_target'])
    
    # ========== DINÁMICA DE LEY ==========
    # Variabilidad en la ley (como en el original)
    if estado['tiempo'] > 0:
        ley_variacion = 0.02 * np.sin(0.5 * estado['tiempo'] + 3) + 0.01 * np.random.normal(0, 0.5)
        estado['L_chancado'] = params['L_nominal'] * (1 + 0.08 * ley_variacion)
        estado['L_chancado'] = np.clip(estado['L_chancado'], 
                                     0.7 * params['L_nominal'], 
                                     1.3 * params['L_nominal'])
        estado['ley_variacion'] = ley_variacion  # Para tracking
    
    # Perseguir objetivo de ley
    tau_L = 2.0
    error_L = objetivos['L_target'] - estado['L_chancado']
    dL_dt = error_L / tau_L
    estado['L_chancado'] += dL_dt * dt
    
    estado['variacion_actual'] = (random_factor - 1) * 100  # Para mostrar en porcentaje
    
    # ========== CÁLCULOS DEL SAG ==========
    # Recirculación (con retardo)
    if estado['tiempo'] > params['tau_recirculacion']:
        # Simplificación: usar flujo actual con factor de reducción
        estado['F_sobre_tamano'] = params['fraccion_recirculacion'] * estado['F_chancado'] * 0.9
    else:
        estado['F_sobre_tamano'] = 0.0
    
    # Alimentación total al SAG
    F_alimentacion_total = estado['F_chancado'] + estado['F_sobre_tamano']
    
    # ========== BALANCE DE MASA ==========
    # Descarga del SAG
    F_descarga = params['k_descarga'] * estado['M_sag']  # t/h
    
    # Finos (con retardo)
    if estado['tiempo'] > params['tau_finos']:
        estado['F_finos'] = max(F_descarga - estado['F_sobre_tamano'], 0)
        
        # Crecimiento gradual de finos (como en el original)
        if estado['tiempo'] < params['tau_finos'] + 1.0:
            factor_crecimiento = 1 - np.exp(-(estado['tiempo'] - params['tau_finos']) / 0.3)
            estado['F_finos'] *= factor_crecimiento
    else:
        estado['F_finos'] = 0
    
    # ========== ECUACIONES DIFERENCIALES ==========
    # Balance de masa sólida (convertido a t/min)
    dM_dt = (F_alimentacion_total - F_descarga) / 60.0
    estado['M_sag'] += dM_dt * dt
    estado['M_sag'] = max(estado['M_sag'], 10.0)  # Mínimo físico
    
    # Balance de cobre
    if estado['M_sag'] > 0.1:
        L_sag = estado['M_cu_sag'] / estado['M_sag']
    else:
        L_sag = estado['L_chancado']
    
    # Flujos de cobre (convertido a t/min)
    entrada_cu = (estado['L_chancado'] * estado['F_chancado'] + 
                  L_sag * estado['F_sobre_tamano']) / 60.0
    salida_cu = (L_sag * F_descarga) / 60.0
    dMcu_dt = entrada_cu - salida_cu
    estado['M_cu_sag'] += dMcu_dt * dt
    estado['M_cu_sag'] = max(estado['M_cu_sag'], 0.001)
    
    # Balance de agua (simplificado)
    agua_necesaria = estado['M_sag'] * (params['humedad_sag'] / (1 - params['humedad_sag']))
    estado['W_sag'] = agua_necesaria
    
    # Humedad actual
    estado['H_sag'] = estado['W_sag'] / max(estado['M_sag'] + estado['W_sag'], 0.001)
    
    # ========== GUARDAR HISTORIAL ==========
    # Guardar cada 10 pasos (aproximadamente cada 10 segundos reales)
    if int(estado['tiempo'] / dt) % 10 == 0:
        max_puntos = 24 * 360  # 10 puntos por hora por 24 horas
        
        for key in ['t', 'M_sag', 'W_sag', 'M_cu_sag', 
                    'F_chancado', 'L_chancado', 'F_finos', 'F_sobre_tamano']:
            if key == 't':
                valor = estado['tiempo']
            else:
                valor = estado[key]
            
            st.session_state.historial[key].append(valor)
            
            # Mantener tamaño manejable
            if len(st.session_state.historial[key]) > max_puntos:
                st.session_state.historial[key] = st.session_state.historial[key][-max_puntos:]
        
        # Guardar objetivos
        st.session_state.historial['F_target'].append(objetivos['F_target'])
        st.session_state.historial['L_target'].append(objetivos['L_target'])
        
        if len(st.session_state.historial['F_target']) > max_puntos:
            st.session_state.historial['F_target'] = st.session_state.historial['F_target'][-max_puntos:]
            st.session_state.historial['L_target'] = st.session_state.historial['L_target'][-max_puntos:]

# ================= FUNCIONES PARA BOTONES =================
def iniciar_simulacion():
    st.session_state.simulando = True
    st.session_state.ultima_actualizacion = time.time()
    st.session_state.semilla_aleatoria = random.randint(1, 10000)

def pausar_simulacion():
    st.session_state.simulando = False

def reiniciar_simulacion():
    st.session_state.simulando = False
    st.session_state.estado = {
        'tiempo': 0.0,
        'M_sag': 100.0,
        'W_sag': 42.86,
        'M_cu_sag': 0.72,
        'F_chancado': 0.0,
        'L_chancado': 0.0072,
        'F_finos': 0.0,
        'F_sobre_tamano': 0.0,
        'H_sag': 0.30,
        'variacion_actual': 0.0,
        'ley_variacion': 0.0
    }
    for key in st.session_state.historial:
        st.session_state.historial[key] = []
    st.session_state.semilla_aleatoria = random.randint(1, 10000)

# ================= EJECUTAR SIMULACIÓN SI ESTÁ ACTIVA =================
# Esta es la parte CRÍTICA: avanzar la simulación si está activa
if st.session_state.simulando:
    # Verificar cuánto tiempo ha pasado desde la última actualización
    tiempo_actual = time.time()
    
    # Si es la primera vez o ha pasado más de 0.1 segundos
    if st.session_state.ultima_actualizacion == 0 or tiempo_actual - st.session_state.ultima_actualizacion > 0.1:
        # Ejecutar un paso de simulación
        simular_paso()
        st.session_state.ultima_actualizacion = tiempo_actual
        
        # Forzar una actualización de la interfaz
        st.rerun()

# ================= INTERFAZ PRINCIPAL =================
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("---")

# ================= BARRA LATERAL =================
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    # Estado de la simulación
    estado_sim = "🟢 EJECUTANDO" if st.session_state.simulando else "⏸️ PAUSADA"
    st.markdown(f"**Estado:** {estado_sim}")
    
    # Botones
    col1, col2 = st.columns(2)
    with col1:
        st.button("▶️ Iniciar", 
                 on_click=iniciar_simulacion,
                 type="primary",
                 use_container_width=True,
                 disabled=st.session_state.simulando)
    
    with col2:
        st.button("⏸️ Pausar",
                 on_click=pausar_simulacion,
                 use_container_width=True,
                 disabled=not st.session_state.simulando)
    
    st.button("🔄 Reiniciar",
             on_click=reiniciar_simulacion,
             use_container_width=True)
    
    st.markdown("---")
    
    # ========== OBJETIVOS ==========
    st.subheader("🎯 **Objetivos de Operación**")
    
    F_objetivo = st.slider(
        "**Flujo (t/h)**",
        500.0, 5000.0, st.session_state.objetivos['F_target'],
        step=100.0,
        key="slider_flujo"
    )
    
    L_objetivo = st.slider(
        "**Ley (%)**",
        0.3, 1.5, st.session_state.objetivos['L_target'] * 100,
        step=0.05,
        format="%.2f",
        key="slider_ley"
    )
    
    # Actualizar objetivos
    st.session_state.objetivos['F_target'] = F_objetivo
    st.session_state.objetivos['L_target'] = L_objetivo / 100.0
    
    st.markdown("---")
    
    # ========== PARÁMETROS ==========
    with st.expander("⚙️ **Parámetros Avanzados**"):
        k_valor = st.slider(
            "Constante descarga (k) [1/hora]",
            0.1, 2.0, st.session_state.params['k_descarga'], 0.1,
            help="k = Descarga / Masa. Valores más altos = masa menor en equilibrio"
        )
        st.session_state.params['k_descarga'] = k_valor
        
        recirc = st.slider(
            "Recirculación (%)",
            5.0, 20.0, st.session_state.params['fraccion_recirculacion'] * 100, 1.0
        )
        st.session_state.params['fraccion_recirculacion'] = recirc / 100.0
    
    st.markdown("---")
    
    # ========== ESTADO ACTUAL ==========
    st.subheader("📊 **Estado Actual**")
    estado = st.session_state.estado
    params = st.session_state.params
    
    # Cálculos para mostrar
    F_alimentacion = estado['F_chancado'] + estado['F_sobre_tamano']
    F_descarga = params['k_descarga'] * estado['M_sag']
    balance = F_alimentacion - F_descarga
    M_equilibrio = F_alimentacion / params['k_descarga'] if params['k_descarga'] > 0 else 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Flujo Chancado", f"{estado['F_chancado']:.0f} t/h")
        st.metric("Masa SAG", f"{estado['M_sag']:.0f} t")
        st.metric("Recirculación", f"{estado['F_sobre_tamano']:.0f} t/h")
    
    with col2:
        st.metric("Ley", f"{estado['L_chancado']*100:.2f} %")
        st.metric("Finos", f"{estado['F_finos']:.0f} t/h")
        st.metric("Variación", f"{estado['variacion_actual']:.1f}%")
    
    # Indicador de equilibrio
    equilibrio = min(abs(balance)/1000, 1.0)
    color = "🟢" if abs(balance) < 100 else "🟡" if abs(balance) < 500 else "🔴"
    st.progress(equilibrio, 
               text=f"{color} Balance: {balance:.0f} t/h (Objetivo: {M_equilibrio:.0f} t)")

# ================= GRÁFICOS =================
# Función para gráfico de balance
def crear_grafico_balance():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_chancado'],
            name='Chancado', line=dict(color='blue', width=2),
            hovertemplate='%{y:.0f} t/h<extra>Chancado</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_finos'],
            name='Finos', line=dict(color='green', width=2),
            hovertemplate='%{y:.0f} t/h<extra>Finos</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_sobre_tamano'],
            name='Sobretamaño', line=dict(color='red', width=2),
            hovertemplate='%{y:.0f} t/h<extra>Sobretamaño</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_target'],
            name='Objetivo', line=dict(color='black', width=2, dash='dash'),
            hovertemplate='%{y:.0f} t/h<extra>Objetivo</extra>'
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# Función para gráfico de masas
def crear_grafico_masas():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        # Masa esperada en equilibrio teórico
        masa_teorica = np.array(st.session_state.historial['F_target']) / st.session_state.params['k_descarga']
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['M_sag'],
            name='Masa Real', line=dict(color='blue', width=3),
            hovertemplate='%{y:.0f} t<extra>Masa Real</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=masa_teorica,
            name='Masa Teórica', line=dict(color='gray', width=2, dash='dash'),
            hovertemplate='%{y:.0f} t<extra>Masa Teórica</extra>'
        ))
        
        # Cobre (escala secundaria)
        M_cu_kg = np.array(st.session_state.historial['M_cu_sag']) * 1000
        fig.add_trace(go.Scatter(
            x=t, y=M_cu_kg,
            name='Cobre (kg)', line=dict(color='orange', width=2),
            yaxis='y2',
            hovertemplate='%{y:.0f} kg<extra>Cobre</extra>'
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis=dict(title="Masa Sólidos (t)"),
        yaxis2=dict(
            title="Cobre (kg)",
            overlaying="y",
            side="right"
        ),
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=60, t=40, b=20)
    )
    
    return fig

# Función para gráfico de cobre
def crear_grafico_cobre():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        # Calcular ley del SAG
        M_cu = np.array(st.session_state.historial['M_cu_sag'])
        M_sag = np.array(st.session_state.historial['M_sag'])
        with np.errstate(divide='ignore', invalid='ignore'):
            L_sag = np.where(M_sag > 0.1, M_cu / M_sag, 0)
        
        # Flujos de cobre
        F_cu_chancado = np.array(st.session_state.historial['F_chancado']) * np.array(st.session_state.historial['L_chancado'])
        F_cu_finos = np.array(st.session_state.historial['F_finos']) * L_sag
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado,
            name='Cobre Chancado', line=dict(color='darkblue', width=2),
            hovertemplate='%{y:.3f} t/h<extra>Cobre Chancado</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_finos,
            name='Cobre Finos', line=dict(color='darkgreen', width=2),
            hovertemplate='%{y:.3f} t/h<extra>Cobre Finos</extra>'
        ))
        
        # Total
        F_cu_total = F_cu_chancado + F_cu_finos
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_total,
            name='Total', line=dict(color='black', width=1, dash='dot'),
            hovertemplate='%{y:.3f} t/h<extra>Total Cobre</extra>'
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo Cobre (t/h)",
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# Función para gráfico de leyes
def crear_grafico_leyes():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        # Calcular ley del SAG
        M_cu = np.array(st.session_state.historial['M_cu_sag'])
        M_sag = np.array(st.session_state.historial['M_sag'])
        with np.errstate(divide='ignore', invalid='ignore'):
            L_sag = np.where(M_sag > 0.1, M_cu / M_sag * 100, 0)
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(st.session_state.historial['L_chancado']) * 100,
            name='Ley Chancado', line=dict(color='blue', width=2),
            hovertemplate='%{y:.2f}%<extra>Ley Chancado</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=L_sag,
            name='Ley SAG', line=dict(color='orange', width=2),
            hovertemplate='%{y:.2f}%<extra>Ley SAG</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(st.session_state.historial['L_target']) * 100,
            name='Objetivo', line=dict(color='black', width=2, dash='dash'),
            hovertemplate='%{y:.2f}%<extra>Objetivo Ley</extra>'
        ))
    
    # Calcular rango dinámico para el eje Y
    if len(t) > 1:
        todos_valores = list(np.array(st.session_state.historial['L_chancado']) * 100)
        if len(L_sag) > 0:
            todos_valores.extend(L_sag)
        todos_valores.extend(np.array(st.session_state.historial['L_target']) * 100)
        
        y_min = max(0, min(todos_valores) * 0.9)
        y_max = min(2.0, max(todos_valores) * 1.1)
    else:
        y_min, y_max = 0, 1.5
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Ley (%)",
        yaxis=dict(range=[y_min, y_max]),
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# ================= MOSTRAR GRÁFICOS =================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Balance de Sólidos")
    st.plotly_chart(crear_grafico_balance(), use_container_width=True)

with col2:
    st.subheader("⚖️ Masas en Molino SAG")
    st.plotly_chart(crear_grafico_masas(), use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.subheader("📈 Flujos de Cobre")
    st.plotly_chart(crear_grafico_cobre(), use_container_width=True)

with col4:
    st.subheader("🔬 Comparación de Leyes")
    st.plotly_chart(crear_grafico_leyes(), use_container_width=True)

# ================= INFORMACIÓN =================
st.markdown("---")

with st.expander("📈 **Comportamiento Esperado**"):
    st.markdown("""
    ### **✅ Variabilidad incluida (recuperada del código original):**
    
    1. **Componente lenta**: Ondas sinusoidales largas (±2%)
    2. **Componente media**: Ondas más rápidas (±1%)
    3. **Componente rápida**: Ruido aleatorio (±0.5%)
    4. **Perturbaciones**: Eventos aleatorios ocasionales (-4% a -10%)
    5. **Variabilidad en ley**: ±8% alrededor del objetivo
    
    ### **🔄 Auto-avance activado:**
    
    - La simulación avanza **automáticamente** cuando está en estado EJECUTANDO
    - 1 segundo real ≈ varios minutos simulados
    - Los gráficos se actualizan en tiempo real
    
    ### **⚖️ Balance de masa corregido:**
    
    La masa se estabiliza en: **M = F_entrada / k**
    
    Ejemplos:
    - F=2000 t/h, k=0.5 → M=4000 toneladas
    - F=1000 t/h, k=0.5 → M=2000 toneladas
    - F=2000 t/h, k=1.0 → M=2000 toneladas
    """)

# ================= PIE DE PÁGINA =================
st.markdown("---")

# Mostrar información de tiempo y estado
estado = st.session_state.estado
params = st.session_state.params
F_alimentacion = estado['F_chancado'] + estado['F_sobre_tamano']
F_descarga = params['k_descarga'] * estado['M_sag']
M_equilibrio = F_alimentacion / params['k_descarga'] if params['k_descarga'] > 0 else 0
balance = F_alimentacion - F_descarga

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Tiempo Simulado", f"{estado['tiempo']:.1f} h")
with col2:
    velocidad = "60x" if st.session_state.simulando else "0x"
    st.metric("Velocidad", velocidad)
with col3:
    st.metric("Masa Actual", f"{estado['M_sag']:.0f} t")
with col4:
    st.metric("Equilibrio Esperado", f"{M_equilibrio:.0f} t")

# Mensaje de estado final
st.markdown("---")
if not st.session_state.simulando:
    st.info("⏸️ **Simulación PAUSADA** - Haz clic en **INICIAR** para comenzar la simulación automática")
elif abs(balance) < 100:
    st.success(f"✅ **Sistema ESTABLE** - Balance: {balance:.0f} t/h (Masa cercana al equilibrio)")
else:
    st.warning(f"🔄 **Sistema BUSCANDO equilibrio** - Balance: {balance:.0f} t/h")

# ================= TRUCO FINAL: AUTO-ACTUALIZACIÓN GARANTIZADA =================
# Este es el secreto: crear un placeholder que force la actualización periódica
if st.session_state.simulando:
    # Crear un contador oculto que fuerza la actualización
    if 'contador_auto' not in st.session_state:
        st.session_state.contador_auto = 0
    
    st.session_state.contador_auto += 1
    
    # Cada 2 incrementos, forzar un rerun si está simulando
    if st.session_state.contador_auto % 2 == 0:
        # Pequeña pausa para no sobrecargar
        time.sleep(0.05)
        st.rerun()
