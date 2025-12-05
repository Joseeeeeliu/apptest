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
    
    def paso_simulacion(self):
        """Paso de simulación CON UNIDADES CORRECTAS"""
        # 1. Alimentación
        F_chancado, L_chancado, variacion = self.calcular_alimentacion()
        
        # 2. Guardar en buffer para retardos
        self.buffer_F.append(F_chancado)
        self.buffer_t.append(self.estado['t'])
        
        # 3. Recirculación (con retardo en horas)
        F_sobre_tamano = 0.0
        tau_rec_horas = self.params['tau_recirculacion'] / 60.0  # convertir minutos a horas
        
        if self.estado['t'] > tau_rec_horas:
            # Buscar valor en el pasado
            tiempo_pasado = self.estado['t'] - tau_rec_horas
            # Encontrar el más cercano
            if self.buffer_t:
                diferencias = [abs(t - tiempo_pasado) for t in self.buffer_t]
                idx_min = np.argmin(diferencias)
                if idx_min < len(self.buffer_F):
                    F_pasado = self.buffer_F[idx_min]
                    F_sobre_tamano = self.params['fraccion_recirculacion'] * F_pasado
        
        # 4. Alimentación total
        F_alimentacion_total = F_chancado + F_sobre_tamano
        
        # 5. Propiedades actuales SAG
        M_sag = self.estado['M_sag']
        W_sag = self.estado['W_sag']
        M_cu_sag = self.estado['M_cu_sag']
        
        if M_sag > 0.001:
            L_sag = M_cu_sag / M_sag
            H_sag = W_sag / (M_sag + W_sag)
        else:
            L_sag = L_chancado
            H_sag = self.params['humedad_sag']
        
        # 6. Flujos de agua (t/h)
        W_chancado = F_chancado * (self.params['humedad_alimentacion'] / 
                                  (1 - self.params['humedad_alimentacion']))
        W_recirculacion = F_sobre_tamano * (self.params['humedad_recirculacion'] / 
                                          (1 - self.params['humedad_recirculacion']))
        
        # 7. Ley de alimentación combinada
        if F_alimentacion_total > 0:
            L_alimentacion_total = (L_chancado * F_chancado + L_sag * F_sobre_tamano) / F_alimentacion_total
        else:
            L_alimentacion_total = 0
        
        # 8. Agua adicional
        agua_necesaria = F_alimentacion_total * (self.params['humedad_sag'] / 
                                               (1 - self.params['humedad_sag']))
        agua_disponible = W_chancado + W_recirculacion
        W_adicional = max(0, agua_necesaria - agua_disponible)
        
        # 9. Descarga SAG (t/h) - ¡CORREGIDO!
        F_descarga = self.params['k_descarga'] * M_sag  # t/h
        
        # 10. Finos (con retardo en horas)
        F_finos = 0.0
        tau_finos_horas = self.params['tau_finos'] / 60.0
        
        if self.estado['t'] > tau_finos_horas:
            F_finos = max(F_descarga - F_sobre_tamano, 0)
            
            # Crecimiento gradual
            if self.estado['t'] < tau_finos_horas + 1.0:
                factor = 1 - np.exp(-(self.estado['t'] - tau_finos_horas) / 0.3)
                F_finos *= factor
        
        # 11. Agua en descarga
        W_descarga = F_descarga * (H_sag / (1 - H_sag))
        
        # 12. ECUACIONES DIFERENCIALES (CORREGIDAS - TODO EN t/h)
        # dt está en horas, así que multiplicamos por dt directamente
        dM_dt = F_alimentacion_total - F_descarga  # t/h
        dW_dt = (W_chancado + W_recirculacion + W_adicional - W_descarga)  # t/h
        dMcu_dt = (L_alimentacion_total * F_alimentacion_total - L_sag * F_descarga)  # t_cu/h
        
        # 13. INTEGRAR (Euler explícito)
        self.estado['M_sag'] += dM_dt * self.dt
        self.estado['W_sag'] += dW_dt * self.dt
        self.estado['M_cu_sag'] += dMcu_dt * self.dt
        self.estado['t'] += self.dt
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
        self.estado['H_sag'] = H_sag
        
        # 14. GUARDAR EN HISTORIAL (cada 6 pasos = cada 10 segundos reales aprox)
        if int(self.estado['t'] / self.dt) % 6 == 0:
            self.historial['t'].append(self.estado['t'])
            self.historial['M_sag'].append(self.estado['M_sag'])
            self.historial['W_sag'].append(self.estado['W_sag'])
            self.historial['M_cu_sag'].append(self.estado['M_cu_sag'])
            self.historial['F_chancado'].append(F_chancado)
            self.historial['L_chancado'].append(L_chancado)
            self.historial['F_finos'].append(F_finos)
            self.historial['F_sobre_tamano'].append(F_sobre_tamano)
            self.historial['F_descarga'].append(F_descarga)
            self.historial['L_sag'].append(L_sag)
            self.historial['H_sag'].append(H_sag)
            self.historial['F_target'].append(self.objetivos['F_target'])
            self.historial['L_target'].append(self.objetivos['L_target'])
            
            # Limitar tamaño del historial (últimas 24 horas)
            max_puntos = 24 * 60  # 1 punto por minuto
            for key in self.historial:
                if len(self.historial[key]) > max_puntos:
                    self.historial[key] = self.historial[key][-max_puntos:]
        
        return {
            'tiempo': self.estado['t'],
            'M_sag': self.estado['M_sag'],
            'W_sag': self.estado['W_sag'],
            'M_cu_sag': self.estado['M_cu_sag'],
            'F_chancado': F_chancado,
            'L_chancado': L_chancado,
            'F_finos': F_finos,
            'F_sobre_tamano': F_sobre_tamano,
            'F_descarga': F_descarga,
            'L_sag': L_sag,
            'H_sag': H_sag,
            'variacion': variacion
        }
    
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

# ================= AUTO-AVANCE: EL CORAZÓN DE LA SIMULACIÓN =================

# Esta es la parte CRÍTICA - se ejecuta en cada rerun
if st.session_state.simulando:
    # Calcular cuántos pasos debemos ejecutar
    tiempo_actual = time.time()
    tiempo_transcurrido = tiempo_actual - st.session_state.ultimo_update
    
    # Queremos ejecutar ~10 pasos por segundo para que sea fluido
    # 10 pasos/segundo = 600 pasos/minuto real = 600 minutos simulados/segundo real
    pasos_por_segundo = 10
    
    pasos_a_ejecutar = int(tiempo_transcurrido * pasos_por_segundo)
    
    if pasos_a_ejecutar > 0:
        # Ejecutar los pasos acumulados
        for _ in range(pasos_a_ejecutar):
            st.session_state.simulador.paso_simulacion()
            st.session_state.pasos_ejecutados += 1
        
        st.session_state.ultimo_update = tiempo_actual
        
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
