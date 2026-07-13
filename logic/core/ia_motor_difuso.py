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

        # 4. BASE DE CONOCIMIENTOS (Reglas Mamdani por Categoría)
        self.simuladores = {}

        # CATEGORÍA 2 Y 5: MAQUINARIA INDUSTRIAL Y FLOTA
        # El recalentamiento, fatiga (integridad estructural) y fugas son inhabilitantes.
        reglas_maq = [
            # Críticas
            ctrl.Rule(self.temperatura['critica'] | self.integridad['peligro'], self.salud['critica']),
            ctrl.Rule(self.fugas['grave'] | self.fallas_previas['cronicas'], self.salud['critica']),
            ctrl.Rule(self.edad_operativa['obsoleta'] & self.anomalia['severa'], self.salud['critica']),
            # Alertas
            ctrl.Rule(self.anomalia['moderada'] & self.temperatura['tibia'], self.salud['alerta']),
            ctrl.Rule(self.integridad['desgaste'] | self.uso['alto'], self.salud['alerta']),
            # Óptimas
            ctrl.Rule(self.anomalia['ninguna'] & self.integridad['intacta'] & self.temperatura['normal'], self.salud['optima'])
        ]
        self.simuladores['maquinaria'] = ctrl.ControlSystemSimulation(ctrl.ControlSystem(reglas_maq))

        # CATEGORÍA 3: TECNOLOGÍA Y TI (Equipos de Cómputo)
        # La temperatura alta destruye equipos, fugas (agua en TI) es letal. La fatiga mecánica (integridad) es irrelevante.
        reglas_ti = [
            # Críticas
            ctrl.Rule(self.temperatura['critica'] | self.fugas['grave'], self.salud['critica']),
            ctrl.Rule(self.anomalia['severa'] & self.uso['alto'], self.salud['critica']),
            # Alertas
            ctrl.Rule(self.anomalia['moderada'] | self.temperatura['tibia'], self.salud['alerta']),
            # Óptimas
            ctrl.Rule(self.temperatura['normal'] & self.anomalia['ninguna'], self.salud['optima'])
        ]
        self.simuladores['tecnologia'] = ctrl.ControlSystemSimulation(ctrl.ControlSystem(reglas_ti))

        # CATEGORÍA 1: INMUEBLES E INFRAESTRUCTURA
        # La fatiga (integridad) es lo más crítico, la temperatura y el uso importan menos.
        reglas_inm = [
            # Críticas
            ctrl.Rule(self.integridad['peligro'], self.salud['critica']),
            ctrl.Rule(self.fugas['grave'], self.salud['critica']),
            # Alertas
            ctrl.Rule(self.integridad['desgaste'] | self.anomalia['moderada'], self.salud['alerta']),
            ctrl.Rule(self.edad_operativa['obsoleta'], self.salud['alerta']),
            # Óptimas
            ctrl.Rule(self.integridad['intacta'] & self.anomalia['ninguna'], self.salud['optima'])
        ]
        self.simuladores['inmuebles'] = ctrl.ControlSystemSimulation(ctrl.ControlSystem(reglas_inm))

        # CATEGORÍA 4 Y OTROS: MOBILIARIO
        # Desgaste físico estándar.
        reglas_mob = [
            # Críticas
            ctrl.Rule(self.anomalia['severa'] | self.integridad['peligro'], self.salud['critica']),
            # Alertas
            ctrl.Rule(self.integridad['desgaste'] | self.uso['alto'], self.salud['alerta']),
            # Óptimas
            ctrl.Rule(self.anomalia['ninguna'] & self.integridad['intacta'], self.salud['optima'])
        ]
        self.simuladores['mobiliario'] = ctrl.ControlSystemSimulation(ctrl.ControlSystem(reglas_mob))

    def procesar_diagnostico_predictivo(self, val_uso: float, val_anomalia: float, val_integridad: float, val_temperatura: float, val_fugas: float, val_fallas_previas: float, val_edad: float, id_categoria: int = 4) -> dict:
        try:
            # Seleccionar simulador por categoría
            if id_categoria in [2, 5]:
                simulador_activo = self.simuladores['maquinaria']
            elif id_categoria == 3:
                simulador_activo = self.simuladores['tecnologia']
            elif id_categoria == 1:
                simulador_activo = self.simuladores['inmuebles']
            else:
                simulador_activo = self.simuladores['mobiliario']

            # Inyectar valores al simulador seleccionado
            simulador_activo.input['uso'] = val_uso
            simulador_activo.input['anomalia'] = val_anomalia
            simulador_activo.input['integridad'] = val_integridad
            simulador_activo.input['temperatura'] = val_temperatura
            simulador_activo.input['fugas'] = val_fugas
            simulador_activo.input['fallas_previas'] = val_fallas_previas
            simulador_activo.input['edad_operativa'] = val_edad

            # Ejecutar el cálculo integral matemático
            simulador_activo.compute()

            # Extraer el resultado escalar (Defuzzificación por Centroide)
            resultado_pct = round(simulador_activo.output['salud'], 2)

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