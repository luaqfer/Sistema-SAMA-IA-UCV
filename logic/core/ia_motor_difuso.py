import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

class MotorDifusoMamdani:
    def __init__(self):
        """
        Inicializa el motor de Inferencia Difusa (Mamdani).
        Configura los universos de discurso (escalas numéricas) y las funciones de pertenencia.
        """
        # 1. DEFINICIÓN DE ANTECEDENTES (Entradas)
        self.uso = ctrl.Antecedent(np.arange(0, 11, 1), 'uso')
        self.anomalia = ctrl.Antecedent(np.arange(0, 11, 1), 'anomalia')
        self.integridad = ctrl.Antecedent(np.arange(0, 11, 1), 'integridad')
        self.temperatura = ctrl.Antecedent(np.arange(0, 11, 1), 'temperatura')
        self.fugas = ctrl.Antecedent(np.arange(0, 11, 1), 'fugas')
        
        # Historial y Contabilidad
        self.fallas_previas = ctrl.Antecedent(np.arange(0, 11, 1), 'fallas_previas') # Bloqueos en 30 dias
        self.edad_operativa = ctrl.Antecedent(np.arange(0, 51, 1), 'edad_operativa') # Años

        # 2. DEFINICIÓN DEL CONSECUENTE (Salida)
        self.salud = ctrl.Consequent(np.arange(0, 101, 1), 'salud')

        # 3. FUZZIFICACIÓN: Funciones de Pertenencia
        self.uso.automf(3, names=['bajo', 'medio', 'alto'])
        self.anomalia.automf(3, names=['ninguna', 'moderada', 'severa'])
        self.integridad.automf(3, names=['peligro', 'desgaste', 'intacta']) # Ojo: Invertido
        self.temperatura.automf(3, names=['normal', 'tibia', 'critica'])
        self.fugas.automf(3, names=['ninguna', 'leve', 'grave'])
        
        self.fallas_previas.automf(3, names=['nulas', 'esporadicas', 'cronicas'])
        
        # Edad (Trimf manual)
        self.edad_operativa['nueva'] = fuzz.trimf(self.edad_operativa.universe, [0, 0, 5])
        self.edad_operativa['madura'] = fuzz.trimf(self.edad_operativa.universe, [3, 10, 20])
        self.edad_operativa['obsoleta'] = fuzz.trimf(self.edad_operativa.universe, [15, 50, 50])

        self.salud['critica'] = fuzz.trimf(self.salud.universe, [0, 0, 40])
        self.salud['alerta'] = fuzz.trimf(self.salud.universe, [30, 50, 70])
        self.salud['optima'] = fuzz.trimf(self.salud.universe, [60, 100, 100])

        # 4. BASE DE CONOCIMIENTOS (Reglas Mamdani)
        reglas = []
        
        # Reglas Óptimas (Camino feliz)
        reglas.append(ctrl.Rule(self.anomalia['ninguna'] & self.integridad['intacta'] & self.fugas['ninguna'] & self.temperatura['normal'], self.salud['optima']))
        
        # Reglas Críticas Indiscutibles (Cualquier factor mortal)
        reglas.append(ctrl.Rule(self.integridad['peligro'], self.salud['critica']))
        reglas.append(ctrl.Rule(self.temperatura['critica'], self.salud['critica']))
        reglas.append(ctrl.Rule(self.fugas['grave'], self.salud['critica']))
        reglas.append(ctrl.Rule(self.fallas_previas['cronicas'], self.salud['critica']))
        
        # Combinación de factores moderados que llevan a Crítica
        reglas.append(ctrl.Rule(self.edad_operativa['obsoleta'] & self.anomalia['severa'], self.salud['critica']))
        reglas.append(ctrl.Rule(self.edad_operativa['obsoleta'] & self.fugas['leve'], self.salud['alerta']))
        reglas.append(ctrl.Rule(self.fallas_previas['esporadicas'] & self.temperatura['tibia'], self.salud['alerta']))
        
        # Reglas de Alerta (Desgastes y advertencias)
        reglas.append(ctrl.Rule(self.uso['alto'] & self.anomalia['moderada'], self.salud['alerta']))
        reglas.append(ctrl.Rule(self.integridad['desgaste'], self.salud['alerta']))
        reglas.append(ctrl.Rule(self.uso['bajo'] & self.anomalia['ninguna'] & self.edad_operativa['madura'], self.salud['optima']))

        # 5. CONSTRUCCIÓN DEL SISTEMA DE CONTROL
        sistema_control = ctrl.ControlSystem(reglas)
        self.simulador = ctrl.ControlSystemSimulation(sistema_control)

    def procesar_diagnostico_predictivo(self, val_uso: float, val_anomalia: float, val_integridad: float, val_temperatura: float, val_fugas: float, val_fallas_previas: float, val_edad: float) -> dict:
        try:
            # Inyectar valores al simulador
            self.simulador.input['uso'] = val_uso
            self.simulador.input['anomalia'] = val_anomalia
            self.simulador.input['integridad'] = val_integridad
            self.simulador.input['temperatura'] = val_temperatura
            self.simulador.input['fugas'] = val_fugas
            self.simulador.input['fallas_previas'] = val_fallas_previas
            self.simulador.input['edad_operativa'] = val_edad

            # Ejecutar el cálculo integral matemático
            self.simulador.compute()

            # Extraer el resultado escalar (Defuzzificación por Centroide)
            resultado_pct = round(self.simulador.output['salud'], 2)

            # Reglas de Negocio para el Estado Recomendado
            bloqueo = True if resultado_pct <= 40.0 else False
            
            if resultado_pct <= 40.0:
                estado_recomendado = "INOPERATIVO (BLOQUEADO)"
            elif resultado_pct <= 70.0:
                estado_recomendado = "EN OBSERVACION"
            else:
                estado_recomendado = "OPERATIVO"

            return {
                "indice_salud_pct": resultado_pct,
                "alerta_bloqueo": bloqueo,
                "estado_recomendado": estado_recomendado,
                "mensaje": f"Evaluado. El activo debe pasar a {estado_recomendado}."
            }
        
        except Exception as e:
            return {"error": str(e)}

# Instancia global para ser importada en los controladores de FastAPI
motor_ia = MotorDifusoMamdani()