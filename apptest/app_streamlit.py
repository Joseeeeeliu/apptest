"""
SIMULADOR SAG - INTERFAZ STREAMLIT CORREGIDA
Versión estable con auto-avance confiable y visualización en tiempo real
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import time

# Importar la clase corregida
from simulador_sag import SimuladorSAG, crear_parametros_default

# ================= CONFIGURACIÓN DE PÁGINA =================
st.set_page_config(
    page_title="Simulador Planta Concentradora - Molino SAG",
    page_icon="🏭",
    layout="wide"
)

# ================= INICIALIZACIÓN DEL ESTADO =================
if 'simulador' not in st.session_state:
    # Crear parámetros por defecto
    params = crear_parametros_default()
    
    # Crear instancia del simulador
    st.session_state.simulador = SimuladorSAG(params)
    
    # Variables de control de la simulación
    st.session_state.simulando = False
    st.session_state.pasos_ejecutados = 0
    st.session_state.hora_inicio = time.time()
    st.session_state.velocidad_sim = 0.5  # segundos entre pasos

# ================= FUNCIONES DE CONTROL =================
def iniciar_simulacion():
    """Inicia la simulación"""
    st.session_state.simulando = True

def pausar_simulacion():
    """Pausa la simulación"""
    st.session_state.simulando = False

def reiniciar_simulacion():
    """Reinicia completamente la simulación"""
    params = crear_parametros_default()
    st.session_state.simulador = SimuladorSAG(params)
    st.session_state.simulando = False
    st.session_state.pasos_ejecutados = 0
    st.session_state.hora_inicio = time.time()

# ================= EJECUTAR PASO DE SIMULACIÓN =================
# Esta sección ejecuta un paso si la simulación está activa
if st.session_state.simulando:
    st.session_state.simulador.paso_simulacion()
    st.session_state.pasos_ejecutados += 1

# ================= INTERFAZ PRINCIPAL =================
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("**Versión corregida con unidades consistentes y auto-avance estable**")
st.markdown("---")

# ================= BARRA LATERAL =================
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    # Estado de la simulación
    estado_sim = "🟢 EJECUTANDO" if st.session_state.simulando else "⏸️ PAUSADA"
    st.metric("Estado", estado_sim)
    
    # Botones de control
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
        index=2  # "Normal" por defecto
    )
    st.session_state.velocidad_sim = velocidad_opciones[velocidad_seleccionada]
    
    st.markdown("---")
    
    # ========== OBJETIVOS DE OPERACIÓN ==========
    st.subheader("🎯 **Objetivos de Operación**")
    
    # Slider para flujo objetivo
    F_obj = st.slider(
        "**Flujo objetivo (t/h)**",
        500.0, 5000.0, 
        float(st.session_state.simulador.objetivos['F_target']),
        step=100.0,
        key="slider_flujo",
        help="Objetivo de flujo de alimentación al molino SAG"
    )
    
    # Actualizar objetivo de flujo
    st.session_state.simulador.actualizar_objetivo('F', F_obj)
    
    # Slider para ley objetivo
    L_obj = st.slider(
        "**Ley objetivo (%)**",
        0.3, 1.5,
        float(st.session_state.simulador.objetivos['L_target'] * 100),
        step=0.05,
        format="%.2f",
        key="slider_ley",
        help="Objetivo de ley de cobre en la alimentación"
    )
    
    # Actualizar objetivo de ley
    st.session_state.simulador.actualizar_objetivo('L', L_obj / 100.0)
    
    st.markdown("---")
    
    # ========== PARÁMETROS AVANZADOS ==========
    with st.expander("⚙️ **Parámetros Avanzados**"):
        # Control de constante de descarga
        k_valor = st.slider(
            "Constante de descarga (k) [1/hora]",
            0.1, 2.0,
            float(st.session_state.simulador.params['k_descarga']),
            0.1,
            help="k = Descarga / Masa. Valores más altos = menor masa en equilibrio"
        )
        st.session_state.simulador.params['k_descarga'] = k_valor
        
        # Control de recirculación
        recirc = st.slider(
            "Recirculación (%)",
            5.0, 20.0,
            float(st.session_state.simulador.params['fraccion_recirculacion'] * 100),
            1.0,
            format="%.1f"
        )
        st.session_state.simulador.params['fraccion_recirculacion'] = recirc / 100.0
        
        # Control de retardos
        tau_rec = st.slider(
            "Retardo recirculación (min)",
            30, 180,
            int(st.session_state.simulador.params['tau_recirculacion']),
            step=10
        )
        st.session_state.simulador.params['tau_recirculacion'] = tau_rec
        
        tau_finos = st.slider(
            "Retardo finos (min)",
            20, 120,
            int(st.session_state.simulador.params['tau_finos']),
            step=10
        )
        st.session_state.simulador.params['tau_finos'] = tau_finos
    
    st.markdown("---")
    
    # ========== ESTADO ACTUAL ==========
    st.subheader("📊 **Estado Actual**")
    estado_actual = st.session_state.simulador.obtener_estado()
    historial = st.session_state.simulador.obtener_historial()
    
    # Mostrar métricas clave
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tiempo simulado", f"{estado_actual['t']:.1f} h")
        st.metric("Flujo actual", f"{estado_actual['F_actual']:.0f} t/h")
        st.metric("Masa SAG", f"{estado_actual['M_sag']:.0f} t")
    
    with col2:
        st.metric("Ley actual", f"{estado_actual['L_actual']*100:.2f} %")
        st.metric("Humedad SAG", f"{estado_actual['H_sag']*100:.1f} %")
        
        # Verificar si hay datos antes de acceder
        if historial['F_finos'] and len(historial['F_finos']) > 0:
            st.metric("Finos actuales", f"{historial['F_finos'][-1]:.0f} t/h")
        else:
            st.metric("Finos actuales", "0 t/h")
    
    # Indicador de equilibrio (con verificación)
    if historial['F_chancado'] and len(historial['F_chancado']) > 0:
        F_chancado_actual = historial['F_chancado'][-1]
        F_sobre_actual = historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] and len(historial['F_sobre_tamano']) > 0 else 0
        F_descarga_actual = historial['F_descarga'][-1] if historial['F_descarga'] and len(historial['F_descarga']) > 0 else 0
        
        balance = F_chancado_actual + F_sobre_actual - F_descarga_actual
        equilibrio = min(abs(balance) / max(F_chancado_actual, 1), 1.0)
        
        if abs(balance) < 50:
            color = "🟢"
            texto = f"{color} Balance: {balance:.0f} t/h (Estable)"
        elif abs(balance) < 200:
            color = "🟡"
            texto = f"{color} Balance: {balance:.0f} t/h (Moderado)"
        else:
            color = "🔴"
            texto = f"{color} Balance: {balance:.0f} t/h (Inestable)"
        
        st.progress(equilibrio, text=texto)

# ================= FUNCIONES PARA GRÁFICOS =================
def crear_grafico_balance(historial):
    """Crea gráfico de balance de sólidos"""
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        # Agregar trazas para cada flujo
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
    
    # Configurar layout
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
    """Crea gráfico de masas en el molino SAG"""
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        # Calcular masa teórica de equilibrio
        if st.session_state.simulador.params['k_descarga'] > 0:
            masa_teorica = np.array(historial['F_target']) / st.session_state.simulador.params['k_descarga']
        else:
            masa_teorica = np.zeros_like(t)
        
        # Masa real de sólidos
        fig.add_trace(go.Scatter(
            x=t, y=historial['M_sag'],
            name='Masa Real', line=dict(color='blue', width=3),
            hovertemplate='%{y:.0f} t<extra>Masa Real</extra>'
        ))
        
        # Masa teórica de equilibrio
        fig.add_trace(go.Scatter(
            x=t, y=masa_teorica,
            name='Masa Teórica', line=dict(color='gray', width=2, dash='dash'),
            hovertemplate='%{y:.0f} t<extra>Masa Teórica</extra>'
        ))
        
        # Masa de agua
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
    """Crea gráfico de comparación de leyes"""
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        # Ley de chancado (convertir a %)
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_chancado']) * 100,
            name='Ley Chancado', line=dict(color='purple', width=2),
            hovertemplate='%{y:.2f}%<extra>Ley Chancado</extra>'
        ))
        
        # Ley del SAG (convertir a %)
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_sag']) * 100,
            name='Ley SAG', line=dict(color='orange', width=2),
            hovertemplate='%{y:.2f}%<extra>Ley SAG</extra>'
        ))
        
        # Ley objetivo (convertir a %)
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
    """Crea gráfico de flujos de cobre"""
    fig = go.Figure()
    
    t = np.array(historial['t'])
    
    if len(t) > 1:
        # Calcular flujos de cobre
        F_cu_chancado = np.array(historial['F_chancado']) * np.array(historial['L_chancado'])
        F_cu_finos = np.array(historial['F_finos']) * np.array(historial['L_sag'])
        
        # Flujo de cobre en chancado
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado,
            name='Cobre Chancado', line=dict(color='darkblue', width=2),
            hovertemplate='%{y:.3f} t/h<extra>Cobre Chancado</extra>'
        ))
        
        # Flujo de cobre en finos
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_finos,
            name='Cobre Finos', line=dict(color='darkgreen', width=2),
            hovertemplate='%{y:.3f} t/h<extra>Cobre Finos</extra>'
        ))
        
        # Total de cobre
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
# Obtener historial actual
historial = st.session_state.simulador.obtener_historial()

# Crear dos columnas para los primeros gráficos
col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(crear_grafico_balance(historial), use_container_width=True)

with col2:
    st.plotly_chart(crear_grafico_masas(historial), use_container_width=True)

# Crear dos columnas para los siguientes gráficos
col3, col4 = st.columns(2)

with col3:
    st.plotly_chart(crear_grafico_leyes(historial), use_container_width=True)

with col4:
    st.plotly_chart(crear_grafico_cobre(historial), use_container_width=True)

# ================= INFORMACIÓN DEL SISTEMA =================
st.markdown("---")

with st.expander("📈 **Información del Sistema y Comportamiento Esperado**"):
    estado = st.session_state.simulador.obtener_estado()
    params = st.session_state.simulador.params
    
    # Cálculos de equilibrio (con verificación)
    if historial['F_chancado'] and len(historial['F_chancado']) > 0:
        F_chancado_actual = historial['F_chancado'][-1]
        F_sobre_actual = historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] and len(historial['F_sobre_tamano']) > 0 else 0
        F_alimentacion = F_chancado_actual + F_sobre_actual
        
        M_equilibrio = F_alimentacion / params['k_descarga'] if params['k_descarga'] > 0 else 0
        M_actual = estado['M_sag']
        diferencia = abs(M_actual - M_equilibrio)
        
        st.markdown(f"""
        ### **Estado Actual del Sistema:**
        
        - **Tiempo simulado:** {estado['t']:.1f} horas
        - **Pasos ejecutados:** {st.session_state.pasos_ejecutados}
        - **Tiempo real transcurrido:** {time.time() - st.session_state.hora_inicio:.0f} segundos
        - **Velocidad:** {1/st.session_state.velocidad_sim:.1f} pasos/segundo
        
        ### **Balance de Masa:**
        
        - **Alimentación total:** {F_alimentacion:.0f} t/h
        - **Descarga actual:** {historial['F_descarga'][-1] if historial['F_descarga'] and len(historial['F_descarga']) > 0 else 0:.0f} t/h
        - **Masa de equilibrio teórica:** {M_equilibrio:.0f} t ( = F_alimentacion / k)
        - **Masa actual en SAG:** {M_actual:.0f} t
        - **Diferencia:** {diferencia:.0f} t ({diferencia/M_equilibrio*100 if M_equilibrio > 0 else 0:.1f}%)
        
        ### **Comportamiento Esperado:**
        
        1. **Masa estable:** Debería converger a **M = F_alimentacion / k**
        2. **Variabilidad controlada:** Ondas sinusoidales suaves (±1%) después de 2 horas
        3. **Respuesta a cambios:** Los ajustes de objetivos toman ~2-3 horas en reflejarse completamente
        4. **Balance de cobre:** La ley del SAG sigue la ley de alimentación con cierto retardo
        
        ### **Fórmulas Clave:**
        
        - **Ecuación de descarga:** F_descarga = k × M_sag
        - **Ecuación de masa:** dM/dt = F_entrada - F_salida
        - **Masa de equilibrio:** M_equilibrio = F_entrada / k
        - **Retardos:** Recirculación (τ_rec) y Finos (τ_finos) en minutos
        """)
    else:
        st.info("Ejecuta la simulación para ver información del sistema")

# ================= PIE DE PÁGINA =================
st.markdown("---")

# Métricas finales (con verificaciones)
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

# Mensaje de estado final
st.markdown("---")

if not st.session_state.simulando:
    st.info("""
    ⏸️ **Simulación en pausa** 
    
    Haz clic en **▶️ INICIAR** para comenzar la simulación automática.
    La simulación avanzará continuamente según la velocidad seleccionada.
    """)
else:
    # Calcular masa de equilibrio esperada (con verificación)
    masa_equilibrio_texto = ""
    if historial['F_target'] and len(historial['F_target']) > 0 and st.session_state.simulador.params['k_descarga'] > 0:
        masa_equilibrio = historial['F_target'][-1] / st.session_state.simulador.params['k_descarga']
        masa_equilibrio_texto = f"La masa debería estabilizarse en: **M = F_alimentacion / k ≈ {masa_equilibrio:.0f} toneladas**"
    else:
        masa_equilibrio_texto = "La masa debería estabilizarse en: **M = F_alimentacion / k** (ejecuta la simulación para ver valores)"
    
    st.success(f"""
    🔄 **Simulación en curso** 
    
    - Pasos ejecutados: **{st.session_state.pasos_ejecutados}**
    - Tiempo simulado: **{estado['t']:.1f} horas**
    - Velocidad: **{1/st.session_state.velocidad_sim:.1f} pasos/segundo**
    
    {masa_equilibrio_texto}
    """)

# Nota informativa
st.caption("""
💡 **Notas:** 
- Cada paso de simulación representa 1 minuto de operación (dt = 1/60 horas).
- La variabilidad aleatoria se activa después de 2 horas de simulación.
- Los cambios en los objetivos toman tiempo en reflejarse debido a la dinámica del sistema.
- La masa en el molino SAG se estabiliza cuando: F_entrada = F_salida = k × M_sag
""")

# ================= AUTO-REFRESH (CRÍTICO) =================
# ESTA SECCIÓN DEBE ESTAR AL FINAL DEL ARCHIVO
# Se ejecuta siempre que la simulación esté activa
if st.session_state.simulando:
    time.sleep(st.session_state.velocidad_sim)
    st.rerun()
