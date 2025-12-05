"""
APLICACIÓN STREAMLIT PARA SIMULACIÓN SAG
Interfaz web interactiva en tiempo real
"""

# 1. IMPORTAR BIBLIOTECAS NECESARIAS
import streamlit as st
import numpy as np
#import matplotlib.pyplot as plt
import time
from threading import Thread
import plotly.graph_objects as go  # Plotly para gráficos interactivos

# Importar nuestro simulador
from simulador_sag import SimuladorSAG, crear_parametros_default

# 2. CONFIGURAR PÁGINA DE STREAMLIT
st.set_page_config(
    page_title="Simulador Planta Concentradora",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 3. INICIALIZAR SIMULADOR (con caching para no reiniciar)
@st.cache_resource
def crear_simulador():
    """Crea y retorna el simulador (cacheado por Streamlit)"""
    params = crear_parametros_default()
    return SimuladorSAG(params)

# 4. TÍTULO PRINCIPAL
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("---")

# 5. BARRA LATERAL CON CONTROLES
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    # Estado de la simulación
    if 'simulador' not in st.session_state:
        st.session_state.simulador = crear_simulador()
        st.session_state.simulando = False
        st.session_state.hilo = None
    
    # Botones de control
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Iniciar", type="primary", use_container_width=True):
            st.session_state.simulando = True
    with col2:
        if st.button("⏸️ Pausar", use_container_width=True):
            st.session_state.simulando = False
    
    if st.button("🔄 Reiniciar", use_container_width=True):
        st.session_state.simulador.reset()
        st.session_state.simulando = False
        st.rerun()
    
    st.markdown("---")
    
    # CONTROLES DESLIZANTES
    st.subheader("📊 **Parámetros de Operación**")
    
    # Flujo objetivo
    F_objetivo = st.slider(
        "**Flujo Objetivo (t/h)**",
        min_value=500.0,
        max_value=3000.0,
        value=float(st.session_state.simulador.objetivos['F_target']),
        step=50.0,
        help="Flujo de alimentación objetivo que la planta intentará alcanzar"
    )
    
    # Ley objetivo
    L_objetivo = st.slider(
        "**Ley Objetivo (%)**",
        min_value=0.1,
        max_value=2.0,
        value=float(st.session_state.simulador.objetivos['L_target'] * 100),
        step=0.05,
        format="%.2f",
        help="Ley de cobre objetivo en la alimentación"
    )
    
    # Actualizar objetivos en el simulador
    st.session_state.simulador.actualizar_objetivo('F', F_objetivo)
    st.session_state.simulador.actualizar_objetivo('L', L_objetivo / 100.0)
    
    st.markdown("---")
    
    # PARÁMETROS AVANZADOS (acordeón)
    with st.expander("⚙️ **Parámetros Avanzados**"):
        # Humedad SAG
        humedad_sag = st.slider(
            "Humedad SAG (%)",
            min_value=20,
            max_value=40,
            value=int(st.session_state.simulador.params['humedad_sag'] * 100),
            step=1
        )
        st.session_state.simulador.params['humedad_sag'] = humedad_sag / 100.0
        
        # Fracción recirculación
        fraccion_rec = st.slider(
            "Fracción Recirculación (%)",
            min_value=5,
            max_value=20,
            value=int(st.session_state.simulador.params['fraccion_recirculacion'] * 100),
            step=1
        )
        st.session_state.simulador.params['fraccion_recirculacion'] = fraccion_rec / 100.0
    
    st.markdown("---")
    
    # INFORMACIÓN DEL SISTEMA
    st.subheader("📈 **Estado Actual**")
    
    if st.session_state.simulando:
        estado = st.session_state.estado_actual
        if estado:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Flujo Actual", f"{estado.get('F_chancado', 0):.1f} t/h")
                st.metric("Masa Sólidos", f"{estado.get('M_sag', 0):.1f} ton")
            with col2:
                st.metric("Ley Actual", f"{estado.get('L_chancado', 0)*100:.2f} %")
                st.metric("Tiempo", f"{estado.get('tiempo', 0):.1f} h")
    
    # VELOCIDAD DE SIMULACIÓN
    st.markdown("---")
    velocidad = st.slider(
        "**Velocidad Simulación**",
        min_value=1,
        max_value=10,
        value=5,
        help="1 = tiempo real, 10 = 10x más rápido"
    )

# 6. ÁREA PRINCIPAL CON GRÁFICOS
def actualizar_simulacion():
    """Función que ejecuta pasos de simulación cuando está activa"""
    while st.session_state.simulando:
        # Ejecutar paso de simulación
        estado = st.session_state.simulador.paso_simulacion()
        st.session_state.estado_actual = estado
        
        # Controlar velocidad
        time.sleep(0.1 / velocidad)

# 7. CONTENEDORES PARA GRÁFICOS
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Balance de Sólidos")
    grafico1 = st.empty()  # Contenedor vacío que actualizaremos
    
with col2:
    st.subheader("⚖️ Masas en Molino SAG")
    grafico2 = st.empty()

col3, col4 = st.columns(2)

with col3:
    st.subheader("📈 Balance de Cobre")
    grafico3 = st.empty()
    
with col4:
    st.subheader("🔬 Comparación de Leyes")
    grafico4 = st.empty()

# 8. FUNCIONES PARA CREAR GRÁFICOS
def crear_grafico_balance_solidos(historial):
    """Crea gráfico de balance de sólidos con Plotly"""
    fig = go.Figure()
    
    # Convertir tiempo a horas
    t_horas = np.array(historial['t'])
    
    # Agregar trazas
    fig.add_trace(go.Scatter(
        x=t_horas, y=historial['F_chancado'],
        name='Chancado', line=dict(color='blue', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=historial['F_finos'],
        name='Finos SAG', line=dict(color='green', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=historial['F_sobre_tamano'],
        name='Sobretamaño', line=dict(color='red', width=2)
    ))
    
    # Línea de objetivo
    if historial['F_target']:
        fig.add_trace(go.Scatter(
            x=t_horas, y=historial['F_target'],
            name='Objetivo', line=dict(color='black', width=2, dash='dash')
        ))
    
    # Configurar layout
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        hovermode='x unified',
        showlegend=True,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    
    return fig

def crear_grafico_masas_sag(historial):
    """Crea gráfico de masas en el SAG"""
    fig = go.Figure()
    
    t_horas = np.array(historial['t'])
    
    # Masas principales (eje izquierdo)
    fig.add_trace(go.Scatter(
        x=t_horas, y=historial['M_sag'],
        name='Sólidos SAG', line=dict(color='blue', width=2),
        yaxis='y1'
    ))
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=historial['W_sag'],
        name='Agua SAG', line=dict(color='red', width=2),
        yaxis='y1'
    ))
    
    # Cobre (eje derecho, escala diferente)
    fig.add_trace(go.Scatter(
        x=t_horas, y=np.array(historial['M_cu_sag']) * 1000,  # Convertir a kg
        name='Cobre SAG (kg)', line=dict(color='orange', width=2, dash='dot'),
        yaxis='y2'
    ))
    
    # Configurar ejes duales
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis=dict(
            title="Masa Sólidos/Agua (ton)",
            titlefont=dict(color="black"),
            tickfont=dict(color="black")
        ),
        yaxis2=dict(
            title="Masa Cobre (kg)",
            titlefont=dict(color="orange"),
            tickfont=dict(color="orange"),
            overlaying="y",
            side="right"
        ),
        hovermode='x unified',
        showlegend=True,
        margin=dict(l=20, r=50, t=30, b=20)
    )
    
    return fig

# 9. BUCLE PRINCIPAL DE ACTUALIZACIÓN
if 'simulando' not in st.session_state:
    st.session_state.simulando = False

# Iniciar hilo de simulación si no está corriendo
if st.session_state.simulando and 'hilo' not in st.session_state:
    st.session_state.hilo = Thread(target=actualizar_simulacion, daemon=True)
    st.session_state.hilo.start()
elif not st.session_state.simulando and 'hilo' in st.session_state:
    st.session_state.hilo = None

# 10. ACTUALIZAR GRÁFICOS PERIÓDICAMENTE
placeholder = st.empty()

while True:
    with placeholder.container():
        # Obtener historial actual
        historial = st.session_state.simulador.obtener_historial()
        
        # Actualizar gráficos solo si hay datos
        if historial['t']:
            # Gráfico 1: Balance de sólidos
            fig1 = crear_grafico_balance_solidos(historial)
            grafico1.plotly_chart(fig1, use_container_width=True)
            
            # Gráfico 2: Masas en SAG
            fig2 = crear_grafico_masas_sag(historial)
            grafico2.plotly_chart(fig2, use_container_width=True)
            
            # Gráfico 3: Balance de cobre
            fig3 = crear_grafico_balance_cobre(historial)
            grafico3.plotly_chart(fig3, use_container_width=True)
            
            # Gráfico 4: Leyes comparadas
            fig4 = crear_grafico_leyes(historial)
            grafico4.plotly_chart(fig4, use_container_width=True)
    
    # Pequeña pausa para no sobrecargar
    time.sleep(0.5)
    
    # Romper si la simulación se detuvo
    if not st.session_state.simulando:
        break

# 11. FUNCIONES ADICIONALES PARA GRÁFICOS (completar)
def crear_grafico_balance_cobre(historial):
    """Crea gráfico de balance de cobre"""
    fig = go.Figure()
    
    t_horas = np.array(historial['t'])
    
    # Calcular flujos de cobre
    F_cu_chancado = np.array(historial['F_chancado']) * np.array(historial['L_chancado'])
    F_cu_finos = np.array(historial['F_finos']) * calcular_ley_sag(historial)
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=F_cu_chancado,
        name='Cobre Chancado', line=dict(color='darkblue', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=F_cu_finos,
        name='Cobre Finos', line=dict(color='darkgreen', width=2)
    ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo Cobre (t/h)",
        hovermode='x unified'
    )
    
    return fig

def crear_grafico_leyes(historial):
    """Crea gráfico comparativo de leyes"""
    fig = go.Figure()
    
    t_horas = np.array(historial['t'])
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=np.array(historial['L_chancado']) * 100,
        name='Ley Chancado', line=dict(color='purple', width=2)
    ))
    
    # Calcular ley del SAG
    ley_sag = calcular_ley_sag(historial) * 100
    
    fig.add_trace(go.Scatter(
        x=t_horas, y=ley_sag,
        name='Ley SAG', line=dict(color='orange', width=2)
    ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Ley (%)",
        hovermode='x unified'
    )
    
    return fig

def calcular_ley_sag(historial):
    """Calcula ley del SAG a partir del historial"""
    M_cu = np.array(historial['M_cu_sag'])
    M_total = np.array(historial['M_sag'])
    
    # Evitar división por cero
    with np.errstate(divide='ignore', invalid='ignore'):
        ley = np.where(M_total > 0.001, M_cu / M_total, 0)
    
    return ley

# 12. INFORMACIÓN ADICIONAL
st.markdown("---")
with st.expander("📚 **Información Técnica**"):
    st.markdown("""
    ### **Cómo funciona la simulación:**
    
    1. **Dinámica de primer orden**: Los flujos no cambian instantáneamente, 
       sino que "persiguen" los valores objetivo con una constante de tiempo.
    
    2. **Retardos realistas**: La recirculación y producción de finos tienen 
       retardos que simulan el tiempo de transporte y procesamiento.
    
    3. **Variabilidad**: Se incluyen variaciones sinusoidales y aleatorias 
       para simular condiciones reales de operación.
    
    4. **Balance de masa**: Se conserva masa total, agua y cobre en todo momento.
    
    ### **Parámetros clave:**
    - **Flujo objetivo**: Valor que el operador desea alcanzar
    - **Ley objetivo**: Concentración de cobre deseada
    - **Humedad SAG**: Porcentaje de agua en la pulpa del molino
    - **Recirculación**: Fracción de material que retorna al SAG

    """)

