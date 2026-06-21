import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

class MotorDifusoMamdani:
    def __init__(self):
        """
        Inicializa el motor de Inferencia Difusa (Mamdani).
        Configura los universos de discurso (escalas numéricas) y las funciones de pertenencia.
        """
        # 1. DEFINICIÓN DE ANTECEDENTES (Entradas) - Escalas de 0 a 10
        self.uso = ctrl.Antecedent(np.arange(0, 11, 1), 'uso')
        self.anomalia = ctrl.Antecedent(np.arange(0, 11, 1), 'anomalia')
        self.integridad = ctrl.Antecedent(np.arange(0, 11, 1), 'integridad')

        # 2. DEFINICIÓN DEL CONSECUENTE (Salida) - Índice de Salud de 0 a 100%
        self.salud = ctrl.Consequent(np.arange(0, 101, 1), 'salud')

        # 3. FUZZIFICACIÓN: Funciones de Pertenencia (Geometría Triangular)
        # Mapeamos los conceptos lingüísticos a grados de verdad (0.0 a 1.0)
        self.uso.automf(3, names=['bajo', 'medio', 'alto'])
        self.anomalia.automf(3, names=['ninguna', 'moderada', 'severa'])
        
        # Ojo: Para Integridad, 0 es peligro (malo) y 10 es intacta (bueno)
        self.integridad.automf(3, names=['peligro', 'desgaste', 'intacta'])

        # Funciones de pertenencia personalizadas para el porcentaje de salud
        self.salud['critica'] = fuzz.trimf(self.salud.universe, [0, 0, 40])       # Riesgo inminente <= 40%
        self.salud['alerta'] = fuzz.trimf(self.salud.universe, [30, 50, 70])      # Requiere mantenimiento
        self.salud['optima'] = fuzz.trimf(self.salud.universe, [60, 100, 100])    # Operativo seguro

        # 4. BASE DE CONOCIMIENTOS (Reglas Mamdani)
        # Estas reglas operan con álgebra booleana difusa (Operador Mínimo para AND '&', Máximo para OR '|')
        regla1 = ctrl.Rule(self.anomalia['severa'] | self.integridad['peligro'], self.salud['critica'])
        regla2 = ctrl.Rule(self.uso['alto'] & self.anomalia['moderada'], self.salud['critica'])
        regla3 = ctrl.Rule(self.uso['medio'] & self.integridad['desgaste'], self.salud['alerta'])
        regla4 = ctrl.Rule(self.anomalia['ninguna'] & self.integridad['intacta'], self.salud['optima'])
        regla5 = ctrl.Rule(self.uso['bajo'] & self.anomalia['ninguna'], self.salud['optima'])
        regla6 = ctrl.Rule(self.anomalia['moderada'] & self.integridad['intacta'], self.salud['alerta'])

        # 5. CONSTRUCCIÓN DEL SISTEMA DE CONTROL
        sistema_control = ctrl.ControlSystem([regla1, regla2, regla3, regla4, regla5, regla6])
        self.simulador = ctrl.ControlSystemSimulation(sistema_control)

    def procesar_diagnostico_predictivo(self, val_uso: float, val_anomalia: float, val_integridad: float) -> dict:
        """
        Método público que recibe los valores crudos, ejecuta la defuzzificación (Centroide) 
        y retorna el porcentaje exacto y si amerita bloqueo preventivo.
        """
        try:
            # Inyectar valores al simulador
            self.simulador.input['uso'] = val_uso
            self.simulador.input['anomalia'] = val_anomalia
            self.simulador.input['integridad'] = val_integridad

            # Ejecutar el cálculo integral matemático
            self.simulador.compute()

            # Extraer el resultado escalar (Defuzzificación por Centroide)
            resultado_pct = round(self.simulador.output['salud'], 2)

            # Regla de Negocio BR-05: Bloqueo Automático
            bloqueo = True if resultado_pct <= 40.0 else False

            return {
                "indice_salud_pct": resultado_pct,
                "alerta_bloqueo": bloqueo,
                "estado_recomendado": "INOPERATIVO (BLOQUEADO)" if bloqueo else "OPERATIVO",
                "mensaje": "El motor difuso procesó las variables exitosamente."
            }
        
        except Exception as e:
            return {"error": str(e)}

# Instancia global para ser importada en los controladores de FastAPI
motor_ia = MotorDifusoMamdani()