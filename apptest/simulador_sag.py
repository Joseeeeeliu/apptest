"""
SIMULADOR SAG EN TIEMPO REAL - VERSIÓN SIMPLIFICADA Y ESTABLE
Chancado con variaciones senoidales simples - Sin acumulación
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
        Calcula el flujo y ley de CHANCADO con variaciones senoidales simples
        
        FILOSOFÍA: Simple y efectivo
        - Converge al objetivo con dinámica de primer orden
        - Variaciones = ondas senoidales + ruido blanco pequeño
        - NO hay acumulación, todo se aplica directamente
        
        Args:
            dt: Paso de tiempo en horas
            
        Returns:
            tuple: (F_chancado, L_chancado) en t/h y decimal
        """
        
        # ========== FLUJO DE CHANCADO ==========
        
        # 1. Dinámica de primer orden hacia el objetivo
        tau_F = 1.0  # Constante de tiempo: 1 hora
        F_base = self.estado['F_actual'] + (self.objetivos['F_target'] - self.estado['F_actual']) / tau_F * dt
        
        # 2. Variaciones senoidales (aplicadas directamente, NO acumuladas)
        t = self.estado['t']
        
        # Ondas de diferentes frecuencias y amplitudes
        onda1 = 0.03 * np.sin(0.2 * t)              # Periodo ~31h, amplitud 3%
        onda2 = 0.02 * np.sin(0.5 * t + 1.2)        # Periodo ~13h, amplitud 2%
        onda3 = 0.015 * np.sin(1.1 * t + 2.5)       # Periodo ~6h, amplitud 1.5%
        
        # Ruido blanco (pequeño)
        ruido = np.random.normal(0, 0.005)          # Desviación estándar 0.5%
        
        # Suma de variaciones (en términos porcentuales)
        variacion_total = onda1 + onda2 + onda3 + ruido
        
        # 3. Aplicar variaciones al flujo objetivo (no al actual)
        F_chancado = F_base * (1 + variacion_total)
        
        # 4. Límites ABSOLUTOS (independientes del objetivo)
        F_min = 0.5 * self.params['F_nominal']  # 1000 t/h
        F_max = 1.5 * self.params['F_nominal']  # 3000 t/h
        F_chancado = np.clip(F_chancado, F_min, F_max)
        
        
        # ========== LEY DE CHANCADO ==========
        
        # 1. Dinámica de primer orden hacia el objetivo
        tau_L = 1.0  # Constante de tiempo: 1 hora
        L_base = self.estado['L_actual'] + (self.objetivos['L_target'] - self.estado['L_actual']) / tau_L * dt
        
        # 2. Variaciones senoidales (diferentes frecuencias que el flujo)
        onda_L1 = 0.025 * np.sin(0.4 * t + 0.8)     # Periodo ~16h, amplitud 2.5%
        onda_L2 = 0.015 * np.sin(0.9 * t + 1.5)     # Periodo ~7h, amplitud 1.5%
        onda_L3 = 0.01 * np.sin(1.3 * t + 3.0)      # Periodo ~5h, amplitud 1%
        
        # Ruido blanco
        ruido_L = np.random.normal(0, 0.004)        # Desviación estándar 0.4%
        
        variacion_L_total = onda_L1 + onda_L2 + onda_L3 + ruido_L
        
        # 3. Aplicar variaciones
        L_chancado = L_base * (1 + variacion_L_total)
        
        # 4. Límites ABSOLUTOS
        L_min = 0.5 * self.params['L_nominal']
        L_max = 1.5 * self.params['L_nominal']
        L_chancado = np.clip(L_chancado, L_min, L_max)
        
        return F_chancado, L_chancado
    
    def calcular_recirculacion(self, F_chancado_actual):
        """
        Calcula la recirculación con retardo de tiempo
        
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
        tiempo_pasado = self.estado['t'] - tau_rec_horas
        
        if len(self.buffer_t) > 0 and tiempo_pasado > 0:
            # Buscar índice del tiempo más cercano
            diferencias = [abs(t - tiempo_pasado) for t in self.buffer_t]
            idx_min = diferencias.index(min(diferencias))
            
            if idx_min < len(self.buffer_F):
                F_pasado = list(self.buffer_F)[idx_min]
                return self.params['fraccion_recirculacion'] * F_pasado
        
        # Arranque suave si no hay suficiente historia
        factor_arranque = min(1.0, self.estado['t'] / tau_rec_horas)
        return self.params['fraccion_recirculacion'] * F_chancado_actual * factor_arranque
    
    def calcular_finos(self, F_descarga, F_sobre_tamano):
        """
        Calcula producción de finos con retardo y dinámica
        
        Args:
            F_descarga: Flujo de descarga del SAG (t/h)
            F_sobre_tamano: Flujo de sobretamaño (t/h)
            
        Returns:
            float: Flujo de finos (t/h)
        """
        tau_finos_horas = self.params['tau_finos'] / 60.0
        
        # Cálculo básico
        F_finos = F_descarga - F_sobre_tamano
        
        # Arranque gradual
        if self.estado['t'] < tau_finos_horas:
            factor = self.estado['t'] / tau_finos_horas
            F_finos *= factor
        elif self.estado['t'] < tau_finos_horas + 1.0:
            # Transición suave
            t_trans = self.estado['t'] - tau_finos_horas
            factor = 1 - 0.3 * np.exp(-t_trans / 0.3)
            F_finos *= factor
        
        return max(0.0, F_finos)
    
    def paso_simulacion(self):
        """
        Ejecuta UN PASO de simulación
        
        ORDEN DE CAUSALIDAD:
        1. Chancado (INDEPENDIENTE)
        2. Recirculación (depende de chancado pasado)
        3. Balance SAG (depende de chancado + recirculación)
        4. Descarga (depende de masa SAG)
        5. Finos (depende de descarga)
        
        Returns:
            dict: Estado actual del sistema
        """
        
        # ===== PASO 1: CHANCADO (EXÓGENO) =====
        F_chancado, L_chancado = self.calcular_alimentacion_chancado(self.dt)
        
        # ===== PASO 2: RECIRCULACIÓN (RETARDADA) =====
        F_sobre_tamano = self.calcular_recirculacion(F_chancado)
        
        # ===== PASO 3: ALIMENTACIÓN TOTAL AL SAG =====
        F_alimentacion_total = F_chancado + F_sobre_tamano
        
        # ===== PASO 4: ESTADO ACTUAL DEL SAG =====
        M_sag = self.estado['M_sag']
        W_sag = self.estado['W_sag']
        M_cu_sag = self.estado['M_cu_sag']
        
        # Calcular propiedades
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
        
        # Ley combinada de alimentación
        if F_alimentacion_total > 0:
            L_alimentacion_total = (L_chancado * F_chancado + 
                                   L_sag * F_sobre_tamano) / F_alimentacion_total
        else:
            L_alimentacion_total = L_chancado
        
        # Agua adicional necesaria
        agua_necesaria = F_alimentacion_total * (self.params['humedad_sag'] / 
                                                (1 - self.params['humedad_sag']))
        agua_disponible = W_chancado + W_recirculacion
        W_adicional = max(0, agua_necesaria - agua_disponible)
        
        # ===== PASO 6: DESCARGA DEL SAG =====
        F_descarga = self.params['k_descarga'] * M_sag
        
        # ===== PASO 7: FINOS =====
        F_finos = self.calcular_finos(F_descarga, F_sobre_tamano)
        
        # ===== PASO 8: AGUA EN DESCARGA =====
        W_descarga = F_descarga * (H_sag / (1 - H_sag)) if H_sag < 1.0 else 0
        
        # ===== PASO 9: ECUACIONES DIFERENCIALES =====
        dM_dt = F_alimentacion_total - F_descarga
        dW_dt = W_chancado + W_recirculacion + W_adicional - W_descarga
        dMcu_dt = L_alimentacion_total * F_alimentacion_total - L_sag * F_descarga
        
        # ===== PASO 10: INTEGRACIÓN CON LÍMITES =====
        # Limitar cambio máximo (2% por paso para estabilidad)
        max_cambio_M = 0.02 * max(abs(M_sag), 10.0)
        max_cambio_W = 0.02 * max(abs(W_sag), 5.0)
        max_cambio_Mcu = 0.02 * max(abs(M_cu_sag), 0.1)
        
        cambio_M = np.clip(dM_dt * self.dt, -max_cambio_M, max_cambio_M)
        cambio_W = np.clip(dW_dt * self.dt, -max_cambio_W, max_cambio_W)
        cambio_Mcu = np.clip(dMcu_dt * self.dt, -max_cambio_Mcu, max_cambio_Mcu)
        
        # Aplicar cambios con límites físicos
        self.estado['M_sag'] = max(10.0, self.estado['M_sag'] + cambio_M)
        self.estado['W_sag'] = max(1.0, self.estado['W_sag'] + cambio_W)
        self.estado['M_cu_sag'] = max(0.0, self.estado['M_cu_sag'] + cambio_Mcu)
        
        # ===== PASO 11: ACTUALIZAR ESTADO =====
        self.estado['t'] += self.dt
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
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
            
            # Mantener tamaño manejable
            for key in self.historial:
                if len(self.historial[key]) > max_puntos:
                    self.historial[key] = self.historial[key][-max_puntos:]
        
        # ===== RETORNAR ESTADO =====
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
        """
        Método para cambiar objetivos desde la interfaz
        
        Args:
            tipo: 'F' para flujo, 'L' para ley
            valor: nuevo valor objetivo
        """
        if tipo == 'F':
            self.objetivos['F_target'] = valor
        elif tipo == 'L':
            self.objetivos['L_target'] = valor
        else:
            raise ValueError(f"Tipo '{tipo}' no reconocido. Use 'F' o 'L'.")
    
    def reset(self):
        """Reinicia la simulación a condiciones iniciales"""
        params = self.params.copy()
        self.__init__(params)
    
    def obtener_estado(self):
        """Retorna una copia del estado actual"""
        return self.estado.copy()
    
    def obtener_historial(self):
        """Retorna una copia del historial completo"""
        return {k: v.copy() for k, v in self.historial.items()}


# ================= FUNCIÓN AUXILIAR =================

def crear_parametros_default():
    """
    Retorna diccionario con parámetros por defecto para el SAG
    
    Returns:
        dict: Parámetros por defecto
    """
    return {
        'F_nominal': 2000.0,          # Flujo nominal (t/h)
        'L_nominal': 0.0072,          # Ley nominal (0.72%)
        'fraccion_recirculacion': 0.11,  # 11% de recirculación
        'humedad_alimentacion': 0.035,   # 3.5% humedad alimentación
        'humedad_sag': 0.30,          # 30% humedad SAG
        'humedad_recirculacion': 0.08,   # 8% humedad recirculación
        'k_descarga': 0.5,            # Constante de descarga (1/h)
        'tau_recirculacion': 90,      # Retardo recirculación (minutos)
        'tau_finos': 48               # Retardo finos (minutos)
    }
