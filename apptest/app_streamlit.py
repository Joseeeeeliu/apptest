"""
SIMULADOR SAG - INTERFAZ STREAMLIT
Versión con parámetros de dinámica ajustados
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import time

from simulador_sag import SimuladorSAG, crear_parametros_default

# ================= CONFIGURACIÓN =================
st.set_page_config(
    page_title="Simulador Planta Concentradora - Molino SAG",
    page_icon="🏭",
    layout="wide"
)

# ================= INICIALIZACIÓN =================
if 'simulador' not in st.session_state:
    params = crear_parametros_default()
    st.session_state.simulador = SimuladorSAG(params)
    st.session_state.simulando = False
    st.session_state.pasos_ejecutados = 0
    st.session_state.hora_inicio = time.time()
    st.session_state.velocidad_sim = 0.5

# ================= FUNCIONES DE CONTROL =================
def iniciar_simulacion():
    st.session_state.simulando = True

def pausar_simulacion():
    st.session_state.simulando = False

def reiniciar_simulacion():
    params = crear_parametros_default()
    st.session_state.simulador = SimuladorSAG(params)
    st.session_state.simulando = False
    st.session_state.pasos_ejecutados = 0
    st.session_state.hora_inicio = time.time()

# ================= EJECUTAR PASO =================
if st.session_state.simulando:
    st.session_state.simulador.paso_simulacion()
    st.session_state.pasos_ejecutados += 1

# ================= INTERFAZ PRINCIPAL =================
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("**Versión con dinámica corregida y crecimiento exponencial correcto**")
st.markdown("---")

# ================= BARRA LATERAL =================
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    estado_sim = "🟢 EJECUTANDO" if st.session_state.simulando else "⏸️ PAUSADA"
    st.metric("Estado", estado_sim)
    
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
    
    # Control de velocidad
    st.subheader("⚡ Velocidad de Simulación")
    velocidad_opciones = {
        "Muy Lenta (2s/paso)": 2.0,
        "Lenta (1s/paso)": 1.0,
        "Normal (0.5s/paso)": 0.5,
        "Rápida (0.2s/paso)": 0.2,
        "Muy Rápida (0.1s/paso)": 0.1
    }
    velocidad_seleccionada = st.selectbox(
        "Selecciona velocidad:",
        options=list(velocidad_opciones.keys()),
        index=2
    )
    st.session_state.velocidad_sim = velocidad_opciones[velocidad_seleccionada]
    
    st.markdown("---")
    
    # ========== OBJETIVOS DE OPERACIÓN ==========
    st.subheader("🎯 **Objetivos de Operación**")
    
    F_obj = st.slider(
        "**Flujo objetivo (t/h)**",
        500.0, 5000.0, 
        float(st.session_state.simulador.objetivos['F_target']),
        step=100.0,
        key="slider_flujo",
        help="Objetivo de flujo de alimentación al molino SAG"
    )
    st.session_state.simulador.actualizar_objetivo('F', F_obj)
    
    L_obj = st.slider(
        "**Ley objetivo (%)**",
        0.3, 1.5,
        float(st.session_state.simulador.objetivos['L_target'] * 100),
        step=0.05,
        format="%.2f",
        key="slider_ley",
        help="Objetivo de ley de cobre en la alimentación"
    )
    st.session_state.simulador.actualizar_objetivo('L', L_obj / 100.0)
    
    st.markdown("---")
    
    # ========== PARÁMETROS AVANZADOS ==========
    with st.expander("⚙️ **Parámetros Avanzados**"):
        
        st.subheader("🏗️ Parámetros del Sistema")
        
        k_valor = st.slider(
            "Constante de descarga (k) [1/hora]",
            0.1, 2.0,
            float(st.session_state.simulador.params['k_descarga']),
            0.1,
            help="k = Descarga / Masa. Valores más altos = respuesta más rápida del SAG"
        )
        st.session_state.simulador.params['k_descarga'] = k_valor
        
        recirc = st.slider(
            "Recirculación (%)",
            1.0, 20.0,
            float(st.session_state.simulador.params['fraccion_recirculacion'] * 100),
            1.0,
            format="%.1f"
        )
        st.session_state.simulador.params['fraccion_recirculacion'] = recirc / 100.0
        
        tau_rec = st.slider(
            "Retardo recirculación (min)",
            0, 30,
            int(st.session_state.simulador.params['tau_recirculacion']),
            step=1
        )
        st.session_state.simulador.params['tau_recirculacion'] = tau_rec
        
        tau_finos = st.slider(
            "Retardo finos (min)",
            0, 300,
            int(st.session_state.simulador.params['tau_finos']),
            step=10
        )
        st.session_state.simulador.params['tau_finos'] = tau_finos
        
        st.markdown("---")
        
        # ========== DINÁMICA DEL CHANCADO ==========
        st.subheader("⏱️ Dinámica del Chancado")
        
        # CAMBIO IMPORTANTE: Rangos más realistas
        tau_F = st.slider(
            "τ flujo (horas)",
            0.1, 2.0,  # De 0.1 a 2 horas (más realista)
            float(st.session_state.simulador.tau_F),
            0.1,
            help="Tiempo para alcanzar 63% del objetivo. Más bajo = respuesta más rápida"
        )
        st.session_state.simulador.tau_F = tau_F
        
        tau_L = st.slider(
            "τ ley (horas)",
            0.5, 3.0,  # De 0.5 a 3 horas
            float(st.session_state.simulador.tau_L),
            0.1,
            help="Tiempo para alcanzar 63% del objetivo de ley"
        )
        st.session_state.simulador.tau_L = tau_L
        
        st.markdown("---")
        
        # ========== VARIABILIDAD ==========
        st.subheader("📊 Variabilidad Natural")
        
        amp_ley = st.slider(
            "Amplitud variación ley (%)",
            0.0, 5.0,
            float(st.session_state.simulador.amplitud_variacion_ley * 100),
            0.1,
            format="%.1f",
            help="Variación máxima de la ley (± porcentaje)"
        )
        st.session_state.simulador.amplitud_variacion_ley = amp_ley / 100.0
        
        amp_flujo = st.slider(
            "Amplitud variación flujo (%)",
            0.0, 2.0,
            float(st.session_state.simulador.amplitud_variacion_flujo * 100),
            0.1,
            format="%.1f",
            help="Variación máxima del flujo (± porcentaje)"
        )
        st.session_state.simulador.amplitud_variacion_flujo = amp_flujo / 100.0
    
    st.markdown("---")
    
    # ========== ESTADO ACTUAL ==========
    st.subheader("📊 **Estado Actual**")
    estado_actual = st.session_state.simulador.obtener_estado()
    historial = st.session_state.simulador.obtener_historial()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tiempo simulado", f"{estado_actual['t']:.1f} h")
        st.metric("Flujo actual", f"{estado_actual['F_actual']:.0f} t/h")
        st.metric("Masa SAG", f"{estado_actual['M_sag']:.0f} t")
    
    with col2:
        st.metric("Ley actual", f"{estado_actual['L_actual']*100:.2f} %")
        st.metric("Humedad SAG", f"{estado_actual['H_sag']*100:.1f} %")
        
        if historial['F_finos'] and len(historial['F_finos']) > 0:
            st.metric("Finos actuales", f"{historial['F_finos'][-1]:.0f} t/h")
        else:
            st.metric("Finos actuales", "0 t/h")
    
    # Indicador de equilibrio
    if historial['F_chancado'] and len(historial['F_chancado']) > 0:
        F_chancado_actual = historial['F_chancado'][-1]
        F_sobre_actual = historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] and len(historial['F_sobre_tamano']) > 0 else 0
        F_descarga_actual = historial['F_descarga'][-1] if historial['F_descarga'] and len(historial['F_descarga']) > 0 else 0
        
        balance = F_chancado_actual + F_sobre_actual - F_descarga_actual
        
        if abs(balance) < 50:
            color = "🟢"
            texto = f"{color} Balance: {balance:.0f} t/h (Estable)"
        elif abs(balance) < 200:
            color = "🟡"
            texto = f"{color} Balance: {balance:.0f} t/h (Moderado)"
        else:
            color = "🔴"
            texto = f"{color} Balance: {balance:.0f} t/h (Inestable)"
        
        equilibrio = min(abs(balance) / max(F_chancado_actual, 1), 1.0)
        st.progress(equilibrio, text=texto)

# ================= GRÁFICOS =================
def crear_grafico_balance(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_chancado'],
            name='Chancado', line=dict(color='blue', width=2),
            hovertemplate='%{y:.0f} t/h<extra>Chancado</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_finos'],
            name='Finos', line=dict(color='green', width=2),
            hovertemplate='%{y:.0f} t/h<extra>Finos</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_sobre_tamano'],
            name='Sobretamaño', line=dict(color='red', width=2),
            hovertemplate='%{y:.0f} t/h<extra>Sobretamaño</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_target'],
            name='Objetivo', line=dict(color='black', width=2, dash='dash'),
            hovertemplate='%{y:.0f} t/h<extra>Objetivo</extra>'
        ))
    
    fig.update_layout(
        height=300,
        title="Balance de Sólidos",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def crear_grafico_masas(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        if st.session_state.simulador.params['k_descarga'] > 0:
            masa_teorica = np.array(historial['F_target']) / st.session_state.simulador.params['k_descarga']
        else:
            masa_teorica = np.zeros_like(t)
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['M_sag'],
            name='Masa Real', line=dict(color='blue', width=3),
            hovertemplate='%{y:.0f} t<extra>Masa Real</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=masa_teorica,
            name='Masa Teórica', line=dict(color='gray', width=2, dash='dash'),
            hovertemplate='%{y:.0f} t<extra>Masa Teórica</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['W_sag'],
            name='Agua', line=dict(color='cyan', width=2),
            hovertemplate='%{y:.0f} t<extra>Agua</extra>'
        ))
    
    fig.update_layout(
        height=300,
        title="Masas en Molino SAG",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Masa (toneladas)",
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

def crear_grafico_leyes(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_chancado']) * 100,
            name='Ley Chancado', line=dict(color='purple', width=2),
            hovertemplate='%{y:.2f}%<extra>Ley Chancado</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_sag']) * 100,
            name='Ley SAG', line=dict(color='orange', width=2),
            hovertemplate='%{y:.2f}%<extra>Ley SAG</extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_target']) * 100,
            name='Objetivo', line=dict(color='black', width=2, dash='dash'),
            hovertemplate='%{y:.2f}%<extra>Objetivo Ley</extra>'
        ))
    
    fig.update_layout(
        height=300,
        title="Comparación de Leyes",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Ley (%)",
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

def crear_grafico_cobre(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        F_cu_chancado = np.array(historial['F_chancado']) * np.array(historial['L_chancado'])
        F_cu_finos = np.array(historial['F_finos']) * np.array(historial['L_sag'])
        
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
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado + F_cu_finos,
            name='Total', line=dict(color='black', width=1, dash='dot'),
            hovertemplate='%{y:.3f} t/h<extra>Total Cobre</extra>'
        ))
    
    fig.update_layout(
        height=300,
        title="Flujos de Cobre",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo Cobre (t/h)",
        showlegend=True,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# ================= MOSTRAR GRÁFICOS =================
historial = st.session_state.simulador.obtener_historial()

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(crear_grafico_balance(historial), use_container_width=True)
with col2:
    st.plotly_chart(crear_grafico_masas(historial), use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(crear_grafico_leyes(historial), use_container_width=True)
with col4:
    st.plotly_chart(crear_grafico_cobre(historial), use_container_width=True)

# ================= INFORMACIÓN DEL SISTEMA =================
st.markdown("---")

with st.expander("📈 **Información del Sistema**"):
    estado = st.session_state.simulador.obtener_estado()
    params = st.session_state.simulador.params
    
    if historial['F_chancado'] and len(historial['F_chancado']) > 0:
        F_chancado_actual = historial['F_chancado'][-1]
        F_sobre_actual = historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] and len(historial['F_sobre_tamano']) > 0 else 0
        F_alimentacion = F_chancado_actual + F_sobre_actual
        
        M_equilibrio = F_alimentacion / params['k_descarga'] if params['k_descarga'] > 0 else 0
        M_actual = estado['M_sag']
        diferencia = abs(M_actual - M_equilibrio)
        
        # Calcular constantes de tiempo efectivas
        tau_efectivo_flujo = st.session_state.simulador.tau_F
        tau_efectivo_masa = 1.0 / params['k_descarga'] if params['k_descarga'] > 0 else float('inf')
        
        st.markdown(f"""
        ### **Dinámica del Sistema:**
        
        - **τ flujo:** {tau_efectivo_flujo:.1f} horas (63% del objetivo en este tiempo)
        - **τ ley:** {st.session_state.simulador.tau_L:.1f} horas
        - **τ masa SAG:** {tau_efectivo_masa:.1f} horas (1/k)
        
        ### **Comportamiento Esperado:**
        
        1. **Chancado:** Crece como F(t) = F_obj × [1 - exp(-t/τ_F)]
        2. **Ley:** Crece como L(t) = L_obj × [1 - exp(-t/τ_L)] + variaciones
        3. **Masa SAG:** Crece como M(t) = (F_alim/k) × [1 - exp(-k×t)]
        4. **Desacople total:** τ_F solo afecta flujo, τ_L solo afecta ley
        
        ### **Tiempos característicos:**
        
        - **1×τ_F ({tau_efectivo_flujo:.1f}h):** Chancado al 63% del objetivo
        - **3×τ_F ({tau_efectivo_flujo*3:.1f}h):** Chancado al 95% del objetivo
        - **1×τ_masa ({tau_efectivo_masa:.1f}h):** Masa al 63% del equilibrio
        """)

# ================= PIE DE PÁGINA =================
st.markdown("---")

estado = st.session_state.simulador.obtener_estado()
historial = st.session_state.simulador.obtener_historial()

col1, col2, col3, col4 = st.columns(4)

with col1:
    velocidad_display = f"{1/st.session_state.velocidad_sim:.1f}x" if st.session_state.simulando else "0x"
    st.metric("Velocidad simulación", velocidad_display)

with col2:
    st.metric("Tiempo simulado", f"{estado['t']:.1f} h")

with col3:
    if historial['F_finos'] and len(historial['F_finos']) > 0:
        st.metric("Producción finos", f"{historial['F_finos'][-1]:.0f} t/h")
    else:
        st.metric("Producción finos", "0 t/h")

with col4:
    if historial['F_chancado'] and len(historial['F_chancado']) > 0:
        F_chancado_actual = historial['F_chancado'][-1]
        F_sobre_actual = historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] and len(historial['F_sobre_tamano']) > 0 else 0
        F_descarga_actual = historial['F_descarga'][-1] if historial['F_descarga'] and len(historial['F_descarga']) > 0 else 0
        balance = F_chancado_actual + F_sobre_actual - F_descarga_actual
        
        if abs(balance) < 50:
            estado_balance = "⚖️ Estable"
        elif balance > 0:
            estado_balance = "📈 Subiendo"
        else:
            estado_balance = "📉 Bajando"
        
        st.metric("Balance masa", f"{balance:.0f} t/h", estado_balance)
    else:
        st.metric("Balance masa", "0 t/h", "⏳ Inicial")

# Mensaje final
st.markdown("---")

if not st.session_state.simulando:
    st.info("""
    ⏸️ **Simulación en pausa** 
    
    Haz clic en **▶️ INICIAR** para comenzar la simulación.
    Observa el crecimiento exponencial del chancado desde 0 t/h.
    """)
else:
    st.success(f"""
    🔄 **Simulación en curso** 
    
    - Pasos ejecutados: **{st.session_state.pasos_ejecutados}**
    - Tiempo simulado: **{estado['t']:.1f} horas**
    - Velocidad: **{1/st.session_state.velocidad_sim:.1f} pasos/segundo**
    
    **Comportamiento esperado:**
    - Chancado: {estado['F_actual']:.0f} t/h → objetivo: {st.session_state.simulador.objetivos['F_target']:.0f} t/h
    - Ley: {estado['L_actual']*100:.2f}% → objetivo: {st.session_state.simulador.objetivos['L_target']*100:.2f}%
    - Masa equilibrio: ≈ {st.session_state.simulador.objetivos['F_target'] / st.session_state.simulador.params['k_descarga']:.0f} t
    """)

st.caption("""
💡 **Notas:** 
- τ (tau) = constante de tiempo = tiempo para alcanzar 63% del cambio
- Crecimiento exponencial: 1τ = 63%, 2τ = 86%, 3τ = 95%, 4τ = 98%
- τ_F y τ_L son completamente independientes
- La masa SAG tiene su propia constante de tiempo = 1/k
""")

# ================= AUTO-REFRESH =================
if st.session_state.simulando:
    time.sleep(st.session_state.velocidad_sim)
    st.rerun()

