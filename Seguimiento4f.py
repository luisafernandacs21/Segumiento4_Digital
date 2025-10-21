from machine import Pin, I2C, PWM, Timer
from ssd1306 import SSD1306_I2C
import time, random

BTN_UP, BTN_DOWN, BTN_START = 14, 27, 12
BUZZER_PIN = 13
SCL_PIN = 22
SDA_PIN = 21

MODOS = [
    ("Clasico",       (3, 800)),
    ("Contra-tiempo", (3, 700)),
    ("Hardcore",      (5, 400))
]
DURACION_CONTRATIEMPO = 60000

SOUND_CONFIRM     = [(800, 70), (1000, 100)]
SOUND_PAUSE       = [(600, 150)]
SOUND_GAMEOVER    = [(400, 200), (0, 50), (200, 300)]
SOUND_MOVE_UP     = [(1000, 40)]
SOUND_MOVE_DOWN   = [(700, 40)]

i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN)) 
oled = SSD1306_I2C(128, 64, i2c)
btn_up = Pin(BTN_UP, Pin.IN, Pin.PULL_UP)
btn_down = Pin(BTN_DOWN, Pin.IN, Pin.PULL_UP)
btn_start = Pin(BTN_START, Pin.IN, Pin.PULL_UP)
buzzer = PWM(Pin(BUZZER_PIN))
buzzer.deinit()

sound_timer, chirp_timer = Timer(-1), Timer(-1)
current_melody, current_note_index, chirp_state = None, 0, {}

def _stop_all_sounds():
    sound_timer.deinit(); chirp_timer.deinit(); buzzer.deinit()

def _play_next_note_callback(timer):
    global current_note_index
    current_note_index += 1
    if current_note_index < len(current_melody):
        freq, dur = current_melody[current_note_index]
        buzzer.duty(0 if freq == 0 else 512); buzzer.freq(freq if freq != 0 else 1000)
        sound_timer.init(period=dur, mode=Timer.ONE_SHOT, callback=_play_next_note_callback)
    else: _stop_all_sounds()

def play_beep(melody):
    global current_melody, current_note_index
    if not melody: return
    _stop_all_sounds(); current_melody, current_note_index = melody, 0
    freq, dur = current_melody[0]
    buzzer.init(freq=freq if freq != 0 else 1000, duty=0 if freq == 0 else 512)
    sound_timer.init(period=dur, mode=Timer.ONE_SHOT, callback=_play_next_note_callback)

def _chirp_callback(timer):
    global chirp_state
    chirp_state['current'] += chirp_state['step']
    if (chirp_state['step'] > 0 and chirp_state['current'] >= chirp_state['end']) or \
       (chirp_state['step'] < 0 and chirp_state['current'] <= chirp_state['end']): _stop_all_sounds()
    else: buzzer.freq(int(chirp_state['current']))

def play_chirp(start_freq, end_freq, duration_ms, steps=20):
    global chirp_state
    if duration_ms == 0: return
    _stop_all_sounds()
    period = max(1, duration_ms // steps)
    chirp_state = {'current': float(start_freq), 'end': float(end_freq), 'step': (end_freq - start_freq) / steps}
    buzzer.init(freq=start_freq, duty=512)
    chirp_timer.init(period=period, mode=Timer.PERIODIC, callback=_chirp_callback)

# ESTADO DEL JUEGO
estado, modo = "MENU", 0
jugador_y, puntaje, obstaculos = 28, 0, []
obstaculos_esquivados = 0 
inicio_tiempo, ultimo_spawn, tiempo_pausado_inicio = 0, 0, 0

def reset_game_state():
    global jugador_y, puntaje, obstaculos, obstaculos_esquivados, inicio_tiempo, ultimo_spawn
    jugador_y, puntaje, obstaculos = 28, 0, []
    obstaculos_esquivados = 0 
    inicio_tiempo, ultimo_spawn = time.ticks_ms(), 0

def actualizar_juego(velocidad, spawn_rate):
    global obstaculos, ultimo_spawn, puntaje, obstaculos_esquivados
    if time.ticks_diff(time.ticks_ms(), ultimo_spawn) > spawn_rate:
        obstaculos.append([120, random.randint(0, 56)])
        ultimo_spawn = time.ticks_ms()
    
    nuevos_obstaculos = []
    for obs in obstaculos:
        obs[0] -= velocidad
        if obs[0] + 8 > 0: 
            nuevos_obstaculos.append(obs)
        else: 
            puntaje += 5
            obstaculos_esquivados += 1 
    obstaculos = nuevos_obstaculos
    puntaje += 1
    
    if modo == 0 and puntaje > 0 and puntaje % 200 == 0:
        return velocidad + 1, max(300, spawn_rate - 50)
    return velocidad, spawn_rate

def colisiona():
    for obs in obstaculos:
        if 10 < obs[0] + 8 and 18 > obs[0] and jugador_y < obs[1] + 8 and jugador_y + 8 > obs[1]:
            return True
    return False

def dibujar_pantalla():
    oled.fill(0)
    
    if estado == "MENU":
        oled.text("== DODGER ==", 20, 0)
        for i, (nombre, _) in enumerate(MODOS):
            oled.text(f"{'>' if i == modo else ' '} {nombre}", 20, 20 + i * 12)
    elif estado == "JUEGO" or estado == "PAUSA":
        oled.fill_rect(10, jugador_y, 8, 8, 1)
        for obs in obstaculos: oled.fill_rect(obs[0], obs[1], 8, 8, 1)
        
        # --- HUD ---
        oled.text(f"E:{obstaculos_esquivados}", 0, 0)
        oled.text(f"P:{puntaje}", 80, 0)
        if modo == 1:
            tiempo_restante = max(0, DURACION_CONTRATIEMPO - time.ticks_diff(time.ticks_ms(), inicio_tiempo))
            oled.text(f"T:{tiempo_restante // 1000}s", 45, 0)
        if estado == "PAUSA": oled.text("--- PAUSA ---", 18, 28)
    elif estado == "GAME_OVER":
        oled.text("GAME OVER", 25, 10)
        oled.text(f"Puntaje:{puntaje}", 10, 35)
        oled.text(f"Esquivados:{obstaculos_esquivados}", 10, 45)
    
    if estado == "MENU": oled.text("Estado: MENU", 0, 56)
    elif estado == "JUEGO": oled.text(f"Modo:{MODOS[modo][0][:4]}", 0, 56)
    elif estado == "PAUSA": oled.text("Estado: PAUSA", 0, 56)
    elif estado == "GAME_OVER": oled.text("Estado: FIN", 0, 56)
    oled.show()

# BUCLE PRINCIPAL 
velocidad_juego, spawn_rate_juego = 0, 0

while True:
    if estado == "MENU":
        if not btn_up.value(): modo = (modo - 1) % len(MODOS); play_chirp(1200, 1500, 70); time.sleep_ms(200)
        elif not btn_down.value(): modo = (modo + 1) % len(MODOS); play_chirp(1200, 900, 70); time.sleep_ms(200)
        elif not btn_start.value():
            reset_game_state()
            _, (velocidad_juego, spawn_rate_juego) = MODOS[modo]
            estado = "JUEGO"
            play_beep(SOUND_CONFIRM); time.sleep_ms(300)

    elif estado == "JUEGO":
        if not btn_start.value():
            estado, tiempo_pausado_inicio = "PAUSA", time.ticks_ms()
            _stop_all_sounds(); play_beep(SOUND_PAUSE); time.sleep_ms(200); continue
        
        if not btn_up.value() and jugador_y > 0: jugador_y -= 4; play_beep(SOUND_MOVE_UP)
        elif not btn_down.value() and jugador_y < 56: jugador_y += 4; play_beep(SOUND_MOVE_DOWN)
        
        velocidad_juego, spawn_rate_juego = actualizar_juego(velocidad_juego, spawn_rate_juego)
        
        if colisiona() or (modo == 1 and time.ticks_diff(time.ticks_ms(), inicio_tiempo) >= DURACION_CONTRATIEMPO):
            estado = "GAME_OVER"

    elif estado == "PAUSA":
        if not btn_start.value():
            inicio_tiempo += time.ticks_diff(time.ticks_ms(), tiempo_pausado_inicio)
            estado = "JUEGO"
            play_beep(SOUND_PAUSE); time.sleep_ms(200)

    elif estado == "GAME_OVER":
        _stop_all_sounds()
        dibujar_pantalla()
        play_beep(SOUND_GAMEOVER); time.sleep(3)
        estado = "MENU"

    dibujar_pantalla()