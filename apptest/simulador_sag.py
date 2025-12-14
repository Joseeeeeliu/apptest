"""
SIMULADOR SAG EN TIEMPO REAL - VERSIÓN CON ARRANQUE GRADUAL
Retardos realistas con transición suave + variaciones senoidales en ley
"""

import numpy as np
from collections import deque

class SimuladorSAG:
    """
    Clase principal para simulación dinámica de molino SAG
    """
    
    def __init__(self, params):
        """
        Inicializa el simulador con parámetros dados
        
        Args:
            params: Diccionario con parámetros de operación
        """
        self.params = params.copy()
        
        # Estado inicial del sistema
        self.estado = {
            't': 0.0,                         # Tiempo actual (horas)
            'M_sag': 100.0,                   # Masa de sólidos en SAG (ton)
            'W_sag': 42.86,                   # Masa de agua en SAG (ton)
            'M_cu_sag': 0.72,                 # Masa de cobre en SAG (ton)
            'F_actual': params['F_nominal'],  # Flujo actual chancado (t/h)
            'L_actual': params['L_nominal'],  # Ley actual (decimal)
            'H_sag': params['humedad_sag']    # Humedad actual (decimal)
        }
        
        # Objetivos de operación
        self.objetivos = {
            'F_target': params['F_nominal'],
            'L_target': params['L_nominal']
        }
        
        # Parámetros de dinámica (ajustables desde UI)
        self.tau_F = 1.0  # Constante de tiempo para flujo (horas)
        self.tau_L = 1.0  # Constante de tiempo para ley (horas)
        
        # Parámetros de variabilidad
        self.amplitud_variacion_ley = 0.03  # ±3% de variación en ley
        self.amplitud_variacion_flujo = 0.0  # Sin variación en flujo por defecto
        
        # Buffers para retardos
        self.buffer_F = deque(maxlen=10000)
        self.buffer_t = deque(maxlen=10000)
        
        # Inicializar buffers
        self.buffer_F.append(self.estado['F_actual'])
        self.buffer_t.append(self.estado['t'])
        
        # Historial para gráficos
        self.historial = {
            't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
            'F_chancado': [], 'L_chancado': [], 'F_finos': [],
            'F_sobre_tamano': [], 'F_target': [], 'L_target': [],
            'F_descarga': [], 'L_sag': [], 'H_sag': []
        }
        
        # Control de simulación
        self.dt = 1/60.0  # 1 minuto en horas
        self.semilla_aleatoria = np.random.randint(1, 10000)
        np.random.seed(self.semilla_aleatoria)
    
    def calcular_alimentacion_chancado(self, dt):
        """
        Calcula el flujo y ley de CHANCADO con dinámica de primer orden
        + variaciones senoidales en la ley
        
        Args:
            dt: Paso de tiempo en horas
            
        Returns:
            tuple: (F_chancado, L_chancado) en t/h y decimal
        """
        
        t = self.estado['t']
        
        # ========== FLUJO DE CHANCADO ==========
        
        # Dinámica de primer orden simple
        F_target = self.objetivos['F_target']
        F_actual = self.estado['F_actual']
        
        cambio_F = (F_target - F_actual) / self.tau_F * dt
        F_base = F_actual + cambio_F
        
        # Variaciones senoidales en flujo (opcional, por defecto 0%)
        if self.amplitud_variacion_flujo > 0:
            onda_F1 = 0.5 * np.sin(0.2 * t)
            onda_F2 = 0.3 * np.sin(0.5 * t + 1.2)
            onda_F3 = 0.2 * np.sin(1.1 * t + 2.5)
            
            # Normalizar ondas (máximo ±1.0)
            variacion_F = (onda_F1 + onda_F2 + onda_F3) / 1.0
            
            F_chancado = F_base * (1 + self.amplitud_variacion_flujo * variacion_F)
        else:
            F_chancado = F_base
        
        # Límites físicos absolutos
        F_chancado = max(0.0, min(F_chancado, 5000.0))
        
        
        # ========== LEY DE CHANCADO ==========
        
        # Dinámica de primer orden hacia el objetivo
        L_target = self.objetivos['L_target']
        L_actual = self.estado['L_actual']
        
        cambio_L = (L_target - L_actual) / self.tau_L * dt
        L_base = L_actual + cambio_L
        
        # Variaciones senoidales en ley (SIEMPRE activas)
        # Tres componentes de diferente frecuencia
        onda_L1 = 0.5 * np.sin(0.4 * t + 0.8)      # Periodo ~16h
        onda_L2 = 0.3 * np.sin(0.9 * t + 1.5)      # Periodo ~7h
        onda_L3 = 0.2 * np.sin(1.3 * t + 3.0)      # Periodo ~5h
        
        # Ruido blanco pequeño
        ruido_L = np.random.normal(0, 0.05)
        
        # Normalizar (máximo ±1.0)
        variacion_L = (onda_L1 + onda_L2 + onda_L3 + ruido_L) / 1.0
        
        # Aplicar amplitud controlada
        L_chancado = L_base * (1 + self.amplitud_variacion_ley * variacion_L)
        
        # Límites físicos absolutos
        L_chancado = max(0.003, min(L_chancado, 0.015))
        
        # Actualizar estado
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
        
        return F_chancado, L_chancado
    
    def calcular_recirculacion(self, F_chancado_actual):
        """
        Calcula la recirculación con retardo de tiempo y arranque gradual
        
        OPCIÓN B: Arranque gradual
        - t < tau_rec: retorno = 0 (aún no llega nada)
        - tau_rec <= t < tau_rec + 15min: transición gradual 0% → 100%
        - t >= tau_rec + 15min: retorno = valor completo
        
        Args:
            F_chancado_actual: Flujo actual de chancado (t/h)
            
        Returns:
            float: Flujo de sobretamaño (t/h)
        """
        # Agregar valor actual al buffer
        self.buffer_F.append(F_chancado_actual)
        self.buffer_t.append(self.estado['t'])
        
        # Calcular retraso en horas
        tau_rec_horas = self.params['tau_recirculacion'] / 60.0
        tiempo_transicion = 15.0 / 60.0  # 15 minutos de transición
        
        # Tiempo en el pasado que queremos leer
        tiempo_pasado = self.estado['t'] - tau_rec_horas
        
        # CASO 1: Aún no ha pasado el tiempo de retardo
        if self.estado['t'] < tau_rec_horas:
            return 0.0  # No hay recirculación aún
        
        # CASO 2: Buscar valor en el buffer
        F_recirculacion_ideal = 0.0
        
        if len(self.buffer_t) > 0 and tiempo_pasado >= 0:
            # Buscar índice del tiempo más cercano
            diferencias = [abs(t - tiempo_pasado) for t in self.buffer_t]
            idx_min = diferencias.index(min(diferencias))
            
            if idx_min < len(self.buffer_F):
                F_pasado = list(self.buffer_F)[idx_min]
                F_recirculacion_ideal = self.params['fraccion_recirculacion'] * F_pasado
        
        # CASO 3: Aplicar factor de arranque gradual
        if self.estado['t'] < tau_rec_horas + tiempo_transicion:
            # Transición gradual: 0% → 100% en 15 minutos
            tiempo_desde_inicio = self.estado['t'] - tau_rec_horas
            factor_arranque = tiempo_desde_inicio / tiempo_transicion
            factor_arranque = max(0.0, min(1.0, factor_arranque))  # Clip [0, 1]
            
            return F_recirculacion_ideal * factor_arranque
        
        # CASO 4: Ya está completamente estable
        return F_recirculacion_ideal
    
    def calcular_finos(self, F_descarga, F_sobre_tamano):
        """
        Calcula producción de finos con retardo y arranque gradual
        
        OPCIÓN B: Arranque gradual
        - t < tau_finos: finos = 0 (aún no sale nada)
        - tau_finos <= t < tau_finos + 15min: transición gradual 0% → 100%
        - t >= tau_finos + 15min: finos = valor completo
        
        Args:
            F_descarga: Flujo de descarga del SAG (t/h)
            F_sobre_tamano: Flujo de sobretamaño (t/h)
            
        Returns:
            float: Flujo de finos (t/h)
        """
        tau_finos_horas = self.params['tau_finos'] / 60.0
        tiempo_transicion = 15.0 / 60.0  # 15 minutos de transición
        
        # Cálculo ideal de finos
        F_finos_ideal = F_descarga - F_sobre_tamano
        F_finos_ideal = max(0.0, F_finos_ideal)  # No puede ser negativo
        
        # CASO 1: Aún no ha pasado el tiempo de retardo
        if self.estado['t'] < tau_finos_horas:
            return 0.0  # No hay producción de finos aún
        
        # CASO 2: Transición gradual
        elif self.estado['t'] < tau_finos_horas + tiempo_transicion:
            # Rampa lineal: 0% → 100% en 15 minutos
            tiempo_desde_inicio = self.estado['t'] - tau_finos_horas
            factor_arranque = tiempo_desde_inicio / tiempo_transicion
            factor_arranque = max(0.0, min(1.0, factor_arranque))
            
            return F_finos_ideal * factor_arranque
        
        # CASO 3: Ya está completamente estable
        else:
            return F_finos_ideal
    
    def paso_simulacion(self):
        """
        Ejecuta UN PASO de simulación
        
        Returns:
            dict: Estado actual del sistema
        """
        
        # ===== PASO 1: CHANCADO =====
        F_chancado, L_chancado = self.calcular_alimentacion_chancado(self.dt)
        
        # ===== PASO 2: RECIRCULACIÓN =====
        F_sobre_tamano = self.calcular_recirculacion(F_chancado)
        
        # ===== PASO 3: ALIMENTACIÓN TOTAL AL SAG =====
        F_alimentacion_total = F_chancado + F_sobre_tamano
        
        # ===== PASO 4: ESTADO ACTUAL DEL SAG =====
        M_sag = self.estado['M_sag']
        W_sag = self.estado['W_sag']
        M_cu_sag = self.estado['M_cu_sag']
        
        if M_sag > 0.001:
            L_sag = M_cu_sag / M_sag
            H_sag = W_sag / (M_sag + W_sag)
        else:
            L_sag = L_chancado
            H_sag = self.params['humedad_sag']
        
        # ===== PASO 5: BALANCE DE AGUA =====
        W_chancado = F_chancado * (self.params['humedad_alimentacion'] / 
                                   (1 - self.params['humedad_alimentacion']))
        
        W_recirculacion = F_sobre_tamano * (self.params['humedad_recirculacion'] / 
                                           (1 - self.params['humedad_recirculacion']))
        
        if F_alimentacion_total > 0:
            L_alimentacion_total = (L_chancado * F_chancado + 
                                   L_sag * F_sobre_tamano) / F_alimentacion_total
        else:
            L_alimentacion_total = L_chancado
        
        agua_necesaria = F_alimentacion_total * (self.params['humedad_sag'] / 
                                                (1 - self.params['humedad_sag']))
        agua_disponible = W_chancado + W_recirculacion
        W_adicional = max(0, agua_necesaria - agua_disponible)
        
        # ===== PASO 6: DESCARGA DEL SAG =====
        F_descarga = self.params['k_descarga'] * M_sag
        
        # ===== PASO 7: FINOS (con arranque gradual) =====
        F_finos = self.calcular_finos(F_descarga, F_sobre_tamano)
        
        # ===== PASO 8: AGUA EN DESCARGA =====
        W_descarga = F_descarga * (H_sag / (1 - H_sag)) if H_sag < 1.0 else 0
        
        # ===== PASO 9: ECUACIONES DIFERENCIALES =====
        dM_dt = F_alimentacion_total - F_descarga
        dW_dt = W_chancado + W_recirculacion + W_adicional - W_descarga
        dMcu_dt = L_alimentacion_total * F_alimentacion_total - L_sag * F_descarga
        
        # ===== PASO 10: INTEGRACIÓN =====
        self.estado['M_sag'] += dM_dt * self.dt
        self.estado['W_sag'] += dW_dt * self.dt
        self.estado['M_cu_sag'] += dMcu_dt * self.dt
        
        self.estado['M_sag'] = max(10.0, self.estado['M_sag'])
        self.estado['W_sag'] = max(1.0, self.estado['W_sag'])
        self.estado['M_cu_sag'] = max(0.0, self.estado['M_cu_sag'])
        
        # ===== PASO 11: ACTUALIZAR TIEMPO =====
        self.estado['t'] += self.dt
        self.estado['H_sag'] = H_sag
        
        # ===== PASO 12: GUARDAR HISTORIAL =====
        if int(self.estado['t'] / self.dt) % 6 == 0:
            max_puntos = 24 * 60
            
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
            'F_alimentacion_total': F_alimentacion_total,
            'F_descarga': F_descarga,
            'L_sag': L_sag,
            'H_sag': H_sag
        }
    
    def actualizar_objetivo(self, tipo, valor):
        """Actualiza objetivos de operación"""
        if tipo == 'F':
            self.objetivos['F_target'] = valor
        elif tipo == 'L':
            self.objetivos['L_target'] = valor
    
    def reset(self):
        """Reinicia la simulación"""
        params = self.params.copy()
        self.__init__(params)
    
    def obtener_estado(self):
        """Retorna estado actual"""
        return self.estado.copy()
    
    def obtener_historial(self):
        """Retorna historial completo"""
        return {k: v.copy() for k, v in self.historial.items()}


def crear_parametros_default():
    """Parámetros por defecto"""
    return {
        'F_nominal': 2000.0,
        'L_nominal': 0.0072,
        'fraccion_recirculacion': 0.11,
        'humedad_alimentacion': 0.035,
        'humedad_sag': 0.30,
        'humedad_recirculacion': 0.08,
        'k_descarga': 0.5,
        'tau_recirculacion': 90,
        'tau_finos': 48
    }
