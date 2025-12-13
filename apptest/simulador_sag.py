"""
SIMULADOR SAG EN TIEMPO REAL - VERSIÓN CORREGIDA Y ESTABLE
Chancado con arranque suave y dinámica mejorada
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
        
        # Estado inicial del sistema - CORREGIDO
        self.estado = {
            't': 0.0,                         # Tiempo actual (horas)
            'M_sag': 100.0,                   # Masa de sólidos en SAG (ton)
            'W_sag': 42.86,                   # Masa de agua en SAG (ton)
            'M_cu_sag': 0.72,                 # Masa de cobre en SAG (ton)
            'F_actual': 0.0,                  # Flujo actual chancado (t/h) - EMPIEZA EN 0
            'L_actual': params['L_nominal'] * 0.3,  # Ley actual (30% del nominal para arranque suave)
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
        
        # Variables para arranque suave
        self.primera_ejecucion = True
    
    def calcular_alimentacion_chancado(self, dt):
        """
        Calcula el flujo y ley de CHANCADO con variaciones senoidales simples
        
        FILOSOFÍA CORREGIDA:
        - Arranque suave desde valores bajos
        - Converge al objetivo con dinámica de primer orden
        - Variaciones = ondas senoidales + ruido blanco pequeño
        - Variaciones solo después de estabilización
        
        Args:
            dt: Paso de tiempo en horas
            
        Returns:
            tuple: (F_chancado, L_chancado) en t/h y decimal
        """
        
        t = self.estado['t']
        
        # ========== FLUJO DE CHANCADO ==========
        
        # ARRANQUE SUAVE - Solo para los primeros 30 minutos
        if t < 0.5:  # 0.5 horas = 30 minutos
            # Subida suave desde 0 hasta el 50% del objetivo
            factor_arranque = min(1.0, t / 0.5)  # Lineal de 0 a 1 en 0.5 horas
            objetivo_arranque = self.objetivos['F_target'] * 0.5 * factor_arranque
            
            # Aplicar variaciones mínimas durante arranque
            ruido_arranque = np.random.normal(0, 0.002)  # Muy pequeño
            F_chancado = objetivo_arranque * (1 + ruido_arranque)
            
        else:
            # FASE DE ESTABILIZACIÓN - Después de arranque
            # Dinámica de primer orden hacia el objetivo
            tau_F = 1.0  # Constante de tiempo: 1 hora
            
            # Diferencia entre objetivo y actual
            diferencia = self.objetivos['F_target'] - self.estado['F_actual']
            
            # Cambio máximo permitido por paso (para evitar saltos bruscos)
            cambio_max = self.objetivos['F_target'] * 0.1 * dt  # Máximo 10% del objetivo por hora
            
            # Calcular cambio con limitación
            cambio = np.clip(diferencia / tau_F * dt, -cambio_max, cambio_max)
            
            F_base = self.estado['F_actual'] + cambio
            
            # VARIACIONES (solo después de 1 hora de simulación)
            if t > 1.0:
                # Ondas de diferentes frecuencias y amplitudes
                onda1 = 0.03 * np.sin(0.2 * t)              # Periodo ~31h, amplitud 3%
                onda2 = 0.02 * np.sin(0.5 * t + 1.2)        # Periodo ~13h, amplitud 2%
                onda3 = 0.015 * np.sin(1.1 * t + 2.5)       # Periodo ~6h, amplitud 1.5%
                
                # Ruido blanco (pequeño)
                ruido = np.random.normal(0, 0.005)          # Desviación estándar 0.5%
                
                # Suma de variaciones (en términos porcentuales)
                variacion_total = onda1 + onda2 + onda3 + ruido
                
                # Aplicar variaciones con factor que depende de qué tan cerca estamos del objetivo
                proximidad_al_objetivo = 1 - min(1.0, abs(diferencia) / self.objetivos['F_target'])
                variacion_total *= proximidad_al_objetivo
            else:
                variacion_total = 0
            
            # Aplicar variaciones
            F_chancado = F_base * (1 + variacion_total)
        
        # Límites ABSOLUTOS
        F_min = 500.0  # Mínimo 500 t/h
        F_max = 5000.0  # Máximo 5000 t/h
        F_chancado = np.clip(F_chancado, F_min, F_max)
        
        
        # ========== LEY DE CHANCADO ==========
        
        # ARRANQUE SUAVE para ley
        if t < 0.5:
            # Subida suave desde 30% del nominal hasta 60%
            factor_arranque_L = min(1.0, t / 0.5)
            objetivo_arranque_L = self.objetivos['L_target'] * (0.3 + 0.3 * factor_arranque_L)
            
            ruido_arranque_L = np.random.normal(0, 0.001)  # Muy pequeño
            L_chancado = objetivo_arranque_L * (1 + ruido_arranque_L)
            
        else:
            # FASE DE ESTABILIZACIÓN
            tau_L = 1.5  # Constante de tiempo: 1.5 horas (más lenta que el flujo)
            
            # Diferencia entre objetivo y actual
            diferencia_L = self.objetivos['L_target'] - self.estado['L_actual']
            
            # Cambio máximo permitido por paso
            cambio_max_L = self.objetivos['L_target'] * 0.05 * dt  # Máximo 5% del objetivo por hora
            
            # Calcular cambio con limitación
            cambio_L = np.clip(diferencia_L / tau_L * dt, -cambio_max_L, cambio_max_L)
            
            L_base = self.estado['L_actual'] + cambio_L
            
            # VARIACIONES para ley (solo después de 1.5 horas)
            if t > 1.5:
                # Ondas de diferentes frecuencias
                onda_L1 = 0.025 * np.sin(0.4 * t + 0.8)     # Periodo ~16h, amplitud 2.5%
                onda_L2 = 0.015 * np.sin(0.9 * t + 1.5)     # Periodo ~7h, amplitud 1.5%
                onda_L3 = 0.01 * np.sin(1.3 * t + 3.0)      # Periodo ~5h, amplitud 1%
                
                # Ruido blanco
                ruido_L = np.random.normal(0, 0.004)        # Desviación estándar 0.4%
                
                variacion_L_total = onda_L1 + onda_L2 + onda_L3 + ruido_L
                
                # Factor de proximidad al objetivo
                proximidad_al_objetivo_L = 1 - min(1.0, abs(diferencia_L) / self.objetivos['L_target'])
                variacion_L_total *= proximidad_al_objetivo_L
            else:
                variacion_L_total = 0
            
            # Aplicar variaciones
            L_chancado = L_base * (1 + variacion_L_total)
        
        # Límites para la ley
        L_min = 0.003  # Mínimo 0.3%
        L_max = 0.015  # Máximo 1.5%
        L_chancado = np.clip(L_chancado, L_min, L_max)
        
        # Guardar valores actuales para referencia futura
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
        
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
        self.estado['H_sag'] = H_sag
        
        # ===== PASO 12: GUARDAR HISTORIAL =====
        if int(self.estado['t'] / self.dt) % 6 == 0:  # Cada 6 minutos
            max_puntos = 24 * 60  # 24 horas de datos
            
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
        # Guardar parámetros actuales
        params = self.params.copy()
        # Crear nueva instancia con los mismos parámetros
        self.__init__(params)
        # Asegurar que los objetivos se mantengan actualizados
        self.objetivos['F_target'] = params['F_nominal']
        self.objetivos['L_target'] = params['L_nominal']
    
    def obtener_estado(self):
        """Retorna una copia del estado actual"""
        estado = self.estado.copy()
        # Añadir información adicional para la interfaz
        estado['F_actual'] = self.estado['F_actual']
        estado['L_actual'] = self.estado['L_actual']
        estado['M_sag'] = self.estado['M_sag']
        estado['W_sag'] = self.estado['W_sag']
        estado['H_sag'] = self.estado['H_sag']
        estado['t'] = self.estado['t']
        return estado
    
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
