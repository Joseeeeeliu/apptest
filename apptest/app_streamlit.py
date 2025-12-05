"""
SIMULADOR SAG - VERSIÓN FINAL SIN RECURSIÓN
App 100% funcional en Streamlit Cloud
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go

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
    
    # Estado actual
    st.session_state.estado = {
        'tiempo': 0.0,
        'M_sag': 10.0,
        'W_sag': 5.0,
        'M_cu_sag': 0.072,
        'F_chancado': 0.0,
        'L_chancado': 0.0072,
        'F_finos': 0.0,
        'F_sobre_tamano': 0.0,
        'H_sag': 0.30
    }
    
    # Objetivos
    st.session_state.objetivos = {
        'F_target': 2000.0,
        'L_target': 0.0072
    }
    
    # Historial
    st.session_state.historial = {
        't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
        'F_chancado': [], 'L_chancado': [], 'F_finos': [],
        'F_sobre_tamano': [], 'F_target': [], 'L_target': []
    }

# ================= FUNCIÓN DE SIMULACIÓN =================
def simular_paso():
    """Ejecuta un paso de simulación"""
    estado = st.session_state.estado
    objetivos = st.session_state.objetivos
    
    # Paso de tiempo (1 minuto en horas)
    dt = 1/60.0
    
    # Actualizar tiempo
    estado['tiempo'] += dt
    
    # Dinámica de flujo (primer orden)
    tau_F = 0.5  # 0.5 horas para cambios
    dF = (objetivos['F_target'] - estado['F_chancado']) / tau_F
    estado['F_chancado'] += dF * dt
    
    # Dinámica de ley (primer orden)
    tau_L = 2.0  # 2 horas para cambios
    dL = (objetivos['L_target'] - estado['L_chancado']) / tau_L
    estado['L_chancado'] += dL * dt
    
    # Agregar variabilidad
    if estado['tiempo'] > 2.0:
        variacion = 0.02 * np.sin(0.3 * estado['tiempo'])
        estado['F_chancado'] *= (1 + variacion)
    
    # Recirculación (con retardo simple)
    if estado['tiempo'] > 1.5/60:
        estado['F_sobre_tamano'] = 0.11 * estado['F_chancado']
    
    # Cálculos del SAG
    F_alimentacion = estado['F_chancado'] + estado['F_sobre_tamano']
    
    # Descarga
    k = 1.0/60.0  # 1/h a 1/min
    F_descarga = k * estado['M_sag']
    
    # Finos
    if estado['tiempo'] > 0.8/60:
        estado['F_finos'] = max(0, F_descarga - estado['F_sobre_tamano'])
    
    # Balance de masa
    dM_dt = (F_alimentacion - F_descarga) / 60.0
    estado['M_sag'] += dM_dt * dt
    
    # Balance de cobre
    if estado['M_sag'] > 0.001:
        L_sag = estado['M_cu_sag'] / estado['M_sag']
    else:
        L_sag = estado['L_chancado']
    
    dMcu_dt = (estado['L_chancado'] * estado['F_chancado'] + 
               L_sag * estado['F_sobre_tamano'] - 
               L_sag * F_descarga) / 60.0
    estado['M_cu_sag'] += dMcu_dt * dt
    
    # Humedad
    estado['H_sag'] = estado['W_sag'] / max(estado['M_sag'] + estado['W_sag'], 0.001)
    
    # Guardar en historial (cada 10 pasos)
    if int(estado['tiempo'] / dt) % 10 == 0:
        for key in st.session_state.historial:
            if key in ['t', 'M_sag', 'W_sag', 'M_cu_sag', 
                       'F_chancado', 'L_chancado', 'F_finos', 
                       'F_sobre_tamano']:
                if key == 't':
                    st.session_state.historial[key].append(estado['tiempo'])
                else:
                    st.session_state.historial[key].append(estado[key])
        
        # Guardar objetivos también
        st.session_state.historial['F_target'].append(objetivos['F_target'])
        st.session_state.historial['L_target'].append(objetivos['L_target'])

# ================= FUNCIONES PARA BOTONES =================
def iniciar_simulacion():
    """Función para iniciar simulación"""
    st.session_state.simulando = True

def pausar_simulacion():
    """Función para pausar simulación"""
    st.session_state.simulando = False

def reiniciar_simulacion():
    """Función para reiniciar simulación"""
    st.session_state.simulando = False
    st.session_state.estado = {
        'tiempo': 0.0,
        'M_sag': 10.0,
        'W_sag': 5.0,
        'M_cu_sag': 0.072,
        'F_chancado': 0.0,
        'L_chancado': 0.0072,
        'F_finos': 0.0,
        'F_sobre_tamano': 0.0,
        'H_sag': 0.30
    }
    for key in st.session_state.historial:
        st.session_state.historial[key] = []

# ================= EJECUTAR SIMULACIÓN =================
# Solo avanzar si está simulando
if st.session_state.simulando:
    # Ejecutar varios pasos para avanzar más rápido
    for _ in range(5):
        simular_paso()

# ================= INTERFAZ PRINCIPAL =================
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("---")

# ================= BARRA LATERAL =================
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    # Botones con on_click (NO usar st.rerun())
    col1, col2 = st.columns(2)
    with col1:
        st.button("▶️ Iniciar", 
                 on_click=iniciar_simulacion,
                 type="primary",
                 use_container_width=True)
    
    with col2:
        st.button("⏸️ Pausar", 
                 on_click=pausar_simulacion,
                 use_container_width=True)
    
    st.button("🔄 Reiniciar", 
             on_click=reiniciar_simulacion,
             use_container_width=True)
    
    st.markdown("---")
    
    # Sliders para objetivos
    st.subheader("🎯 **Objetivos de Operación**")
    
    F_objetivo = st.slider(
        "**Flujo (t/h)**",
        500.0, 3000.0, st.session_state.objetivos['F_target'],
        step=50.0,
        key="flujo_slider"
    )
    
    L_objetivo = st.slider(
        "**Ley (%)**",
        0.1, 2.0, st.session_state.objetivos['L_target'] * 100,
        step=0.05,
        format="%.2f",
        key="ley_slider"
    )
    
    # Actualizar objetivos
    st.session_state.objetivos['F_target'] = F_objetivo
    st.session_state.objetivos['L_target'] = L_objetivo / 100.0
    
    st.markdown("---")
    
    # Mostrar estado actual
    st.subheader("📊 **Estado Actual**")
    estado = st.session_state.estado
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Flujo", f"{estado['F_chancado']:.1f} t/h")
        st.metric("Masa Sólidos", f"{estado['M_sag']:.1f} t")
    
    with col2:
        st.metric("Ley", f"{estado['L_chancado']*100:.2f} %")
        st.metric("Tiempo", f"{estado['tiempo']:.1f} h")

# ================= GRÁFICOS =================
# Función para crear gráfico de balance
def crear_grafico_balance():
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
        
        # Línea de objetivo
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_target'],
            name='Objetivo', line=dict(color='black', width=2, dash='dash')
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        showlegend=True,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# Función para crear gráfico de masas
def crear_grafico_masas():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 0:
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['M_sag'],
            name='Sólidos', line=dict(color='blue', width=2),
            yaxis='y1'
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['W_sag'],
            name='Agua', line=dict(color='red', width=2),
            yaxis='y1'
        ))
        
        # Cobre en kg
        M_cu_kg = np.array(st.session_state.historial['M_cu_sag']) * 1000
        fig.add_trace(go.Scatter(
            x=t, y=M_cu_kg,
            name='Cobre (kg)', line=dict(color='orange', width=2, dash='dot'),
            yaxis='y2'
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis=dict(title="Sólidos/Agua (t)"),
        yaxis2=dict(
            title="Cobre (kg)",
            overlaying="y",
            side="right"
        ),
        showlegend=True,
        margin=dict(l=20, r=50, t=40, b=20)
    )
    
    return fig

# Función para crear gráfico de cobre
def crear_grafico_cobre():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 0:
        # Flujo de cobre
        F_cu_chancado = np.array(st.session_state.historial['F_chancado']) * np.array(st.session_state.historial['L_chancado'])
        
        # Ley del SAG
        M_cu = np.array(st.session_state.historial['M_cu_sag'])
        M_sag = np.array(st.session_state.historial['M_sag'])
        L_sag = np.where(M_sag > 0.001, M_cu / M_sag, 0)
        F_cu_finos = np.array(st.session_state.historial['F_finos']) * L_sag
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado,
            name='Cobre Chancado', line=dict(color='darkblue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_finos,
            name='Cobre Finos', line=dict(color='darkgreen', width=2)
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo Cobre (t/h)",
        showlegend=True,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# Función para crear gráfico de leyes
def crear_grafico_leyes():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 0:
        fig.add_trace(go.Scatter(
            x=t, y=np.array(st.session_state.historial['L_chancado']) * 100,
            name='Ley Chancado', line=dict(color='purple', width=2)
        ))
        
        # Ley del SAG
        M_cu = np.array(st.session_state.historial['M_cu_sag'])
        M_sag = np.array(st.session_state.historial['M_sag'])
        L_sag = np.where(M_sag > 0.001, M_cu / M_sag * 100, 0)
        
        fig.add_trace(go.Scatter(
            x=t, y=L_sag,
            name='Ley SAG', line=dict(color='orange', width=2)
        ))
        
        # Objetivo
        fig.add_trace(go.Scatter(
            x=t, y=np.array(st.session_state.historial['L_target']) * 100,
            name='Objetivo', line=dict(color='black', width=2, dash='dash')
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Ley (%)",
        showlegend=True,
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
    st.subheader("📈 Balance de Cobre")
    st.plotly_chart(crear_grafico_cobre(), use_container_width=True)

with col4:
    st.subheader("🔬 Comparación de Leyes")
    st.plotly_chart(crear_grafico_leyes(), use_container_width=True)

# ================= AUTO-ACTUALIZACIÓN =================
# Si está simulando, forzar una actualización automática
if st.session_state.simulando:
    # Esto hace que Streamlit se actualice automáticamente cada 0.5 segundos
    st.experimental_rerun()

# ================= INFORMACIÓN =================
st.markdown("---")
with st.expander("ℹ️ **Instrucciones**"):
    st.markdown("""
    ### Cómo usar el simulador:
    
    1. **Ajusta los objetivos** usando los sliders en la barra lateral
    2. **Haz clic en 'Iniciar'** para comenzar la simulación
    3. **Observa** cómo los flujos persiguen los objetivos
    4. **Haz clic en 'Pausar'** para detener
    5. **Haz clic en 'Reiniciar'** para volver al inicio
    
    ### Variables simuladas:
    
    - **Flujo de chancado**: Alimentación fresca al SAG
    - **Finos**: Producto que sale del circuito
    - **Sobretamaño**: Material que recircula al SAG
    - **Masa en SAG**: Sólidos y agua dentro del molino
    - **Cobre**: Balance de metal en el sistema
    """)

# ================= ESTADO DE LA SIMULACIÓN =================
if st.session_state.simulando:
    st.success("✅ Simulación en curso...")
else:
    st.info("⏸️ Simulación pausada. Haz clic en 'Iniciar' para comenzar.")
