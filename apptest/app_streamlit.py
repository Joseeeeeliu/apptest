"""
APLICACIÓN STREAMLIT PARA SIMULADOR SAG - VERSIÓN CORREGIDA
Sin matplotlib, con inicialización correcta de variables
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import time

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="Simulador Planta Concentradora",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. INICIALIZACIÓN DE VARIABLES DE SESIÓN (CRÍTICO)
# Esto se ejecuta ANTES de cualquier otra cosa

# Verificar si las variables de sesión existen, si no, crearlas
if 'simulador_inicializado' not in st.session_state:
    st.session_state.simulador_inicializado = False
    st.session_state.simulando = False
    st.session_state.estado_actual = {
        'tiempo': 0.0,
        'M_sag': 10.0,
        'W_sag': 5.0,
        'M_cu_sag': 0.072,
        'F_chancado': 0.0,
        'L_chancado': 0.0072,
        'F_finos': 0.0,
        'F_sobre_tamano': 0.0
    }
    st.session_state.historial = {
        't': [],
        'M_sag': [],
        'W_sag': [],
        'M_cu_sag': [],
        'F_chancado': [],
        'L_chancado': [],
        'F_finos': [],
        'F_sobre_tamano': []
    }
    st.session_state.objetivos = {
        'F_target': 2000.0,
        'L_target': 0.0072
    }

# 3. TÍTULO
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("---")

# 4. BARRA LATERAL CON CONTROLES
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    # Estado de simulación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Iniciar", type="primary", use_container_width=True):
            st.session_state.simulando = True
            st.rerun()
    
    with col2:
        if st.button("⏸️ Pausar", use_container_width=True):
            st.session_state.simulando = False
            st.rerun()
    
    if st.button("🔄 Reiniciar", use_container_width=True):
        # Resetear todo
        st.session_state.simulando = False
        st.session_state.estado_actual = {
            'tiempo': 0.0,
            'M_sag': 10.0,
            'W_sag': 5.0,
            'M_cu_sag': 0.072,
            'F_chancado': 0.0,
            'L_chancado': 0.0072,
            'F_finos': 0.0,
            'F_sobre_tamano': 0.0
        }
        st.session_state.historial = {
            't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
            'F_chancado': [], 'L_chancado': [], 'F_finos': [],
            'F_sobre_tamano': []
        }
        st.rerun()
    
    st.markdown("---")
    
    # CONTROLES DESLIZANTES
    st.subheader("📊 **Parámetros de Operación**")
    
    # Flujo objetivo
    F_objetivo = st.slider(
        "**Flujo Objetivo (t/h)**",
        min_value=500.0,
        max_value=3000.0,
        value=st.session_state.objetivos['F_target'],
        step=50.0
    )
    
    # Ley objetivo
    L_objetivo = st.slider(
        "**Ley Objetivo (%)**",
        min_value=0.1,
        max_value=2.0,
        value=st.session_state.objetivos['L_target'] * 100,
        step=0.05,
        format="%.2f"
    )
    
    # Actualizar objetivos
    st.session_state.objetivos['F_target'] = F_objetivo
    st.session_state.objetivos['L_target'] = L_objetivo / 100.0
    
    st.markdown("---")
    
    # MOSTRAR ESTADO ACTUAL
    st.subheader("📈 **Estado Actual**")
    
    estado = st.session_state.estado_actual  # AHORA SÍ EXISTE
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Flujo Actual", f"{estado['F_chancado']:.1f} t/h")
        st.metric("Masa Sólidos", f"{estado['M_sag']:.1f} ton")
    with col2:
        st.metric("Ley Actual", f"{estado['L_chancado']*100:.2f} %")
        st.metric("Tiempo", f"{estado['tiempo']:.1f} h")

# 5. SIMULACIÓN SIMPLIFICADA (sin threads)
def simular_paso():
    """Simula un paso de tiempo simple"""
    
    estado = st.session_state.estado_actual
    objetivos = st.session_state.objetivos
    
    # Incrementar tiempo
    dt = 1/60  # 1 minuto en horas
    estado['tiempo'] += dt
    
    # Dinámica simple de primer orden para flujo
    tau = 0.5  # Constante de tiempo (horas)
    dF = (objetivos['F_target'] - estado['F_chancado']) / tau
    estado['F_chancado'] += dF * dt
    
    # Dinámica simple para ley
    dL = (objetivos['L_target'] - estado['L_chancado']) / (tau * 2)
    estado['L_chancado'] += dL * dt
    
    # Variabilidad (simulación de perturbaciones)
    if estado['tiempo'] > 2.0:
        variacion = 0.02 * np.sin(0.3 * estado['tiempo'])
        estado['F_chancado'] *= (1 + variacion)
    
    # Cálculos simples del SAG
    # Recirculación (con retardo simple)
    if estado['tiempo'] > 1.5/60:  # 1.5 minutos en horas
        estado['F_sobre_tamano'] = 0.11 * estado['F_chancado']
    
    # Descarga
    k = 1.0/60  # 1/h convertido a 1/min
    F_descarga = k * estado['M_sag']
    
    # Finos
    if estado['tiempo'] > 0.8/60:  # 0.8 minutos
        estado['F_finos'] = max(0, F_descarga - estado['F_sobre_tamano'])
    
    # Balance de masa simple
    F_entrada = estado['F_chancado'] + estado['F_sobre_tamano']
    dM_dt = (F_entrada - F_descarga) / 60.0
    estado['M_sag'] += dM_dt * dt
    
    # Balance de cobre simple
    L_sag = estado['M_cu_sag'] / max(estado['M_sag'], 0.001)
    dMcu_dt = (estado['L_chancado'] * estado['F_chancado'] + 
               L_sag * estado['F_sobre_tamano'] - 
               L_sag * F_descarga) / 60.0
    estado['M_cu_sag'] += dMcu_dt * dt
    
    # Guardar en historial (cada 10 pasos)
    if int(estado['tiempo'] / dt) % 10 == 0:
        for key in st.session_state.historial:
            if key in estado:
                st.session_state.historial[key].append(estado[key])
    
    return estado

# 6. EJECUTAR SIMULACIÓN SI ESTÁ ACTIVA
if st.session_state.simulando:
    # Ejecutar varios pasos para avanzar en el tiempo
    for _ in range(10):  # 10 pasos por actualización
        st.session_state.estado_actual = simular_paso()

# 7. CONTENEDORES PARA GRÁFICOS
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Balance de Sólidos")
    contenedor1 = st.empty()
    
with col2:
    st.subheader("⚖️ Masas en Molino SAG")
    contenedor2 = st.empty()

col3, col4 = st.columns(2)

with col3:
    st.subheader("📈 Balance de Cobre")
    contenedor3 = st.empty()
    
with col4:
    st.subheader("🔬 Comparación de Leyes")
    contenedor4 = st.empty()

# 8. CREAR GRÁFICOS
def crear_grafico_balance():
    """Crea gráfico de balance de sólidos"""
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 0:
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_chancado'],
            name='Chancado', line=dict(color='blue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_finos'],
            name='Finos', line=dict(color='green', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_sobre_tamano'],
            name='Sobretamaño', line=dict(color='red', width=2)
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        showlegend=True
    )
    
    return fig

def crear_grafico_masas():
    """Crea gráfico de masas en el SAG"""
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 0:
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['M_sag'],
            name='Sólidos SAG', line=dict(color='blue', width=2),
            yaxis='y1'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['W_sag'],
            name='Agua SAG', line=dict(color='red', width=2),
            yaxis='y1'
        ))
        
        # Cobre en kg para mejor escala
        M_cu_kg = np.array(st.session_state.historial['M_cu_sag']) * 1000
        fig.add_trace(go.Scatter(
            x=t, y=M_cu_kg,
            name='Cobre (kg)', line=dict(color='orange', width=2, dash='dot'),
            yaxis='y2'
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis=dict(title="Masa Sólidos/Agua (ton)"),
        yaxis2=dict(
            title="Cobre (kg)",
            overlaying="y",
            side="right"
        ),
        showlegend=True
    )
    
    return fig

# 9. ACTUALIZAR GRÁFICOS
contenedor1.plotly_chart(crear_grafico_balance(), use_container_width=True)
contenedor2.plotly_chart(crear_grafico_masas(), use_container_width=True)

# 10. INFORMACIÓN ADICIONAL
st.markdown("---")
st.info("""
**Instrucciones:**
1. Ajusta los controles deslizantes para cambiar los objetivos
2. Haz clic en 'Iniciar' para comenzar la simulación
3. Haz clic en 'Pausar' para detener
4. Haz clic en 'Reiniciar' para volver al inicio
""")

# 11. AUTO-ACTUALIZACIÓN (para simulación en tiempo real)
if st.session_state.simulando:
    time.sleep(0.1)  # Pequeña pausa
    st.rerun()  # Esto hace que Streamlit se actualice automáticamente
