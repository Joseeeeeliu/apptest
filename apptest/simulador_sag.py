"""
SIMULADOR SAG EN TIEMPO REAL - VERSIÓN ESTABLE Y CORREGIDA
Clase principal con unidades consistentes y cálculo correcto
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
            't': 0.0,                    # Tiempo actual (horas)
            'M_sag': 100.0,              # Masa de sólidos en SAG (ton)
            'W_sag': 42.86,              # Masa de agua en SAG (ton) - para 30% humedad
            'M_cu_sag': 0.72,            # Masa de cobre en SAG (ton) - 0.72% de 100 ton
            'F_actual': 0.0,             # Flujo actual de alimentación (t/h)
            'L_actual': params['L_nominal'],  # Ley actual (decimal)
            'H_sag': params['humedad_sag']    # Humedad actual (decimal)
        }
        
        # Objetivos de operación
        self.objetivos = {
            'F_target': params['F_nominal'],  # Objetivo de flujo (t/h)
            'L_target': params['L_nominal']   # Objetivo de ley (decimal)
        }
        
        # Buffers para retardos (usando deque para eficiencia)
        self.buffer_F = deque(maxlen=10000)  # Historial de flujos
        self.buffer_t = deque(maxlen=10000)  # Historial de tiempos
        
        # Inicializar buffers con valores iniciales
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
        self.dt = 1/60.0  # Paso de tiempo: 1 minuto en horas
        self.semilla_aleatoria = np.random.randint(1, 10000)
        
        # Para seguimiento de estabilidad
        self.dM_dt_prev = 0.0
    
    def calcular_alimentacion(self, dt):
        """
        Calcula la alimentación dinámica que persigue el objetivo con variabilidad
        
        Args:
            dt: Paso de tiempo en horas
            
        Returns:
            tuple: (F_chancado, L_chancado) en t/h y decimal
        """
        # Parámetros de dinámica
        tau_F = 0.5  # 0.5 horas para cambios de flujo
        tau_L = 2.0  # 2.0 horas para cambios de ley (más lento)
        
        # 1. DINÁMICA DE FLUJO (Primer Orden)
        dF_dt = (self.objetivos['F_target'] - self.estado['F_actual']) / tau_F
        F_nuevo = self.estado['F_actual'] + dF_dt * dt
        
        # 2. DINÁMICA DE LEY (Primer Orden)
        dL_dt = (self.objetivos['L_target'] - self.estado['L_actual']) / tau_L
        L_nuevo = self.estado['L_actual'] + dL_dt * dt
        
        # 3. VARIABILIDAD (solo después de 2 horas)
        if self.estado['t'] > 2.0:
            # Componentes de variabilidad (controladas)
            variacion_F = 0.01 * np.sin(0.3 * self.estado['t']) + 0.005 * np.sin(0.7 * self.estado['t'] + 1)
            variacion_L = 0.005 * np.sin(0.5 * self.estado['t'] + 1.5)
            
            # Perturbaciones aleatorias ocasionales (menos frecuentes)
            if np.random.random() < 0.0005:  # 0.05% de probabilidad
                perturbacion = np.random.uniform(-0.02, 0.02)
                variacion_F += perturbacion
            
            F_nuevo *= (1 + variacion_F)
            L_nuevo *= (1 + variacion_L)
        
        # 4. LÍMITES FÍSICOS
        F_nuevo = np.clip(F_nuevo, 
                         0.1 * self.objetivos['F_target'], 
                         1.2 * self.objetivos['F_target'])
        
        L_nuevo = np.clip(L_nuevo, 
                         0.8 * self.objetivos['L_target'], 
                         1.2 * self.objetivos['L_target'])
        
        return F_nuevo, L_nuevo
    
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
        tau_rec_horas = self.params['tau_recirculacion'] / 60.0  # convertir minutos a horas
        
        # Buscar valor en el pasado
        tiempo_pasado = self.estado['t'] - tau_rec_horas
        
        if len(self.buffer_t) > 0 and tiempo_pasado > 0:
            # Buscar índice del tiempo más cercano
            diferencias = [abs(t - tiempo_pasado) for t in self.buffer_t]
            idx_min = diferencias.index(min(diferencias))
            
            # Obtener flujo de ese momento
            if idx_min < len(self.buffer_F):
                F_pasado = list(self.buffer_F)[idx_min]
                return self.params['fraccion_recirculacion'] * F_pasado
        
        return 0.0  # Si no hay datos suficientes
    
    def calcular_finos(self, F_descarga, F_sobre_tamano):
        """
        Calcula producción de finos con retardo y dinámica
        
        Args:
            F_descarga: Flujo de descarga del SAG (t/h)
            F_sobre_tamano: Flujo de sobretamaño (t/h)
            
        Returns:
            float: Flujo de finos (t/h)
        """
        # Verificar si ha pasado suficiente tiempo
        tau_finos_horas = self.params['tau_finos'] / 60.0  # convertir minutos a horas
        
        if self.estado['t'] < tau_finos_horas:
            return 0.0
        
        # Cálculo básico
        F_finos = F_descarga - F_sobre_tamano
        
        # Dinámica de arranque (crecimiento gradual)
        if self.estado['t'] < tau_finos_horas + 1.0:  # 1 hora después
            factor = 1 - np.exp(-(self.estado['t'] - tau_finos_horas) / 0.3)
            F_finos *= factor
        
        # No permitir valores negativos
        return max(0.0, F_finos)
    
    def paso_simulacion(self):
        """
        Ejecuta UN PASO de simulación usando Euler Explícito con unidades correctas
        
        Returns:
            dict: Estado actual del sistema
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
        
        # 5. CÁLCULO DE FLUJOS DE AGUA (t/h)
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
        
        # 8. DESCARGA DEL SAG (CORREGIDO - t/h)
        # k_descarga está en 1/hora, M_sag en ton → F_descarga en t/h
        F_descarga = self.params['k_descarga'] * M_sag
        
        # 9. FINOS
        F_finos = self.calcular_finos(F_descarga, F_sobre_tamano)
        
        # 10. AGUA EN DESCARGA (t/h)
        W_descarga = F_descarga * (H_sag / (1 - H_sag))
        
        # 11. ECUACIONES DIFERENCIALES (CORREGIDAS - TODO en t/h)
        # dt está en horas, así que NO hay que dividir por 60
        dM_dt = F_alimentacion_total - F_descarga  # t/h
        
        # Filtro de suavizado para estabilidad
        alpha = 0.3  # Coeficiente de filtrado
        dM_dt_filtrado = alpha * dM_dt + (1 - alpha) * self.dM_dt_prev
        self.dM_dt_prev = dM_dt_filtrado
        
        dW_dt = (W_chancado + W_recirculacion + W_adicional - W_descarga)  # t/h
        dMcu_dt = (L_alimentacion_total * F_alimentacion_total - 
                  L_sag * F_descarga)  # t_cu/h
        
        # 12. INTEGRACIÓN CON LÍMITES DE ESTABILIDAD (Euler explícito)
        # Limitar cambio máximo por paso (5% de la masa actual)
        cambio_M = dM_dt_filtrado * self.dt
        cambio_max = 0.05 * abs(M_sag) if M_sag > 10 else 5.0
        cambio_M = np.clip(cambio_M, -cambio_max, cambio_max)
        
        self.estado['M_sag'] += cambio_M
        self.estado['W_sag'] += dW_dt * self.dt
        self.estado['M_cu_sag'] += dMcu_dt * self.dt
        
        # 13. ACTUALIZAR TIEMPO Y ESTADO
        self.estado['t'] += self.dt
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
        self.estado['H_sag'] = H_sag
        
        # 14. GUARDAR EN HISTORIAL (cada 6 pasos = ~10 segundos reales)
        if int(self.estado['t'] / self.dt) % 6 == 0:
            # Limitar tamaño del historial (últimas 24 horas)
            max_puntos = 24 * 60  # 1 punto por minuto durante 24 horas
            
            # Guardar todos los valores
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
        
        # 15. RETORNAR ESTADO ACTUAL
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
        'F_nominal': 2000.0,          # Flujo nominal (t/h) - simplificado
        'L_nominal': 0.0072,          # Ley nominal (0.72%)
        'fraccion_recirculacion': 0.11,  # 11% de recirculación
        'humedad_alimentacion': 0.035,   # 3.5% humedad alimentación
        'humedad_sag': 0.30,          # 30% humedad SAG
        'humedad_recirculacion': 0.08,   # 8% humedad recirculación
        'k_descarga': 0.5,            # Constante de descarga (1/h) - ajustado para estabilidad
        'tau_recirculacion': 90,      # Retardo recirculación (minutos)
        'tau_finos': 48               # Retardo finos (minutos)
    }
