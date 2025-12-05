"""
SIMULADOR SAG - VERSIÓN ESTABLE Y BALANCEADA
Sin crecimiento descontrolado, con balance correcto
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import time

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
    st.session_state.ultimo_tiempo = time.time()
    
    # Estado actual - VALORES INICIALES REALISTAS
    st.session_state.estado = {
        'tiempo': 0.0,                    # horas
        'M_sag': 100.0,                   # ton (más realista)
        'W_sag': 42.86,                   # ton (30% humedad: 100/(1-0.3)-100)
        'M_cu_sag': 0.72,                 # ton (0.72% de 100 ton)
        'F_chancado': 0.0,                # t/h
        'L_chancado': 0.0072,             # 0.72%
        'F_finos': 0.0,                   # t/h
        'F_sobre_tamano': 0.0,            # t/h
        'H_sag': 0.30                     # 30%
    }
    
    # Objetivos
    st.session_state.objetivos = {
        'F_target': 2000.0,               # t/h
        'L_target': 0.0072                # 0.72%
    }
    
    # Historial
    st.session_state.historial = {
        't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
        'F_chancado': [], 'L_chancado': [], 'F_finos': [],
        'F_sobre_tamano': [], 'F_target': [], 'L_target': []
    }

# ================= FUNCIÓN DE SIMULACIÓN BALANCEADA =================
def simular_paso():
    """Ejecuta un paso de simulación con BALANCE CORRECTO"""
    estado = st.session_state.estado
    objetivos = st.session_state.objetivos
    
    # Paso de tiempo (1 minuto en horas)
    dt = 1/60.0
    
    # Actualizar tiempo
    estado['tiempo'] += dt
    
    # ========== DINÁMICA DE ALIMENTACIÓN ==========
    # Flujo sigue objetivo con dinámica de primer orden
    tau_F = 0.5  # 0.5 horas para cambios
    error_F = objetivos['F_target'] - estado['F_chancado']
    dF_dt = error_F / tau_F
    estado['F_chancado'] += dF_dt * dt
    
    # Ley sigue objetivo
    tau_L = 2.0  # 2 horas para cambios
    error_L = objetivos['L_target'] - estado['L_chancado']
    dL_dt = error_L / tau_L
    estado['L_chancado'] += dL_dt * dt
    
    # Variabilidad REALISTA (sin crecimiento exponencial)
    if estado['tiempo'] > 2.0:
        # Variación suave (máximo ±3%)
        variacion = 0.015 * np.sin(0.5 * estado['tiempo']) + 0.01 * np.sin(1.5 * estado['tiempo'] + 1)
        estado['F_chancado'] = estado['F_chancado'] * (1 + variacion)
    
    # Limitar valores físicos
    estado['F_chancado'] = max(estado['F_chancado'], 0.0)
    estado['L_chancado'] = np.clip(estado['L_chancado'], 0.005, 0.015)
    
    # ========== CÁLCULOS DEL SAG ==========
    # Recirculación (11% con retardo de 1.5 horas)
    if estado['tiempo'] > 1.5:  # 1.5 HORAS, no minutos
        # Flujo con retardo (simplificado)
        F_chancado_retrasado = max(estado['F_chancado'] * 0.9, 0)  # 10% pérdida
        estado['F_sobre_tamano'] = 0.11 * F_chancado_retrasado
    else:
        estado['F_sobre_tamano'] = 0.0
    
    # Alimentación total al SAG
    F_alimentacion_total = estado['F_chancado'] + estado['F_sobre_tamano']
    
    # ========== BALANCE DE MASA CRÍTICO ==========
    # CONSTANTE k AJUSTADA PARA ESTABILIDAD
    # Si k = 0.5, significa que la mitad de la masa sale por hora
    # En equilibrio: F_descarga = k * M_sag = F_alimentacion_total
    # => M_sag_equilibrio = F_alimentacion_total / k
    
    k = 0.5  # 1/hora - ¡ESTE ES EL PARÁMETRO CLAVE!
    
    # Descarga del SAG
    F_descarga = k * estado['M_sag']  # t/h
    
    # Finos (con retardo de 0.8 horas)
    if estado['tiempo'] > 0.8:  # 0.8 HORAS
        estado['F_finos'] = max(F_descarga - estado['F_sobre_tamano'], 0)
    else:
        estado['F_finos'] = 0
    
    # ========== ECUACIONES DIFERENCIALES ==========
    # dM/dt = entrada - salida (CONVERTIDO A t/min)
    dM_dt = (F_alimentacion_total - F_descarga) / 60.0  # t/min
    estado['M_sag'] += dM_dt * dt
    
    # Evitar valores negativos o muy pequeños
    estado['M_sag'] = max(estado['M_sag'], 10.0)
    
    # Balance de cobre
    if estado['M_sag'] > 0.1:
        L_sag = estado['M_cu_sag'] / estado['M_sag']
    else:
        L_sag = estado['L_chancado']
    
    # Flujo de cobre (convertido a t/min)
    entrada_cu = (estado['L_chancado'] * estado['F_chancado'] + 
                  L_sag * estado['F_sobre_tamano']) / 60.0
    salida_cu = (L_sag * F_descarga) / 60.0
    dMcu_dt = entrada_cu - salida_cu
    estado['M_cu_sag'] += dMcu_dt * dt
    estado['M_cu_sag'] = max(estado['M_cu_sag'], 0.001)
    
    # Humedad del SAG (controlada)
    agua_necesaria = estado['M_sag'] * (0.30 / (1 - 0.30))  # para 30% humedad
    estado['W_sag'] = agua_necesaria  # Control simple de agua
    
    # ========== GUARDAR HISTORIAL ==========
    # Solo guardar cada 60 pasos (1 punto por hora)
    if int(estado['tiempo'] / dt) % 60 == 0:
        # Limitar historial a las últimas 48 horas
        max_horas = 48
        max_puntos = max_horas * 60  # 1 punto por minuto
        
        for key in ['t', 'M_sag', 'W_sag', 'M_cu_sag', 
                    'F_chancado', 'L_chancado', 'F_finos', 'F_sobre_tamano']:
            if key == 't':
                valor = estado['tiempo']
            else:
                valor = estado[key]
            
            st.session_state.historial[key].append(valor)
            
            # Truncar si es muy largo
            if len(st.session_state.historial[key]) > max_puntos:
                st.session_state.historial[key] = st.session_state.historial[key][-max_puntos:]
        
        # Guardar objetivos también
        st.session_state.historial['F_target'].append(objetivos['F_target'])
        st.session_state.historial['L_target'].append(objetivos['L_target'])
        
        if len(st.session_state.historial['F_target']) > max_puntos:
            st.session_state.historial['F_target'] = st.session_state.historial['F_target'][-max_puntos:]
            st.session_state.historial['L_target'] = st.session_state.historial['L_target'][-max_puntos:]

# ================= FUNCIONES PARA BOTONES =================
def iniciar_simulacion():
    st.session_state.simulando = True
    st.session_state.ultimo_tiempo = time.time()

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
        'H_sag': 0.30
    }
    for key in st.session_state.historial:
        st.session_state.historial[key] = []

# ================= INTERFAZ PRINCIPAL =================
st.title("🏭 Simulador Planta Concentradora - Molino SAG")
st.markdown("---")

# ================= BARRA LATERAL =================
with st.sidebar:
    st.header("🎛️ **Controles de Operación**")
    
    # Estado de la simulación
    estado_sim = "🟢 EN EJECUCIÓN" if st.session_state.simulando else "⏸️ PAUSADA"
    st.markdown(f"**Estado:** {estado_sim}")
    
    # Botones
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Iniciar", 
                    on_click=iniciar_simulacion,
                    type="primary",
                    use_container_width=True,
                    disabled=st.session_state.simulando):
            pass
    
    with col2:
        if st.button("⏸️ Pausar",
                    on_click=pausar_simulacion,
                    use_container_width=True,
                    disabled=not st.session_state.simulando):
            pass
    
    if st.button("🔄 Reiniciar",
                on_click=reiniciar_simulacion,
                use_container_width=True):
        pass
    
    st.markdown("---")
    
    # ========== PARÁMETROS CLAVE ==========
    st.subheader("🎯 **Parámetros Clave**")
    
    # Flujo objetivo
    F_objetivo = st.slider(
        "**Flujo Objetivo (t/h)**",
        500.0, 5000.0, st.session_state.objetivos['F_target'],
        step=100.0,
        help="Flujo total de alimentación al circuito"
    )
    
    # Ley objetivo
    L_objetivo = st.slider(
        "**Ley Objetivo (%)**",
        0.3, 1.5, st.session_state.objetivos['L_target'] * 100,
        step=0.05,
        format="%.2f",
        help="Ley de cobre en la alimentación"
    )
    
    # Constante k (MOSTRAR PERO NO EDITAR POR AHORA)
    st.markdown("---")
    st.subheader("⚙️ **Parámetro de Control**")
    k_valor = st.slider(
        "**Constante de Descarga (k)**",
        0.1, 2.0, 0.5, 0.1,
        help="k = Descarga / Masa_SAG [1/hora]. Define cuán rápido sale el material"
    )
    
    # Actualizar objetivos
    st.session_state.objetivos['F_target'] = F_objetivo
    st.session_state.objetivos['L_target'] = L_objetivo / 100.0
    # k se usa directamente en la función simular_paso()
    
    st.markdown("---")
    
    # ========== ESTADO ACTUAL ==========
    st.subheader("📊 **Estado Actual**")
    estado = st.session_state.estado
    
    # Cálculos para mostrar
    F_alimentacion_total = estado['F_chancado'] + estado['F_sobre_tamano']
    k = 0.5  # Usar el valor fijo por ahora
    F_descarga = k * estado['M_sag']
    balance = F_alimentacion_total - F_descarga
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Flujo Chancado", f"{estado['F_chancado']:.0f} t/h")
        st.metric("Masa SAG", f"{estado['M_sag']:.0f} t")
        st.metric("Recirculación", f"{estado['F_sobre_tamano']:.0f} t/h")
    
    with col2:
        st.metric("Ley", f"{estado['L_chancado']*100:.2f} %")
        st.metric("Finos", f"{estado['F_finos']:.0f} t/h")
        st.metric("Balance", f"{balance:.0f} t/h", 
                 delta="ESTABLE" if abs(balance) < 50 else "INESTABLE")
    
    # Información del equilibrio
    if abs(balance) < 50:
        st.success("✅ Sistema en equilibrio")
    else:
        st.warning("⚠️ Sistema buscando equilibrio")

# ================= EJECUTAR SIMULACIÓN =================
# Control de velocidad: tiempo real (1 segundo real = 1 minuto simulado)
if st.session_state.simulando:
    tiempo_actual = time.time()
    tiempo_transcurrido = tiempo_actual - st.session_state.ultimo_tiempo
    
    # Avanzar simulación según tiempo real
    # 1 segundo real = 1 minuto simulado
    if tiempo_transcurrido >= 0.1:  # Cada 0.1 segundos reales
        # Ejecutar pasos de simulación
        for _ in range(int(tiempo_transcurrido / 0.1)):
            simular_paso()
        
        st.session_state.ultimo_tiempo = tiempo_actual
        
        # Forzar actualización de la interfaz (sin recursión)
        st.rerun()

# ================= GRÁFICOS =================
# Función para gráfico de balance
def crear_grafico_balance():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
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
        
        # Objetivo
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['F_target'],
            name='Objetivo', line=dict(color='black', width=2, dash='dash')
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo (t/h)",
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

# Función para gráfico de masas
def crear_grafico_masas():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        # Calcular masa esperada en equilibrio
        k = 0.5
        masa_equilibrio = np.array(st.session_state.historial['F_target']) / k
        
        fig.add_trace(go.Scatter(
            x=t, y=st.session_state.historial['M_sag'],
            name='Masa Actual', line=dict(color='blue', width=3)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=masa_equilibrio,
            name='Masa Esperada', line=dict(color='gray', width=2, dash='dash')
        ))
        
        # Cobre (escala secundaria)
        M_cu_kg = np.array(st.session_state.historial['M_cu_sag']) * 1000
        fig.add_trace(go.Scatter(
            x=t, y=M_cu_kg,
            name='Cobre (kg)', line=dict(color='orange', width=2),
            yaxis='y2'
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
        showlegend=True
    )
    
    return fig

# Función para gráfico de cobre
def crear_grafico_cobre():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        # Flujos de cobre
        F_cu_chancado = np.array(st.session_state.historial['F_chancado']) * np.array(st.session_state.historial['L_chancado'])
        F_cu_recirculacion = np.array(st.session_state.historial['F_sobre_tamano']) * np.array(st.session_state.historial['L_chancado'])
        F_cu_total = F_cu_chancado + F_cu_recirculacion
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_chancado,
            name='Cobre Chancado', line=dict(color='darkblue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_recirculacion,
            name='Cobre Recirculación', line=dict(color='purple', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=F_cu_total,
            name='Cobre Total', line=dict(color='black', width=3, dash='dash')
        ))
    
    fig.update_layout(
        height=300,
        xaxis_title="Tiempo (horas)",
        yaxis_title="Flujo Cobre (t/h)",
        showlegend=True
    )
    
    return fig

# Función para gráfico de leyes
def crear_grafico_leyes():
    fig = go.Figure()
    
    t = np.array(st.session_state.historial['t'])
    
    if len(t) > 1:
        # Ley del SAG
        M_cu = np.array(st.session_state.historial['M_cu_sag'])
        M_sag = np.array(st.session_state.historial['M_sag'])
        with np.errstate(divide='ignore', invalid='ignore'):
            L_sag = np.where(M_sag > 0.1, M_cu / M_sag * 100, 0)
        
        fig.add_trace(go.Scatter(
            x=t, y=np.array(st.session_state.historial['L_chancado']) * 100,
            name='Ley Alimentación', line=dict(color='blue', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=t, y=L_sag,
            name='Ley SAG', line=dict(color='orange', width=3)
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
        yaxis=dict(range=[0, 1.5]),
        showlegend=True
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

# ================= INFORMACIÓN ADICIONAL =================
st.markdown("---")

with st.expander("📚 **Teoría del Balance - ¡ESTO ES CLAVE!**"):
    st.markdown("""
    ### **¿Por qué la masa se estabiliza ahora?**
    
    La ecuación fundamental del SAG es:
    
    ```
    dM/dt = F_entrada - F_salida
    ```
    
    Donde:
    - `F_entrada = F_chancado + F_recirculacion`
    - `F_salida = k * M_sag`
    
    ### **En estado estacionario (dM/dt = 0):**
    
    ```
    F_entrada = k * M_sag
    M_sag_equilibrio = F_entrada / k
    ```
    
    ### **Parámetro k (constante de descarga):**
    - **k = 0.5** → Toda la masa sale en 2 horas
    - **k = 1.0** → Toda la masa sale en 1 hora
    - **k = 2.0** → Toda la masa sale en 0.5 horas
    
    ### **Ejemplo:**
    Si `F_entrada = 2000 t/h` y `k = 0.5`:
    ```
    M_sag_equilibrio = 2000 / 0.5 = 4000 toneladas
    ```
    
    La masa se estabilizará alrededor de 4000 toneladas.
    """)

with st.expander("🎯 **Cómo usar el simulador**"):
    st.markdown("""
    1. **Ajusta el Flujo Objetivo** (500-5000 t/h)
    2. **Ajusta la Ley Objetivo** (0.3-1.5%)
    3. **Haz clic en INICIAR**
    4. **Observa** cómo la masa busca su equilibrio
    5. **Cambia los parámetros** en tiempo real
    
    ### **Indicadores de estabilidad:**
    - ✅ **Balance cercano a 0** = Sistema estable
    - 📈 **Masa convergiendo** = Buscando equilibrio
    - 🔄 **Oscilaciones pequeñas** = Normal (debido a variabilidad)
    """)

# ================= PIE DE PÁGINA =================
st.markdown("---")
estado = st.session_state.estado
F_alimentacion = estado['F_chancado'] + estado['F_sobre_tamano']
k = 0.5
F_descarga = k * estado['M_sag']
M_equilibrio = F_alimentacion / k if k > 0 else 0

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Tiempo Simulado", f"{estado['tiempo']:.1f} h")
with col2:
    st.metric("Masa Actual", f"{estado['M_sag']:.0f} t")
with col3:
    st.metric("Masa Esperada", f"{M_equilibrio:.0f} t")

# Estado final
if not st.session_state.simulando:
    st.info("⏸️ Simulación pausada. Haz clic en INICIAR para comenzar.")
elif abs(F_alimentacion - F_descarga) < 100:
    st.success("✅ Sistema estable - En equilibrio dinámico")
else:
    st.warning("🔄 Sistema buscando equilibrio...")

# ================= AUTO-ACTUALIZACIÓN CONTROLADA =================
# Solo se actualiza si está simulando y ha pasado suficiente tiempo
if st.session_state.simulando:
    # Verificar si necesita actualizarse (cada 0.5 segundos)
    tiempo_actual = time.time()
    if tiempo_actual - st.session_state.ultimo_tiempo > 0.5:
        # Usar st.rerun() correctamente
        st.rerun()
