"""
SIMULADOR SAG - VERSIÓN CORREGIDA Y CON AUTO-AVANCE FIABLE
Usa la clase SimuladorSAG corregida + actualización automática garantizada
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import time
import random

# ================= INCLUIR LA CLASE SIMULADOR SAG CORREGIDA =================

class SimuladorSAG:
    def __init__(self, params):
        self.params = params.copy()
        
        # Estado inicial
        self.estado = {
            't': 0.0,
            'M_sag': 100.0,
            'W_sag': 42.86,
            'M_cu_sag': 0.72,
            'F_actual': 0.0,
            'L_actual': params['L_nominal'],
            'H_sag': params['humedad_sag']
        }
        
        # Objetivos
        self.objetivos = {
            'F_target': params['F_nominal'],
            'L_target': params['L_nominal']
        }
        
        # Buffers para retardos (más eficiente)
        self.buffer_F = []
        self.buffer_t = []
        
        # Historial para gráficos
        self.historial = {
            't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
            'F_chancado': [], 'L_chancado': [], 'F_finos': [],
            'F_sobre_tamano': [], 'F_target': [], 'L_target': [],
            'F_descarga': [], 'L_sag': [], 'H_sag': []
        }
        
        # Control
        self.dt = 1/60.0  # 1 minuto en horas
        self.semilla_aleatoria = random.randint(1, 10000)
        
    def calcular_alimentacion(self):
        """Versión simplificada pero con variabilidad realista"""
        t = self.estado['t']
        objetivos = self.objetivos
        
        # 1. DINÁMICA DE PRIMER ORDEN hacia el objetivo
        tau_F = 0.5  # 0.5 horas para cambios
        error_F = objetivos['F_target'] - self.estado['F_actual']
        dF_dt = error_F / tau_F
        F_nuevo = self.estado['F_actual'] + dF_dt * self.dt
        
        # 2. VARIABILIDAD (como en el original)
        np.random.seed(self.semilla_aleatoria + int(t * 1000))
        
        if t > 2.0:
            # Componentes de variabilidad
            lenta = 0.02 * np.sin(0.3 * t) + 0.01 * np.sin(0.7 * t + 1)
            media = 0.01 * np.sin(2.0 * t + 2)
            rapida = 0.005 * np.random.normal(0, 1)
            
            perturbacion = 0
            if np.random.random() < 0.002:
                perturbacion += np.random.uniform(-0.04, -0.02)
            
            random_factor = 1 + lenta + media + rapida + perturbacion
        else:
            random_factor = 1
        
        # 3. ARRANQUE GRADUAL
        if t > 0:
            factor_arranque = 1 - np.exp(-t / 0.5)
        else:
            factor_arranque = 0
        
        F_nuevo = F_nuevo * factor_arranque * random_factor
        
        # 4. LEY
        if t > 0:
            ley_variacion = 0.02 * np.sin(0.5 * t + 3) + 0.01 * np.random.normal(0, 0.5)
            L_nuevo = self.params['L_nominal'] * (1 + 0.08 * ley_variacion)
            L_nuevo = np.clip(L_nuevo, 0.7 * self.params['L_nominal'], 1.3 * self.params['L_nominal'])
        else:
            L_nuevo = self.params['L_nominal']
        
        # Perseguir objetivo
        tau_L = 2.0
        error_L = objetivos['L_target'] - L_nuevo
        dL_dt = error_L / tau_L
        L_nuevo += dL_dt * self.dt
        
        # Limitar valores
        F_nuevo = np.clip(F_nuevo, 0.1 * objetivos['F_target'], 1.5 * objetivos['F_target'])
        
        return F_nuevo, L_nuevo, (random_factor - 1) * 100
    
# ================= REEMPLAZA ESTA FUNCIÓN =================
# Busca la función simular_paso() que tenías (líneas ~80-200)
# Y reemplázala por:

def simular_paso():
    """VERSIÓN SIMPLIFICADA PARA DEBUGGING - reemplaza la anterior"""
    estado = st.session_state.estado
    params = st.session_state.params
    objetivos = st.session_state.objetivos
    
    dt = 1/60.0  # 1 minuto en horas
    
    # 1. FLUJO CON DINÁMICA SIMPLE (sin aleatoriedad inicial)
    tau = 2.0  # 2 horas de constante de tiempo
    error_F = objetivos['F_target'] - estado['F_chancado']
    
    # Limitar cambio máximo al inicio
    if estado['tiempo'] < 1.0:  # Primera hora
        max_cambio = objetivos['F_target'] * 0.05 * dt  # 5% por minuto
        cambio_F = np.clip(error_F / tau * dt, -max_cambio, max_cambio)
    else:
        cambio_F = (error_F / tau) * dt
    
    estado['F_chancado'] += cambio_F
    
    # 2. RECIRCULACIÓN SIMPLIFICADA (sin retardo por ahora)
    estado['F_sobre_tamano'] = params['fraccion_recirculacion'] * estado['F_chancado']
    
    # 3. CÁLCULOS BÁSICOS
    F_alimentacion_total = estado['F_chancado'] + estado['F_sobre_tamano']
    F_descarga = params['k_descarga'] * estado['M_sag']
    estado['F_finos'] = max(F_descarga - estado['F_sobre_tamano'], 0)
    
    # 4. BALANCE DE MASA (ESTABLE - CON LÍMITES)
    dM_dt = F_alimentacion_total - F_descarga
    
    # Limitar cambio máximo por paso (5% de la masa actual o 10 toneladas)
    cambio_max = max(0.05 * estado['M_sag'], 10.0)
    cambio_M = np.clip(dM_dt * dt, -cambio_max, cambio_max)
    
    estado['M_sag'] += cambio_M
    estado['M_sag'] = max(estado['M_sag'], 10.0)  # Mínimo físico
    
    # 5. BALANCE DE COBRE SIMPLIFICADO
    # Asumir ley constante por ahora
    estado['L_chancado'] = objetivos['L_target']
    
    # Actualizar masa de cobre en SAG (simplificado)
    if estado['M_sag'] > 0.1:
        estado['M_cu_sag'] = estado['M_sag'] * estado['L_chancado']
    else:
        estado['M_cu_sag'] = 0.001
    
    # 6. BALANCE DE AGUA SIMPLIFICADO
    # Humedad deseada: 30%
    agua_necesaria = estado['M_sag'] * (params['humedad_sag'] / (1 - params['humedad_sag']))
    estado['W_sag'] = agua_necesaria
    
    # 7. ACTUALIZAR TIEMPO
    estado['tiempo'] += dt
    
    # 8. GUARDAR HISTORIAL (cada paso para debugging)
    # Limitar tamaño para no saturar memoria
    max_historial = 24 * 60  # 24 horas * 60 puntos/hora
    
    for key in ['t', 'M_sag', 'W_sag', 'M_cu_sag', 
                'F_chancado', 'L_chancado', 'F_finos', 'F_sobre_tamano']:
        if key == 't':
            valor = estado['tiempo']
        else:
            valor = estado[key]
        
        st.session_state.historial[key].append(valor)
        
        if len(st.session_state.historial[key]) > max_historial:
            st.session_state.historial[key] = st.session_state.historial[key][-max_historial:]
    
    # Guardar objetivos
    st.session_state.historial['F_target'].append(objetivos['F_target'])
    st.session_state.historial['L_target'].append(objetivos['L_target'])
    
    if len(st.session_state.historial['F_target']) > max_historial:
        st.session_state.historial['F_target'] = st.session_state.historial['F_target'][-max_historial:]
        st.session_state.historial['L_target'] = st.session_state.historial['L_target'][-max_historial:]
    
    # 9. DEBUG: Imprimir valores para diagnóstico
    print(f"Tiempo: {estado['tiempo']:.2f}h | "
          f"Masa: {estado['M_sag']:.0f}t | "
          f"F_chancado: {estado['F_chancado']:.0f}t/h | "
          f"F_descarga: {F_descarga:.0f}t/h | "
          f"dM/dt: {dM_dt:.1f}t/h")
    
    def actualizar_objetivo(self, tipo, valor):
        if tipo == 'F':
            self.objetivos['F_target'] = valor
        elif tipo == 'L':
            self.objetivos['L_target'] = valor
    
    def reset(self):
        """Reiniciar manteniendo parámetros"""
        params = self.params.copy()
        self.__init__(params)
    
    def obtener_estado(self):
        return self.estado.copy()
    
    def obtener_historial(self):
        return {k: v.copy() for k, v in self.historial.items()}

# ================= CONFIGURACIÓN STREAMLIT =================

st.set_page_config(
    page_title="Simulador Planta SAG - Versión Corregida",
    page_icon="🏭",
    layout="wide"
)

# ================= INICIALIZACIÓN =================

if 'simulador' not in st.session_state:
    params = {
        'F_nominal': 45000/(24*0.94),  # ~2000 t/h
        'L_nominal': 0.0072,
        'fraccion_recirculacion': 0.11,
        'humedad_alimentacion': 0.035,
        'humedad_sag': 0.30,
        'humedad_recirculacion': 0.08,
        'k_descarga': 0.5,
        'tau_recirculacion': 90,  # minutos
        'tau_finos': 48           # minutos
    }
    
    st.session_state.simulador = SimuladorSAG(params)
    st.session_state.simulando = False
    st.session_state.ultimo_update = time.time()
    st.session_state.pasos_ejecutados = 0

# ================= FUNCIONES DE CONTROL =================

def iniciar_simulacion():
    st.session_state.simulando = True
    st.session_state.ultimo_update = time.time()

def pausar_simulacion():
    st.session_state.simulando = False

def reiniciar_simulacion():
    st.session_state.simulador.reset()
    st.session_state.simulando = False
    st.session_state.pasos_ejecutados = 0

# ================= REEMPLAZA LA LÓGICA DE AUTO-AVANCE =================
# Busca esta sección y reemplázala:

# EJECUTAR SIMULACIÓN SI ESTÁ ACTIVA
if st.session_state.simulando:
    tiempo_actual = time.time()
    
    # Queremos 1 paso por segundo real
    if st.session_state.ultima_actualizacion == 0:
        st.session_state.ultima_actualizacion = tiempo_actual
    
    # Si ha pasado más de 1 segundo desde la última actualización
    if tiempo_actual - st.session_state.ultima_actualizacion >= 1.0:
        # Ejecutar exactamente 1 paso
        simular_paso()
        st.session_state.ultima_actualizacion = tiempo_actual
        
        # Forzar actualización de la interfaz
        st.rerun()

# ================= INTERFAZ =================

st.title("🏭 Simulador Planta SAG - Versión Corregida")
st.markdown("**Unidades consistentes + Auto-avance garantizado + Variabilidad realista**")

# Barra lateral
with st.sidebar:
    st.header("🎛️ Controles de Operación")
    
    simulador = st.session_state.simulador
    
    # Estado
    estado = "🟢 EJECUTANDO" if st.session_state.simulando else "⏸️ PAUSADA"
    st.metric("Estado", estado)
    
    # Botones
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Iniciar", use_container_width=True, disabled=st.session_state.simulando):
            iniciar_simulacion()
    with col2:
        if st.button("⏸️ Pausar", use_container_width=True, disabled=not st.session_state.simulando):
            pausar_simulacion()
    
    if st.button("🔄 Reiniciar", use_container_width=True):
        reiniciar_simulacion()
    
    st.markdown("---")
    
    # Objetivos
    st.subheader("🎯 Objetivos")
    
    F_obj = st.slider(
        "Flujo objetivo (t/h)",
        1000.0, 3000.0, float(simulador.objetivos['F_target']),
        step=50.0
    )
    simulador.actualizar_objetivo('F', F_obj)
    
    L_obj = st.slider(
        "Ley objetivo (%)",
        0.5, 1.0, float(simulador.objetivos['L_target'] * 100),
        step=0.05,
        format="%.2f"
    )
    simulador.actualizar_objetivo('L', L_obj / 100.0)
    
    st.markdown("---")
    
    # Parámetros
    with st.expander("⚙️ Parámetros"):
        k_valor = st.slider(
            "k descarga (1/h)",
            0.1, 2.0, float(simulador.params['k_descarga']),
            step=0.1
        )
        simulador.params['k_descarga'] = k_valor
        
        recirc = st.slider(
            "Recirculación (%)",
            5.0, 20.0, float(simulador.params['fraccion_recirculacion'] * 100),
            step=1.0
        )
        simulador.params['fraccion_recirculacion'] = recirc / 100.0
        
        tau_rec = st.slider(
            "τ recirculación (min)",
            30, 180, int(simulador.params['tau_recirculacion']),
            step=10
        )
        simulador.params['tau_recirculacion'] = tau_rec
        
        tau_finos = st.slider(
            "τ finos (min)",
            20, 120, int(simulador.params['tau_finos']),
            step=10
        )
        simulador.params['tau_finos'] = tau_finos
    
    st.markdown("---")
    
    # Estado actual
    st.subheader("📊 Estado Actual")
    estado_actual = simulador.obtener_estado()
    historial = simulador.obtener_historial()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tiempo", f"{estado_actual['t']:.1f} h")
        st.metric("Flujo", f"{estado_actual['F_actual']:.0f} t/h")
        st.metric("Masa SAG", f"{estado_actual['M_sag']:.0f} t")
    
    with col2:
        st.metric("Ley", f"{estado_actual['L_actual']*100:.2f} %")
        st.metric("Humedad", f"{estado_actual['H_sag']*100:.1f} %")
        st.metric("Cobre SAG", f"{estado_actual['M_cu_sag']:.3f} t")
    
    # Últimos valores del historial
    if historial['F_finos']:
        st.metric("Finos", f"{historial['F_finos'][-1]:.0f} t/h")
    if historial['F_sobre_tamano']:
        st.metric("Recirculación", f"{historial['F_sobre_tamano'][-1]:.0f} t/h")

# ================= GRÁFICOS =================

def crear_grafico_balance(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    if len(t) > 1:
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_chancado'],
            name='Chancado', line=dict(color='blue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_finos'],
            name='Finos', line=dict(color='green', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_sobre_tamano'],
            name='Sobretamaño', line=dict(color='red', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['F_target'],
            name='Objetivo', line=dict(color='black', width=2, dash='dash')
        ))
    
    fig.update_layout(
        height=300,
        title="Balance de Sólidos",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        showlegend=True,
        hovermode='x unified'
    )
    return fig

def crear_grafico_masas(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    if len(t) > 1:
        fig.add_trace(go.Scatter(
            x=t, y=historial['M_sag'],
            name='Masa Sólidos', line=dict(color='blue', width=3)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=historial['W_sag'],
            name='Masa Agua', line=dict(color='cyan', width=2)
        ))
        
        # Cobre en escala secundaria
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['M_cu_sag']) * 1000,
            name='Cobre (kg)', line=dict(color='orange', width=2),
            yaxis='y2'
        ))
    
    fig.update_layout(
        height=300,
        title="Masas en Molino SAG",
        xaxis_title="Tiempo (horas)",
        yaxis=dict(title="Masa Sólidos/Agua (t)"),
        yaxis2=dict(
            title="Cobre (kg)",
            overlaying='y',
            side='right'
        ),
        showlegend=True
    )
    return fig

def crear_grafico_leyes(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    if len(t) > 1:
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_chancado']) * 100,
            name='Ley Chancado', line=dict(color='purple', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_sag']) * 100,
            name='Ley SAG', line=dict(color='orange', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(historial['L_target']) * 100,
            name='Objetivo', line=dict(color='black', width=2, dash='dash')
        ))
    
    fig.update_layout(
        height=300,
        title="Comparación de Leyes",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Ley (%)",
        showlegend=True
    )
    return fig

def crear_grafico_cobre(historial):
    fig = go.Figure()
    
    t = np.array(historial['t'])
    if len(t) > 1:
        # Flujos de cobre
        F_cu_chancado = np.array(historial['F_chancado']) * np.array(historial['L_chancado'])
        F_cu_finos = np.array(historial['F_finos']) * np.array(historial['L_sag'])
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado,
            name='Cobre Chancado', line=dict(color='darkblue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_finos,
            name='Cobre Finos', line=dict(color='darkgreen', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado + F_cu_finos,
            name='Total', line=dict(color='black', width=1, dash='dot')
        ))
    
    fig.update_layout(
        height=300,
        title="Flujos de Cobre",
        xaxis_title="Tiempo (horas)",
        yaxis_title="Cobre (t/h)",
        showlegend=True
    )
    return fig

# Mostrar gráficos
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

# ================= INFORMACIÓN ADICIONAL =================

st.markdown("---")

with st.expander("📈 Información del Sistema"):
    estado = st.session_state.simulador.obtener_estado()
    params = st.session_state.simulador.params
    
    # Cálculos de equilibrio
    F_alimentacion = estado['F_actual'] + (historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] else 0)
    M_equilibrio = F_alimentacion / params['k_descarga'] if params['k_descarga'] > 0 else 0
    
    st.markdown(f"""
    ### **Estado Actual:**
    - **Tiempo simulado:** {estado['t']:.1f} horas
    - **Pasos ejecutados:** {st.session_state.pasos_ejecutados}
    - **Velocidad:** ~{10 if st.session_state.simulando else 0}x (10 pasos/segundo real)
    
    ### **Balance:**
    - **Alimentación total:** {F_alimentacion:.0f} t/h
    - **Descarga:** {historial['F_descarga'][-1] if historial['F_descarga'] else 0:.0f} t/h
    - **Masa equilibrio teórica:** {M_equilibrio:.0f} t
    - **Masa actual:** {estado['M_sag']:.0f} t
    
    ### **Variabilidad incluida:**
    - Ondas sinusoidales largas (±2%)
    - Ondas medias (±1%)
    - Ruido rápido (±0.5%)
    - Perturbaciones aleatorias ocasionales
    """)

# ================= PIE DE PÁGINA =================

st.markdown("---")

# Métricas finales
estado = st.session_state.simulador.obtener_estado()
col1, col2, col3, col4 = st.columns(4)

with col1:
    velocidad = "10x" if st.session_state.simulando else "0x"
    st.metric("Velocidad simulación", velocidad)

with col2:
    st.metric("Tiempo simulado", f"{estado['t']:.1f} h")

with col3:
    if historial['F_finos']:
        st.metric("Producción finos", f"{historial['F_finos'][-1]:.0f} t/h")

with col4:
    balance_actual = (estado['F_actual'] + (historial['F_sobre_tamano'][-1] if historial['F_sobre_tamano'] else 0) -
                     (historial['F_descarga'][-1] if historial['F_descarga'] else 0))
    estado_balance = "⚖️ Estable" if abs(balance_actual) < 100 else "📈 Subiendo" if balance_actual > 0 else "📉 Bajando"
    st.metric("Balance actual", f"{balance_actual:.0f} t/h", estado_balance)

# Mensaje de estado
if not st.session_state.simulando:
    st.info("⏸️ **Simulación en pausa** - Haz clic en INICIAR para comenzar")
else:
    st.success(f"🔄 **Simulación en curso** - {st.session_state.pasos_ejecutados} pasos ejecutados")

# Nota importante
st.caption("""
💡 **Nota:** La simulación avanza automáticamente cuando está activa. 
Cada paso representa 1 minuto de operación. La velocidad actual es de ~10 pasos por segundo real.
""")


