"""
SIMULADOR SAG EN TIEMPO REAL - VERSIÓN CORREGIDA
Corrección de unidades y estabilidad
"""

import numpy as np
from collections import deque

class SimuladorSAG:
    def __init__(self, params):
        self.params = params.copy()
        
        # Estado inicial CORREGIDO
        self.estado = {
            't': 0.0,
            'M_sag': 100.0,           # ton
            'W_sag': 42.86,           # ton (para 30% humedad)
            'M_cu_sag': 0.72,         # ton (0.72% de 100 ton)
            'F_actual': 0.0,          # t/h
            'L_actual': params['L_nominal'],
            'H_sag': params['humedad_sag']
        }
        
        # Objetivos
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
        
        # Historial
        self.historial = {
            't': [], 'M_sag': [], 'W_sag': [], 'M_cu_sag': [],
            'F_chancado': [], 'L_chancado': [], 'F_finos': [],
            'F_sobre_tamano': [], 'F_target': [], 'L_target': [],
            'F_descarga': [], 'L_sag': [], 'H_sag': []
        }
        
        # Control
        self.dt = 1/60.0  # 1 minuto en horas
        self.semilla_aleatoria = np.random.randint(1, 10000)
    
    # ... (mantén el resto de métodos como están PERO corrige paso_simulacion) ...
    
    def paso_simulacion(self):
        """VERSIÓN CORREGIDA - Unidades consistentes"""
        # 1. Calcular alimentación (tu método actual)
        F_chancado, L_chancado = self.calcular_alimentacion(self.dt)
        
        # 2. Recirculación
        F_sobre_tamano = self.calcular_recirculacion(F_chancado)
        
        # 3. Alimentación total
        F_alimentacion_total = F_chancado + F_sobre_tamano
        
        # 4. Propiedades actuales
        M_sag = self.estado['M_sag']
        W_sag = self.estado['W_sag']
        M_cu_sag = self.estado['M_cu_sag']
        
        if M_sag > 0.001:
            L_sag = M_cu_sag / M_sag
            H_sag = W_sag / (M_sag + W_sag)
        else:
            L_sag = L_chancado
            H_sag = self.params['humedad_sag']
        
        # 5. Flujos de agua (t/h)
        W_chancado = F_chancado * (self.params['humedad_alimentacion'] / 
                                  (1 - self.params['humedad_alimentacion']))
        W_recirculacion = F_sobre_tamano * (self.params['humedad_recirculacion'] / 
                                          (1 - self.params['humedad_recirculacion']))
        
        # 6. Ley combinada
        if F_alimentacion_total > 0:
            L_alimentacion_total = (L_chancado * F_chancado + L_sag * F_sobre_tamano) / F_alimentacion_total
        else:
            L_alimentacion_total = 0
        
        # 7. Agua adicional
        agua_necesaria = F_alimentacion_total * (self.params['humedad_sag'] / 
                                               (1 - self.params['humedad_sag']))
        agua_disponible = W_chancado + W_recirculacion
        W_adicional = max(0, agua_necesaria - agua_disponible)
        
        # 8. DESCARGA CORREGIDA (t/h) - ¡NO dividas k por 60!
        F_descarga = self.params['k_descarga'] * M_sag  # t/h
        
        # 9. Finos
        F_finos = self.calcular_finos(F_descarga, F_sobre_tamano)
        
        # 10. Agua en descarga
        W_descarga = F_descarga * (H_sag / (1 - H_sag))
        
        # 11. ECUACIONES DIFERENCIALES CORREGIDAS
        # TODO está en t/h, dt está en horas → NO dividas por 60
        dM_dt = F_alimentacion_total - F_descarga  # t/h
        dW_dt = (W_chancado + W_recirculacion + W_adicional - W_descarga)  # t/h
        dMcu_dt = (L_alimentacion_total * F_alimentacion_total - L_sag * F_descarga)  # t_cu/h
        
        # 12. INTEGRACIÓN (dt ya está en horas)
        self.estado['M_sag'] += dM_dt * self.dt
        self.estado['W_sag'] += dW_dt * self.dt
        self.estado['M_cu_sag'] += dMcu_dt * self.dt
        self.estado['t'] += self.dt
        self.estado['F_actual'] = F_chancado
        self.estado['L_actual'] = L_chancado
        self.estado['H_sag'] = H_sag
        
        # 13. Guardar historial
        if int(self.estado['t'] / self.dt) % 10 == 0:
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
            'H_sag': H_sag
        }
    
    # ... (mantén los otros métodos tal como están) ...
