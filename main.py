# main.py - Sistema de Riego Inteligente Hidrosmart (Versión Online/Offline)
# Autor: Gemini
# Basado en los requerimientos de la Tarea Extraclase #2

import machine
import dht
import time
import network
import urequests
import ntptime

# --- CONFIGURACIÓN PRINCIPAL ---
# Cambia a False para usar el modo sin internet y configurar la hora manualmente
USAR_INTERNET = False

# --- CONFIGURACIÓN GENERAL (SOLO PARA MODO ONLINE) ---
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""
CLAVE_API_CLIMA = ""
LATITUD = "10.012415"
LONGITUD = "-84.027928"
URL_CLIMA = f"https://api.openweathermap.org/data/2.5/onecall?lat={LATITUD}&lon={LONGITUD}&exclude=current,minutely,hourly,alerts&appid={CLAVE_API_CLIMA}&units=metric&lang=es"

# --- CONFIGURACIÓN DE PINES ---
PIN_VALVULA = machine.Pin(16, machine.Pin.OUT)

# --- CLASES BASADAS EN EL DIAGRAMA UML ---
class CalendarioRiego:
    """Representa el 'CalendarioRiego'."""
    def __init__(self, hora_inicio, hora_fin, frecuencia_dias=1):
        self.hora_inicio = hora_inicio
        self.hora_fin = hora_fin
        self.frecuencia_dias = frecuencia_dias

    def debe_ejecutarse_ahora(self, hora_actual, dia_del_ano):
        """Verifica si, según la hora y la frecuencia, el riego debería estar activo."""
        if self.frecuencia_dias <= 0: return False
        if (dia_del_ano % self.frecuencia_dias) != 0: return False
        if self.hora_inicio <= hora_actual < self.hora_fin: return True
        return False

class Zona:
    """Representa una 'Zona' de riego."""
    def __init__(self, nombre, pin_sensor, humedad_minima, humedad_maxima, calendario):
        self.nombre = nombre
        self.sensor = dht.DHT22(machine.Pin(pin_sensor))
        self.humedad_minima = humedad_minima
        self.humedad_maxima = humedad_maxima
        self.calendario = calendario
        self.humedad_actual = 0
        self.temperatura_actual = 0

    def leer_sensor(self):
        """Lee el sensor de humedad y actualiza los valores internos."""
        try:
            self.sensor.measure()
            self.humedad_actual = self.sensor.humidity()
            self.temperatura_actual = self.sensor.temperature()
            print(f"Zona '{self.nombre}': Humedad={self.humedad_actual:.1f}%, Temp={self.temperatura_actual:.1f}°C")
        except Exception as e:
            print(f"Error al leer sensor en Zona '{self.nombre}': {e}")

    def verificar_logica_riego(self, hora_actual, dia_del_ano):
        """Aplica todas las reglas de los requerimientos para decidir si regar."""
        if self.humedad_actual < self.humedad_minima:
            print(f"¡Alerta! Humedad en '{self.nombre}' baja. Forzando riego.")
            return True
        if self.humedad_actual > self.humedad_maxima:
            print(f"Info: Humedad en '{self.nombre}' alta. Riego detenido.")
            return False
        if self.calendario.debe_ejecutarse_ahora(hora_actual, dia_del_ano):
            print(f"Info: Calendario activo para la zona '{self.nombre}'.")
            return True
        return False

# --- FUNCIONES AUXILIARES ---

def conectar_wifi():
    """Conecta el dispositivo a la red Wi-Fi."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Conectando a la red {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)
    print("Conexión Wi-Fi exitosa:", wlan.ifconfig())

def sincronizar_hora_ntp():
    """Sincroniza la hora del Pico W usando un servidor NTP por internet."""
    print("Sincronizando hora desde servidor NTP...")
    try:
        ntptime.settime()
        print("Hora sincronizada correctamente.")
    except Exception as e:
        print(f"Error al sincronizar hora: {e}")

def configurar_hora_manual():
    """
    Permite establecer la fecha y hora manualmente para el modo offline.
    El Pico no tiene reloj persistente, así que esto se debe hacer cada vez que se reinicia.
    """
    print("MODO OFFLINE: Configurando hora manualmente.")
    # FORMATO: (año, mes, día, día_de_la_semana, hora, minuto, segundo, microsegundo)
    # día_de_la_semana: Lunes=0, Martes=1, ..., Domingo=6
    # EJEMPLO: 17 de Octubre de 2025, 00:30:00, Viernes (4)
    fecha_y_hora = (2025, 10, 17, 4, 0, 30, 0, 0)
    
    rtc = machine.RTC()
    rtc.datetime(fecha_y_hora)
    print(f"Hora configurada a: {rtc.datetime()}")

def obtener_probabilidad_lluvia():
    """Consulta la API del clima. En modo offline, siempre retorna 0."""
    if not USAR_INTERNET:
        print("Info: Modo offline, omitiendo chequeo de lluvia.")
        return 0

    try:
        respuesta = urequests.get(URL_CLIMA)
        datos = respuesta.json()
        respuesta.close()
        pop_hoy = datos.get('daily', [])[0].get('pop', 0) * 100
        print(f"Probabilidad de lluvia para hoy: {pop_hoy:.1f}%")
        return pop_hoy
    except Exception as e:
        print(f"Error al obtener datos del clima: {e}")
        return 0

# --- INICIALIZACIÓN DEL SISTEMA ---

if USAR_INTERNET:
    conectar_wifi()
    sincronizar_hora_ntp()
else:
    configurar_hora_manual()

# Crear calendarios y zonas (sin cambios)
calendario_z1 = CalendarioRiego(hora_inicio=7, hora_fin=8, frecuencia_dias=1)
calendario_z2 = CalendarioRiego(hora_inicio=21, hora_fin=22, frecuencia_dias=3)
calendario_z3 = CalendarioRiego(hora_inicio=0, hora_fin=0, frecuencia_dias=0)

zona1 = Zona("Jardín Frontal", 15, 30, 60, calendario_z1)
zona2 = Zona("Patio Trasero", 14, 25, 55, calendario_z2)
zona3 = Zona("Patio de Luz", 13, 40, 70, calendario_z3)

zonas = [zona1, zona2, zona3]

# Variables de control
ultimo_chequeo_clima_dia = -1
probabilidad_lluvia_hoy = 0

# --- BUCLE PRINCIPAL ---
print("\n--- Sistema de Riego Hidrosmart INICIADO ---")
PIN_VALVULA.value(0)

while True:
    tiempo_actual = time.localtime()
    hora_actual = tiempo_actual[3]
    dia_actual_del_ano = tiempo_actual[7]
    
    if dia_actual_del_ano != ultimo_chequeo_clima_dia:
        print(f"\nNuevo día ({dia_actual_del_ano}).")
        probabilidad_lluvia_hoy = obtener_probabilidad_lluvia()
        ultimo_chequeo_clima_dia = dia_actual_del_ano

    if probabilidad_lluvia_hoy > 70:
        print(f"ADVERTENCIA: Probabilidad de lluvia alta. Riego suspendido hoy.")
        PIN_VALVULA.value(0)
        time.sleep(3600)
        continue

    alguna_zona_necesita_agua = False
    print(f"\n--- Verificando Zonas (Hora: {hora_actual:02d}:00) ---")
    
    for zona in zonas:
        zona.leer_sensor()
    
    for zona in zonas:
        if zona.verificar_logica_riego(hora_actual, dia_actual_del_ano):
            alguna_zona_necesita_agua = True
            print(f"DECISIÓN: Zona '{zona.nombre}' SÍ necesita riego.")
        else:
            print(f"DECISIÓN: Zona '{zona.nombre}' NO necesita riego.")

    if alguna_zona_necesita_agua:
        print("\nACCIÓN: ABRIENDO VÁLVULA principal.")
        PIN_VALVULA.value(1)
    else:
        print("\nACCIÓN: CERRANDO VÁLVULA principal.")
        PIN_VALVULA.value(0)

    print("--- Ciclo completado. Actualizando... ---")
    time.sleep(2)