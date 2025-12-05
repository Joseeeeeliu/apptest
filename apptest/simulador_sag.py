"""
SIMULADOR SAG EN TIEMPO REAL
Versión optimizada para interactividad y expansión futura
Autor: [Tu nombre]
"""

import numpy as np
from collections import deque
import time

class SimuladorSAG:
    """
    CLASE PRINCIPAL DEL SIMULADOR
    
    Una clase es como un 'molde' que define:
    - Atributos: variables que guardan el estado (ej: masa_sag, tiempo)
    - Métodos: funciones que realizan acciones (ej: paso_simulacion, reset)
    
    Ventajas de usar clases:
    1. Organización: todo relacionado está junto
    2. Reutilización: puedes crear múltiples simuladores
    3. Encapsulación: datos protegidos, solo métodos públicos
    """
    
    def __init__(self, params):
        """
        MÉTODO CONSTRUCTOR: se ejecuta AL CREAR el simulador
        
        Parámetros:
        - params: diccionario con parámetros iniciales
        """
        
        # 1. GUARDAR PARÁMETROS (atributo de la clase)
        self.params = params.copy()
        
        # 2. ESTADO INICIAL DEL SISTEMA
        self.estado = {
            't': 0.0,                # Tiempo actual (horas)
            'M_sag': 10.0,           # Masa de sólidos en SAG (ton)
            'W_sag': 5.0,            # Masa de agua en SAG (ton)
            'M_cu_sag': 0.072,       # Masa de cobre en SAG (ton)
            'F_actual': 0.0,         # Flujo actual de alimentación (t/h)
            'L_actual': params['L_nominal'],  # Ley actual (%)
            'H_sag': params['humedad_sag']    # Humedad actual
        }
        
        # 3. OBJETIVOS ACTUALES (seguidos dinámicamente)
        self.objetivos = {
            'F_target': params['F_nominal'],  # Objetivo de flujo (t/h)
            'L_target': params['L_nominal']   # Objetivo de ley
        }
        
        # 4. BUFFERS PARA RETARDOS (estructuras de datos eficientes)
        # deque = "double-ended queue" (cola de dos extremos) de la biblioteca collections
        # Es MUY eficiente para agregar/remover elementos
        self.buffer_F = deque(maxlen=10000)    # Historial de flujos
        self.buffer_L = deque(maxlen=10000)    # Historial de leyes
        self.buffer_t = deque(maxlen=10000)    # Historial de tiempos
        
        # Inicializar buffers con valores iniciales
        self.buffer_F.append(self.estado['F_actual'])
        self.buffer_L.append(self.estado['L_actual'])
        self.buffer_t.append(self.estado['t'])
        
        # 5. HISTORIAL PARA GRÁFICOS
        self.historial = {
            't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
            'F_chancado': [], 'L_chancado': [], 'F_finos': [],
            'F_sobre_tamano': [], 'F_target': [], 'L_target': []
        }
        
        # 6. CONTROL DE SIMULACIÓN
        self.activo = False
        self.dt = 1/60  # Paso de tiempo: 1 minuto en horas (1/60)
        
    def calcular_alimentacion(self, dt):
        """
        Calcula la alimentación dinámica que persigue el objetivo
        
        Esta función simula que la planta 'intenta' alcanzar el valor
        del slider, pero con inercia (no cambia instantáneamente)
        
        Ecuación: dF/dt = (F_target - F_actual) / tau
        Donde tau = constante de tiempo (0.5 horas = 30 minutos)
        """
        
        # Parámetros de dinámica
        tau_F = 0.5  # 0.5 horas para cambios de flujo
        tau_L = 2.0  # 2.0 horas para cambios de ley (más lento)
        
        # 1. DINÁMICA DE FLUJO (Primer Orden)
        # Euler explícito: F_nuevo = F_actual + dF * dt
        dF_dt = (self.objetivos['F_target'] - self.estado['F_actual']) / tau_F
        F_nuevo = self.estado['F_actual'] + dF_dt * dt
        
        # 2. DINÁMICA DE LEY (Primer Orden)
        dL_dt = (self.objetivos['L_target'] - self.estado['L_actual']) / tau_L
        L_nuevo = self.estado['L_actual'] + dL_dt * dt
        
        # 3. AGREGAR VARIABILIDAD (similar al código original)
        if self.estado['t'] > 2.0:  # Después de 2 horas
            # Variación suave (no muy brusca para tiempo real)
            variacion_F = 0.02 * np.sin(0.3 * self.estado['t'])
            variacion_L = 0.01 * np.sin(0.5 * self.estado['t'] + 1.5)
            
            F_nuevo *= (1 + variacion_F)
            L_nuevo *= (1 + variacion_L)
            
            # Perturbaciones aleatorias ocasionales
            if np.random.random() < 0.001:  # 0.1% de probabilidad
                perturbacion = np.random.uniform(-0.05, 0.05)
                F_nuevo *= (1 + perturbacion)
        
        # 4. LIMITAR VALORES (para evitar imposibles físicos)
        F_nuevo = np.clip(F_nuevo, 0.1 * self.objetivos['F_target'], 
                         1.5 * self.objetivos['F_target'])
        L_nuevo = np.clip(L_nuevo, 0.7 * self.objetivos['L_target'], 
                         1.3 * self.objetivos['L_target'])
        
        return F_nuevo, L_nuevo
    
    def calcular_recirculacion(self, F_chancado_actual):
        """
        Calcula la recirculación con retardo de tiempo
        
        Usa buffers (colas) para simular que el material tarda
        en viajar por las correas transportadoras
        """
        
        # 1. AGREGAR VALOR ACTUAL AL BUFFER
        self.buffer_F.append(F_chancado_actual)
        self.buffer_t.append(self.estado['t'])
        
        # 2. CALCULAR RETRASO EN MINUTOS
        tau_rec_min = self.params['tau_recirculacion']  # ya está en minutos
        
        # 3. BUSCAR VALOR EN EL PASADO
        # Buscamos el tiempo: t_actual - tau_rec
        tiempo_pasado = self.estado['t'] - (tau_rec_min / 60.0)  # Convertir a horas
        
        # 4. ENCONTRAR EL VALOR MÁS CERCANO EN EL BUFFER
        if len(self.buffer_t) > 0 and tiempo_pasado > 0:
            # Buscar índice del tiempo más cercano
            diferencias = [abs(t - tiempo_pasado) for t in self.buffer_t]
            idx_min = diferencias.index(min(diferencias))
            
            # Obtener flujo de ese momento
            if idx_min < len(self.buffer_F):
                F_pasado = list(self.buffer_F)[idx_min]
                F_sobre_tamano = self.params['fraccion_recirculacion'] * F_pasado
                return F_sobre_tamano
        
        return 0.0  # Si no hay datos suficientes
    
    def calcular_finos(self, F_descarga, F_sobre_tamano):
        """
        Calcula producción de finos con retardo y dinámica
        """
        
        # 1. VERIFICAR SI HA PASADO SUFICIENTE TIEMPO
        tau_finos_min = self.params['tau_finos']  # minutos
        tau_finos_horas = tau_finos_min / 60.0
        
        if self.estado['t'] < tau_finos_horas:
            return 0.0
        
        # 2. CÁLCULO BÁSICO
        F_finos = F_descarga - F_sobre_tamano
        
        # 3. DINÁMICA DE ARRANQUE (crecimiento gradual)
        if self.estado['t'] < tau_finos_horas + 1.0:  # 1 hora después
            factor = 1 - np.exp(-(self.estado['t'] - tau_finos_horas) / 0.3)
            F_finos *= factor
        
        # 4. NO PERMITIR VALORES NEGATIVOS
        return max(0.0, F_finos)
    
    def paso_simulacion(self):
        """
        Ejecuta UN PASO de simulación usando Euler Explícito
        
        Euler Explícito es el método numérico MÁS SIMPLE:
        nuevo_valor = valor_actual + derivada * dt
        
        Es rápido pero menos preciso que métodos complejos.
        Para simulación interactiva, velocidad > precisión extrema.
        """
        
        # 1. CALCULAR ALIMENTACIÓN ACTUAL (persigue objetivo)
        F_chancado, L_chancado = self.calcular_alimentacion(self.dt)
        
        # 2. CALCULAR RECIRCULACIÓN (con retardo)
        F_sobre_tamano = self.calcular_recirculacion(F_chancado)
        
        # 3. ALIMENTACIÓN TOTAL AL SAG
        F_alimentacion_total = F_chancado + F_sobre_tamano
        
        # 4. PROPIEDADES ACTUALES DEL SAG
        M_sag = self.estado['M_sag']
        W_sag = self.estado['W_sag']
        M_cu_sag = self.estado['M_cu_sag']
        
        if M_sag > 0.001:
            L_sag = M_cu_sag / M_sag
            H_sag = W_sag / (M_sag + W_sag)
        else:
            L_sag = L_chancado
            H_sag = self.params['humedad_sag']
        
        # 5. CÁLCULO DE FLUJOS DE AGUA
        W_chancado = F_chancado * (self.params['humedad_alimentacion'] / 
                                  (1 - self.params['humedad_alimentacion']))
        W_recirculacion = F_sobre_tamano * (self.params['humedad_recirculacion'] / 
                                          (1 - self.params['humedad_recirculacion']))
        
        # 6. LEY DE ALIMENTACIÓN COMBINADA
        if F_alimentacion_total > 0:
            L_alimentacion_total = (L_chancado * F_chancado + 
                                   L_sag * F_sobre_tamano) / F_alimentacion_total
        else:
            L_alimentacion_total = 0
        
        # 7. AGUA ADICIONAL NECESARIA
        agua_necesaria = F_alimentacion_total * (self.params['humedad_sag'] / 
                                               (1 - self.params['humedad_sag']))
        agua_disponible = W_chancado + W_recirculacion
        W_adicional = max(0, agua_necesaria - agua_disponible)
        
        # 8. DESCARGA DEL SAG
        # k_descarga está en 1/hora, convertir a 1/minuto para dt en horas
        k_min = self.params['k_descarga'] / 60.0
        F_descarga = k_min * M_sag
        
        # 9. FINOS
        F_finos = self.calcular_finos(F_descarga, F_sobre_tamano)
        
        # 10. AGUA EN DESCARGA
        W_descarga = F_descarga * (H_sag / (1 - H_sag))
        
        # 11. ECUACIONES DIFERENCIALES (EULER EXPLÍCITO)
        # dM/dt = entrada - salida
        dM_dt = (F_alimentacion_total - F_descarga) / 60.0  # Convertir t/h a t/min
        dW_dt = (W_chancado + W_recirculacion + W_adicional - W_descarga) / 60.0
        dMcu_dt = (L_alimentacion_total * F_alimentacion_total - 
                  L_sag * F_descarga) / 60.0
        
        # 12. ACTUALIZAR ESTADO (INTEGRACIÓN)
        self.estado['M_sag'] += dM_dt * self.dt
        self.estado['W_sag'] += dW_dt * self.dt
        self.estado['M_cu_sag'] += dMcu_dt * self.dt
        self.estado['t'] += self.dt
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
        self.estado['H_sag'] = H_sag
        
        # 13. GUARDAR EN HISTORIAL (cada 10 pasos para eficiencia)
        if int(self.estado['t'] / self.dt) % 10 == 0:
            self.historial['t'].append(self.estado['t'])
            self.historial['M_sag'].append(self.estado['M_sag'])
            self.historial['W_sag'].append(self.estado['W_sag'])
            self.historial['M_cu_sag'].append(self.estado['M_cu_sag'])
            self.historial['F_chancado'].append(F_chancado)
            self.historial['L_chancado'].append(L_chancado)
            self.historial['F_finos'].append(F_finos)
            self.historial['F_sobre_tamano'].append(F_sobre_tamano)
            self.historial['F_target'].append(self.objetivos['F_target'])
            self.historial['L_target'].append(self.objetivos['L_target'])
        
        # 14. RETORNAR ESTADO ACTUAL
        return {
            'tiempo': self.estado['t'],
            'M_sag': self.estado['M_sag'],
            'W_sag': self.estado['W_sag'],
            'M_cu_sag': self.estado['M_cu_sag'],
            'F_chancado': F_chancado,
            'L_chancado': L_chancado,
            'F_finos': F_finos,
            'F_sobre_tamano': F_sobre_tamano,
            'F_alimentacion_total': F_alimentacion_total,
            'F_descarga': F_descarga
        }
    
    def actualizar_objetivo(self, tipo, valor):
        """
        Método para cambiar objetivos desde Streamlit
        
        Parámetros:
        - tipo: 'F' para flujo, 'L' para ley
        - valor: nuevo valor objetivo
        """
        if tipo == 'F':
            self.objetivos['F_target'] = valor
        elif tipo == 'L':
            self.objetivos['L_target'] = valor
    
    def reset(self):
        """Reinicia la simulación a condiciones iniciales"""
        self.__init__(self.params)
    
    def obtener_historial(self):
        """Retorna todo el historial para graficar"""
        return self.historial.copy()


# FUNCIÓN PARA CREAR PARÁMETROS POR DEFECTO
def crear_parametros_default():
    """Retorna diccionario con parámetros por defecto"""
    return {
        'F_nominal': 45000/(24*0.94),  # Flujo nominal (t/h)
        'L_nominal': 0.0072,           # Ley nominal (0.72%)
        'fraccion_recirculacion': 0.11,# 11% de recirculación
        'humedad_alimentacion': 0.035, # 3.5% humedad alimentación
        'humedad_sag': 0.30,           # 30% humedad SAG
        'humedad_recirculacion': 0.08, # 8% humedad recirculación
        'k_descarga': 1.0,             # Constante de descarga (1/h)
        'tau_recirculacion': 90,       # Retardo recirculación (minutos)
        'tau_finos': 48                # Retardo finos (minutos)
    }