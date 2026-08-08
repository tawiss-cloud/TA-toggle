import ctypes
import ctypes.wintypes
import time
from monitorcontrol import get_monitors
import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw
import threading
import tkinter as tk
from tkinter import ttk
import json
import os
import queue

# ===================== НАСТРОЙКИ =====================
DEBUG = False          # Включить отладочный вывод в консоль

# ===================== WINAPI =====================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

HOTKEY_ID = 1
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
VK_Z = 0x5A

WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_POPUP = 0x80000000
GWL_STYLE = -16

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)]

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", ctypes.c_ulong)]

# ===================== VCP =====================
VCP_MODE_SWITCH = 0xE0
VCP_LOCAL_DIMMING = 0x99
VCP_LOCAL_DIMMING_ALT = 0x47
VCP_BRIGHTNESS = 0x10
VCP_COLOR_PRESET = 0x14

# ===================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====================
current_mode_index = 0
last_switch_time = 0
DELAY = 1
manual_override = False  # Флаг ручного переключения

DEFAULT_MODES = [
    {"name": "Стандартный", "local_dimming": 2, "brightness": 20},
    {"name": "Игровой", "local_dimming": 3, "brightness": 36}
]

LOCAL_DIMMING_OPTIONS = [
    {"value": 2, "name": "Выкл", "description": "Local Dimming выключен"},
    {"value": 3, "name": "Низкий", "description": "Низкий уровень"},
    {"value": 5, "name": "Средний", "description": "Средний уровень"},
    {"value": 4, "name": "Средний+", "description": "Повышенный средний уровень"},
    {"value": 6, "name": "Высокий", "description": "Максимальный уровень"}
]

modes = DEFAULT_MODES.copy()
SETTINGS_FILE = "monitor_settings.json"

monitor_index = None
hotkey_thread_id = None
stop_hotkey_thread = False
tray_icon = None

hdr_settings = {
    "auto_set_preset": False,
    "preset_number": 5
}
auto_switch_enabled = True
media_players_enabled = True
media_delay_seconds = 5

tk_queue = queue.Queue()
active_connections = 0
connections_lock = threading.Lock()

# --- Отслеживание игр и медиа ---
game_counter = 0
GAME_THRESHOLD = 2
game_window_hwnd = None
media_timer = None
media_timer_lock = threading.Lock()
last_reported_state = None

# --- Кеш HDR статуса ---
hdr_status_cache = None
hdr_cache_time = 0
HDR_CACHE_TIME = 2  # Кешируем на 2 секунды
hdr_cache_lock = threading.Lock()

# --- Списки процессов ---
MEDIA_PLAYER_PROCESSES = [
    "mpc-hc.exe", "mpc-be.exe", "mpc-hc64.exe", "mpc-be64.exe",
    "vlc.exe", "potplayer.exe", "kmplayer.exe", "mediaplayerclassic.exe"
]

# ====== ЧЁРНЫЙ СПИСОК (ИСКЛЮЧЕНИЯ) ======
EXCLUDED_PROCESSES = [
    "wallpaper32.exe",      # Wallpaper Engine (32-bit)
    "wallpaper64.exe",      # Wallpaper Engine (64-bit)
    "chrome.exe",           # Google Chrome
    "firefox.exe",          # Mozilla Firefox
    "msedge.exe",           # Microsoft Edge
    "brave.exe",            # Brave Browser
    "opera.exe",            # Opera
    "explorer.exe",         # Проводник Windows
]

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def log(msg):
    if DEBUG:
        print(msg)

# --- Загрузка/сохранение настроек ---
def load_settings():
    global modes, hdr_settings, auto_switch_enabled, media_players_enabled, media_delay_seconds
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'modes' in data and isinstance(data['modes'], list) and len(data['modes']) == 2:
                    modes = data['modes']
                    log("Настройки режимов загружены")
                if 'hdr_settings' in data and isinstance(data['hdr_settings'], dict):
                    hdr_settings.update(data['hdr_settings'])
                    log("Настройки HDR загружены")
                if 'auto_switch_enabled' in data:
                    auto_switch_enabled = data['auto_switch_enabled']
                    log(f"Авто-переключение: {'включено' if auto_switch_enabled else 'выключено'}")
                if 'media_players_enabled' in data:
                    media_players_enabled = data['media_players_enabled']
                    log(f"Учёт медиаплееров: {'включён' if media_players_enabled else 'выключен'}")
                if 'media_delay_seconds' in data:
                    media_delay_seconds = data['media_delay_seconds']
                    log(f"Задержка медиаплееров: {media_delay_seconds} сек")
    except Exception as e:
        log(f"Ошибка загрузки: {e}")

def save_settings():
    try:
        data = {
            'modes': modes,
            'hdr_settings': hdr_settings,
            'auto_switch_enabled': auto_switch_enabled,
            'media_players_enabled': media_players_enabled,
            'media_delay_seconds': media_delay_seconds
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log("Настройки сохранены")
        return True
    except Exception as e:
        log(f"Ошибка сохранения: {e}")
        return False

# --- Безопасные операции с монитором ---
def safe_monitor_operation(operation, monitor_idx=None):
    global active_connections
    monitors = get_monitors()
    if not monitors:
        log("Мониторы не найдены")
        return None
    target_idx = monitor_idx if monitor_idx is not None else monitor_index
    if target_idx is None or target_idx >= len(monitors):
        log(f"Неверный индекс монитора: {target_idx}")
        return None
    monitor = None
    try:
        monitor = monitors[target_idx]
        with connections_lock:
            active_connections += 1
        with monitor:
            result = operation(monitor)
            return result
    except Exception as e:
        log(f"Ошибка операции с монитором: {e}")
        return None
    finally:
        with connections_lock:
            active_connections -= 1
        if monitor:
            monitor = None

def is_hdr_enabled(force_refresh=False):
    """
    Проверяет HDR по яркости 100% с кешированием на 2 секунды.
    force_refresh=True - принудительно обновить кеш
    """
    global hdr_status_cache, hdr_cache_time
    
    with hdr_cache_lock:
        now = time.time()
        
        # Если принудительное обновление или кеш устарел
        if force_refresh or hdr_status_cache is None or (now - hdr_cache_time) >= HDR_CACHE_TIME:
            # Делаем реальный запрос
            def check_hdr(monitor):
                try:
                    current_brightness, max_brightness = monitor.vcp.get_vcp_feature(VCP_BRIGHTNESS)
                    if current_brightness == 100:
                        return "hdr"
                    else:
                        return "ok"
                except Exception as e:
                    log(f"Ошибка чтения яркости: {e}")
                    return "error"
            
            result = safe_monitor_operation(check_hdr)
            
            # Если результат None, считаем что HDR выключен
            if result is None:
                result = "ok"
            
            hdr_status_cache = result
            hdr_cache_time = now
        
        return hdr_status_cache

def show_notification(message):
    def create_notification():
        try:
            notification = tk.Toplevel()
            notification.overrideredirect(True)
            notification.attributes('-topmost', True)
            notification.attributes('-alpha', 0.95)
            notification.configure(bg='#2b2b2b', highlightbackground='#000000', highlightthickness=1)
            screen_width = notification.winfo_screenwidth()
            screen_height = notification.winfo_screenheight()
            window_width = 350
            window_height = 70
            x = screen_width - window_width - 10
            y = screen_height - window_height - 50
            notification.geometry(f'{window_width}x{window_height}+{x}+{y}')
            message_label = tk.Label(notification, text=message, fg='#4CAF50', bg='#2b2b2b',
                                     font=('Arial', 11, 'bold'))
            message_label.pack(expand=True)
            def close_notification():
                try:
                    notification.destroy()
                except:
                    pass
            notification.after(2000, close_notification)
        except Exception as e:
            log(f"Ошибка уведомления: {e}")
    tk_queue.put(('notification', create_notification))

def get_current_monitor_settings():
    def get_settings(monitor):
        current_brightness = None
        current_local_dimming = None
        try:
            current_brightness, max_brightness = monitor.vcp.get_vcp_feature(VCP_BRIGHTNESS)
        except Exception as e:
            log(f"Ошибка получения яркости: {e}")
        try:
            current_local_dimming, max_local_dimming = monitor.vcp.get_vcp_feature(VCP_LOCAL_DIMMING)
        except Exception:
            try:
                current_local_dimming, max_local_dimming = monitor.vcp.get_vcp_feature(VCP_LOCAL_DIMMING_ALT)
            except Exception as e:
                log(f"Ошибка получения LD: {e}")
        return current_brightness, current_local_dimming
    return safe_monitor_operation(get_settings)

def sync_current_mode():
    global current_mode_index
    brightness, local_dimming = get_current_monitor_settings()
    if brightness is None or local_dimming is None:
        current_mode_index = 0
        return
    if (brightness == modes[0]["brightness"] and local_dimming == modes[0]["local_dimming"]):
        current_mode_index = 0
    elif (brightness == modes[1]["brightness"] and local_dimming == modes[1]["local_dimming"]):
        current_mode_index = 1
    else:
        diff_standard = abs(brightness - modes[0]["brightness"])
        diff_gaming = abs(brightness - modes[1]["brightness"])
        current_mode_index = 0 if diff_standard < diff_gaming else 1

def find_titan_army_monitor():
    global monitor_index
    monitors = get_monitors()
    log(f"Найдено мониторов: {len(monitors)}")
    for i, monitor in enumerate(monitors):
        try:
            with monitor:
                try:
                    current, maximum = monitor.vcp.get_vcp_feature(VCP_MODE_SWITCH)
                    if maximum >= 14:
                        monitor_index = i
                        log(f"Найден Titan Army (индекс {i})")
                        return True
                except Exception as e:
                    log(f"Монитор {i}: VCP 0xE0 не поддерживается")
        except Exception as e:
            log(f"Монитор {i}: ошибка доступа - {e}")
            continue
    for i, monitor in enumerate(monitors):
        try:
            with monitor:
                monitor_index = i
                log(f"Выбран первый доступный монитор (индекс {i})")
                return True
        except Exception:
            continue
    log("Ни один монитор не доступен!")
    return False

def create_image():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    margin = 16
    d.rectangle([margin, margin, 64 - margin - 1, 64 - margin - 1],
                fill=(255, 255, 255, 255))
    d.rectangle([margin, margin, 64 - margin - 1, 64 - margin - 1],
                outline=(0, 0, 0, 255), width=1)
    return img

# --- Применение настроек с повторными попытками ---
def set_local_dimming(monitor, value, retries=3):
    for attempt in range(retries):
        try:
            monitor.vcp.set_vcp_feature(VCP_LOCAL_DIMMING, value)
            try:
                monitor.vcp.set_vcp_feature(VCP_LOCAL_DIMMING_ALT, value)
            except Exception:
                pass
            return True
        except Exception as e:
            log(f"Ошибка установки LD (попытка {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(0.3)
            else:
                log("Не удалось установить LD после нескольких попыток")
                return False
    return False

def apply_mode_settings(mode_index):
    mode = modes[mode_index]
    def set_mode(monitor):
        success_brightness = False
        success_dimming = False
        # Яркость
        for attempt in range(3):
            try:
                monitor.vcp.set_vcp_feature(VCP_BRIGHTNESS, mode["brightness"])
                success_brightness = True
                log(f"Яркость {mode['brightness']} установлена успешно")
                break
            except Exception as e:
                log(f"Ошибка установки яркости (попытка {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(0.3)
        if not success_brightness:
            log("Не удалось установить яркость после нескольких попыток")
        time.sleep(0.1)
        # Локальное затемнение
        for attempt in range(3):
            try:
                monitor.vcp.set_vcp_feature(VCP_LOCAL_DIMMING, mode["local_dimming"])
                try:
                    monitor.vcp.set_vcp_feature(VCP_LOCAL_DIMMING_ALT, mode["local_dimming"])
                except:
                    pass
                success_dimming = True
                log(f"LD {mode['local_dimming']} установлен успешно")
                break
            except Exception as e:
                log(f"Ошибка установки LD (попытка {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(0.3)
        if not success_dimming:
            log("Не удалось установить LD после нескольких попыток")
        return success_dimming, success_brightness
    result = safe_monitor_operation(set_mode)
    if result is None:
        log("safe_monitor_operation вернула None")
        return False, False, False
    success_dimming, success_brightness = result
    return (success_dimming or success_brightness), success_dimming, success_brightness

def apply_mode_by_index(index, force_hdr_check=False):
    global current_mode_index, tray_icon
    if current_mode_index == index:
        return True
    
    # Проверка HDR перед переключением
    hdr_check = is_hdr_enabled(force_refresh=force_hdr_check)
    if hdr_check == "hdr":
        log("HDR включен – переключение режимов заблокировано")
        return False
    
    for attempt in range(3):
        log(f"Попытка переключения на режим {index} (шаг {attempt+1}/3)")
        apply_success, _, _ = apply_mode_settings(index)
        if apply_success:
            current_mode_index = index
            if tray_icon:
                try:
                    tray_icon.title = f"Режим {modes[current_mode_index]['name']}"
                except:
                    pass
            show_notification(f"Режим: {modes[current_mode_index]['name']}")
            return True
        else:
            log(f"Не удалось применить режим {index}, попытка {attempt+1}/3")
            if attempt < 2:
                time.sleep(1)
    log(f"Не удалось переключить на режим {index} после 3 попыток")
    return False

# --- Определение процесса ---
def get_process_name(hwnd):
    try:
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return None
        handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            size = psapi.GetModuleFileNameExW(handle, None, buffer, ctypes.wintypes.MAX_PATH)
            if size > 0:
                return os.path.basename(buffer.value)
        finally:
            kernel32.CloseHandle(handle)
        return None
    except Exception as e:
        log(f"Ошибка получения имени процесса: {e}")
        return None

def is_game_window(hwnd):
    if not hwnd:
        return False

    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    monitor = user32.MonitorFromWindow(hwnd, 2)
    if not monitor:
        return False

    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
        return False

    monitor_rect = mi.rcMonitor
    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top
    mon_w = monitor_rect.right - monitor_rect.left
    mon_h = monitor_rect.bottom - monitor_rect.top

    width_ratio = win_w / mon_w
    height_ratio = win_h / mon_h
    covers_most = (width_ratio >= 0.95 and height_ratio >= 0.95)

    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    if style == 0:
        return False

    has_caption = bool(style & WS_CAPTION)
    is_popup = bool(style & WS_POPUP)

    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.IsIconic(hwnd):
        return False

    is_game = covers_most and (not has_caption or is_popup)

    process_name = get_process_name(hwnd)
    if process_name:
        if process_name.lower() in [p.lower() for p in EXCLUDED_PROCESSES]:
            log(f"Исключён процесс {process_name}")
            return False

    if not is_game and media_players_enabled:
        if process_name and process_name.lower() in [m.lower() for m in MEDIA_PLAYER_PROCESSES]:
            media_covers = (width_ratio >= 0.70 and height_ratio >= 0.70)
            if media_covers:
                log(f"Медиаплеер {process_name} – игровой режим")
                return True

    return is_game

# --- Отложенное переключение для медиаплеера ---
def delayed_media_switch(hwnd):
    global media_timer, game_window_hwnd, last_reported_state
    with media_timer_lock:
        media_timer = None
    
    hdr_check = is_hdr_enabled()
    if hdr_check == "hdr":
        log("HDR включен – переключение медиаплеера отменено")
        return
    
    if not user32.IsWindow(hwnd):
        log("Медиаплеер закрыт до срабатывания таймера – отмена")
        return
    
    if not is_game_window(hwnd):
        log("Окно перестало быть медиаплеером за время задержки – отмена")
        return
    
    if current_mode_index != 1:
        log(f"Медиаплеер подтверждён через {media_delay_seconds} сек – переключение на игровой режим")
        if apply_mode_by_index(1):
            game_window_hwnd = hwnd
            last_reported_state = True
    else:
        log("Медиаплеер подтверждён, но игровой режим уже активен")
        game_window_hwnd = hwnd
        last_reported_state = True

# --- Мониторинг (проверка каждую секунду) ---
def monitor_loop():
    global current_mode_index, stop_hotkey_thread, game_counter, game_window_hwnd
    global auto_switch_enabled, media_timer, media_delay_seconds, last_reported_state
    global manual_override

    while not stop_hotkey_thread:
        try:
            if not auto_switch_enabled:
                time.sleep(1)
                continue

            # Если включён ручной режим - пропускаем все авто-переключения
            if manual_override:
                time.sleep(1)
                continue

            hwnd = user32.GetForegroundWindow()
            is_game = False
            is_media = False
            if hwnd:
                is_game = is_game_window(hwnd)
                if is_game and media_players_enabled:
                    process_name = get_process_name(hwnd)
                    if process_name and process_name.lower() in [m.lower() for m in MEDIA_PLAYER_PROCESSES]:
                        is_media = True

            if is_game:
                game_counter = min(game_counter + 1, GAME_THRESHOLD + 1)

                if is_media:
                    if game_counter >= GAME_THRESHOLD:
                        if game_window_hwnd == hwnd and last_reported_state == True:
                            pass
                        else:
                            with media_timer_lock:
                                if media_timer is None:
                                    log(f"Медиаплеер обнаружен – запускаем задержку {media_delay_seconds} сек")
                                    media_timer = threading.Timer(media_delay_seconds, delayed_media_switch, args=[hwnd])
                                    media_timer.daemon = True
                                    media_timer.start()
                else:
                    with media_timer_lock:
                        if media_timer is not None:
                            media_timer.cancel()
                            media_timer = None
                            log("Обнаружена игра – таймер медиа отменён")
                    if game_counter >= GAME_THRESHOLD:
                        if last_reported_state != True:
                            log("Обнаружена игра (подтверждено) – переключение на игровой режим")
                            if apply_mode_by_index(1):
                                game_window_hwnd = hwnd
                                last_reported_state = True
            else:
                game_counter = max(game_counter - 1, 0)
                with media_timer_lock:
                    if media_timer is not None:
                        media_timer.cancel()
                        media_timer = None
                        log("Активное окно не игра – таймер медиа отменён")

                if game_window_hwnd is not None:
                    if not user32.IsWindow(game_window_hwnd):
                        log("Игра/медиаплеер закрыта (окно уничтожено) – возврат стандартного режима")
                        if apply_mode_by_index(0):
                            game_window_hwnd = None
                            last_reported_state = False
                    else:
                        if last_reported_state != True:
                            log("Игра/медиаплеер уже запущена (свёрнута) – переключаем на игровой")
                            if apply_mode_by_index(1):
                                last_reported_state = True
                else:
                    if last_reported_state is None:
                        log("Игра/медиаплеер не обнаружена – состояние стандартное (без переключения)")
                        last_reported_state = False
                    elif last_reported_state != False:
                        log("Игра/медиаплеер не обнаружена – возврат стандартного режима")
                        if apply_mode_by_index(0):
                            last_reported_state = False

        except Exception as e:
            log(f"Ошибка в мониторинге: {e}")

        time.sleep(1)  # Проверка каждую секунду

# --- Ручное переключение ---
def toggle_mode(icon=None):
    global current_mode_index, last_switch_time, last_reported_state
    global manual_override
    
    now = time.time()
    if now - last_switch_time < DELAY:
        return
    
    try:
        log("\n" + "="*50)
        log("Начало переключения режима")
        
        # При ручном переключении принудительно обновляем HDR кеш
        hdr_check_result = is_hdr_enabled(force_refresh=True)
        if hdr_check_result == "error":
            log("Ошибка проверки HDR")
            show_notification("⚠️ Ошибка проверки HDR")
            return
        if hdr_check_result == "hdr":
            log("HDR включен - переключение заблокировано")
            show_notification("⚠️ Включен HDR")
            return
        
        if monitor_index is None:
            if not find_titan_army_monitor():
                return
        
        sync_current_mode()
        new_mode_index = 1 - current_mode_index
        
        # При ручном переключении принудительно обновляем HDR кеш
        if apply_mode_by_index(new_mode_index, force_hdr_check=True):
            last_switch_time = now
            mode_name = modes[current_mode_index]["name"]
            
            # Переключаем ручной режим: если он был включён, выключаем, иначе включаем
            if manual_override:
                manual_override = False
                log("Ручной режим отключён")
            else:
                manual_override = True
                log("Ручной режим включён")
            
            # Синхронизация состояния при ручном переключении
            if current_mode_index == 1:
                last_reported_state = True
            else:
                last_reported_state = False
            
            show_notification(f"Режим: {mode_name}")
            if icon:
                try:
                    icon.title = f"Режим {mode_name}"
                except Exception:
                    pass
        
        log("="*50)
    except Exception as e:
        log(f"Ошибка переключения: {e}")

def get_local_dimming_name(value):
    for option in LOCAL_DIMMING_OPTIONS:
        if option["value"] == value:
            return option["name"]
    return "Неизвестно"

# ===================== ИНТЕРФЕЙС =====================
def create_settings_window():
    def create_window():
        def save_all_settings():
            nonlocal auto_switch_var, media_players_var, media_delay_var
            try:
                standard_brightness = int(standard_brightness_entry.get())
                if not (0 <= standard_brightness <= 100):
                    raise ValueError("Яркость должна быть от 0 до 100")
                standard_dimming = standard_dimming_var.get()
                if standard_dimming == 0:
                    raise ValueError("Выберите режим локального затемнения")
                gaming_brightness = int(gaming_brightness_entry.get())
                if not (0 <= gaming_brightness <= 100):
                    raise ValueError("Яркость должна быть от 0 до 100")
                gaming_dimming = gaming_dimming_var.get()
                if gaming_dimming == 0:
                    raise ValueError("Выберите режим локального затемнения")
                auto_set_preset = auto_set_var.get()
                preset_number = int(preset_entry.get())
                if not (0 <= preset_number <= 255):
                    raise ValueError("Номер пресета должен быть от 0 до 255")
                
                try:
                    delay_val = int(media_delay_var.get())
                    if delay_val < 1:
                        raise ValueError("Задержка должна быть не менее 1 секунды")
                    if delay_val > 60:
                        raise ValueError("Задержка не должна превышать 60 секунд")
                except ValueError as e:
                    show_notification(f"Ошибка в поле задержки: {e}")
                    return

                global auto_switch_enabled, media_players_enabled, media_delay_seconds
                auto_switch_enabled = auto_switch_var.get()
                media_players_enabled = media_players_var.get()
                media_delay_seconds = delay_val

                modes[0]["brightness"] = standard_brightness
                modes[0]["local_dimming"] = standard_dimming
                modes[1]["brightness"] = gaming_brightness
                modes[1]["local_dimming"] = gaming_dimming
                hdr_settings["auto_set_preset"] = auto_set_preset
                hdr_settings["preset_number"] = preset_number

                if save_settings():
                    show_notification("Настройки сохранены")
                    hdr_check = is_hdr_enabled(force_refresh=True)
                    if hdr_check != "hdr":
                        apply_mode_settings(current_mode_index)

                if auto_switch_enabled:
                    def check_now():
                        hwnd = user32.GetForegroundWindow()
                        if hwnd and is_game_window(hwnd):
                            log("Авто-переключение включено – игра/медиаплеер активна, переключаем")
                            apply_mode_by_index(1, force_hdr_check=True)
                    threading.Thread(target=check_now, daemon=True).start()

                window.destroy()
            except ValueError as e:
                show_notification(f"Ошибка: {str(e)}")
            except Exception as e:
                show_notification(f"Ошибка сохранения: {e}")

        def on_cancel():
            window.destroy()

        def on_standard_dimming_select():
            selected_value = standard_dimming_var.get()
            for option in LOCAL_DIMMING_OPTIONS:
                if option["value"] == selected_value:
                    standard_desc_label.config(text=option["description"])
                    break

        def on_gaming_dimming_select():
            selected_value = gaming_dimming_var.get()
            for option in LOCAL_DIMMING_OPTIONS:
                if option["value"] == selected_value:
                    gaming_desc_label.config(text=option["description"])
                    break

        def toggle_media_players_state(*args):
            if auto_switch_var.get():
                media_players_check.config(state="normal")
                if media_players_var.get():
                    media_delay_entry.config(state="normal")
                else:
                    media_delay_entry.config(state="disabled")
            else:
                media_players_check.config(state="disabled")
                media_delay_entry.config(state="disabled")

        def toggle_media_delay_state(*args):
            if auto_switch_var.get() and media_players_var.get():
                media_delay_entry.config(state="normal")
            else:
                media_delay_entry.config(state="disabled")

        window = tk.Toplevel()
        window.title("Настройки")
        window.geometry("550x750")
        window.resizable(False, False)
        window.update_idletasks()
        x = (window.winfo_screenwidth() - 550) // 2
        y = (window.winfo_screenheight() - 750) // 2
        window.geometry(f"+{x}+{y}")

        canvas = tk.Canvas(window)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        main_frame = ttk.Frame(scrollable_frame, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        auto_switch_var = tk.BooleanVar(value=auto_switch_enabled)
        auto_switch_check = ttk.Checkbutton(
            main_frame,
            text="Автоматическое переключение игровых режимов",
            variable=auto_switch_var,
            command=toggle_media_players_state
        )
        auto_switch_check.pack(anchor=tk.W, pady=(0, 5))

        media_players_var = tk.BooleanVar(value=media_players_enabled)
        media_players_check = ttk.Checkbutton(
            main_frame,
            text="Включать медиаплееры (MPC, VLC, PotPlayer) в игровой режим",
            variable=media_players_var,
            command=toggle_media_delay_state
        )
        media_players_check.pack(anchor=tk.W, pady=(0, 5))

        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 15))
        ttk.Label(delay_frame, text="Задержка перед переключением для медиаплееров (сек):").pack(side=tk.LEFT, padx=(0, 5))
        media_delay_var = tk.StringVar(value=str(media_delay_seconds))
        media_delay_entry = ttk.Entry(delay_frame, width=10, textvariable=media_delay_var)
        media_delay_entry.pack(side=tk.LEFT)
        ttk.Label(delay_frame, text="(1-60)").pack(side=tk.LEFT, padx=5)

        if not (auto_switch_var.get() and media_players_var.get()):
            media_delay_entry.config(state="disabled")

        auto_switch_var.trace('w', toggle_media_players_state)
        media_players_var.trace('w', toggle_media_delay_state)

        standard_frame = ttk.LabelFrame(main_frame, text="Стандартный режим (SDR)", padding="10")
        standard_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(standard_frame, text="Яркость (0-100):").pack(anchor=tk.W, pady=(0, 5))
        standard_brightness_entry = ttk.Entry(standard_frame, width=20)
        standard_brightness_entry.insert(0, str(modes[0]["brightness"]))
        standard_brightness_entry.pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(standard_frame, text="Локальное затемнение:", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        standard_dimming_var = tk.IntVar(value=modes[0]["local_dimming"])
        radio_frame_standard = ttk.Frame(standard_frame)
        radio_frame_standard.pack(anchor=tk.W, fill=tk.X)
        for i, option in enumerate(LOCAL_DIMMING_OPTIONS):
            col = i % 2
            row = i // 2
            frame = ttk.Frame(radio_frame_standard)
            frame.grid(row=row, column=col, sticky=tk.W, padx=(0, 20), pady=2)
            rb = ttk.Radiobutton(frame, text=f"{option['name']} ({option['value']})",
                                 variable=standard_dimming_var, value=option["value"],
                                 command=on_standard_dimming_select)
            rb.pack(anchor=tk.W)
        standard_desc_label = ttk.Label(standard_frame, text="", wraplength=500, foreground="gray")
        standard_desc_label.pack(anchor=tk.W, pady=(5, 0))
        on_standard_dimming_select()

        gaming_frame = ttk.LabelFrame(main_frame, text="Игровой режим (SDR)", padding="10")
        gaming_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(gaming_frame, text="Яркость (0-100):").pack(anchor=tk.W, pady=(0, 5))
        gaming_brightness_entry = ttk.Entry(gaming_frame, width=20)
        gaming_brightness_entry.insert(0, str(modes[1]["brightness"]))
        gaming_brightness_entry.pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(gaming_frame, text="Локальное затемнение:", font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        gaming_dimming_var = tk.IntVar(value=modes[1]["local_dimming"])
        radio_frame_gaming = ttk.Frame(gaming_frame)
        radio_frame_gaming.pack(anchor=tk.W, fill=tk.X)
        for i, option in enumerate(LOCAL_DIMMING_OPTIONS):
            col = i % 2
            row = i // 2
            frame = ttk.Frame(radio_frame_gaming)
            frame.grid(row=row, column=col, sticky=tk.W, padx=(0, 20), pady=2)
            rb = ttk.Radiobutton(frame, text=f"{option['name']} ({option['value']})",
                                 variable=gaming_dimming_var, value=option["value"],
                                 command=on_gaming_dimming_select)
            rb.pack(anchor=tk.W)
        gaming_desc_label = ttk.Label(gaming_frame, text="", wraplength=500, foreground="gray")
        gaming_desc_label.pack(anchor=tk.W, pady=(5, 0))
        on_gaming_dimming_select()

        hdr_frame = ttk.LabelFrame(main_frame, text="Настройки HDR", padding="10")
        hdr_frame.pack(fill=tk.X, pady=(0, 15))
        auto_set_var = tk.BooleanVar(value=hdr_settings["auto_set_preset"])
        auto_set_check = ttk.Checkbutton(hdr_frame,
                                         text="Устанавливать цветовой пресет при нажатии Ctrl+Alt+Z (если HDR включен)",
                                         variable=auto_set_var)
        auto_set_check.pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(hdr_frame, text="Номер цветового пресета (0-255):").pack(anchor=tk.W, pady=(0, 5))
        preset_entry = ttk.Entry(hdr_frame, width=20)
        preset_entry.insert(0, str(hdr_settings["preset_number"]))
        preset_entry.pack(anchor=tk.W)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Сохранить", command=save_all_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=on_cancel).pack(side=tk.LEFT, padx=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", on_mousewheel)

        window.protocol("WM_DELETE_WINDOW", on_cancel)
        window.focus_force()

    tk_queue.put(('window', create_window))

def set_hdr_color_preset():
    try:
        log("Проверка HDR для пресета...")
        hdr_check_result = is_hdr_enabled(force_refresh=True)
        if hdr_check_result != "hdr":
            log("HDR не включен")
            return
        if not hdr_settings["auto_set_preset"]:
            log("Автоустановка пресета отключена")
            show_notification("⚠️ Включен HDR")
            return
        preset_number = hdr_settings["preset_number"]
        log(f"Установка цветового пресета {preset_number}...")
        if preset_number <= 20 and preset_number != 0:
            log(f"Предупреждение: Значение {preset_number} может не подходить для HDR")
            show_notification(f"⚠️ Пресет {preset_number} может не работать в HDR")
        def set_color_preset(monitor):
            try:
                monitor.vcp.set_vcp_feature(VCP_COLOR_PRESET, preset_number)
                return True
            except Exception as e:
                log(f"Ошибка установки: {e}")
                return False
        success = safe_monitor_operation(set_color_preset)
        if success:
            show_notification(f"✅ Цветовой пресет {preset_number} установлен")
        else:
            show_notification(f"❌ Пресет {preset_number} не поддерживается в HDR")
    except Exception as e:
        log(f"Ошибка: {e}")

def on_settings(icon, item):
    create_settings_window()

def on_about(icon, item):
    def create_about_window():
        about_window = tk.Toplevel()
        about_window.title("О программе")
        about_window.geometry("500x460")
        about_window.resizable(False, False)
        about_window.update_idletasks()
        x = (about_window.winfo_screenwidth() - 500) // 2
        y = (about_window.winfo_screenheight() - 460) // 2
        about_window.geometry(f"+{x}+{y}")
        main_frame = ttk.Frame(about_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        title_label = ttk.Label(main_frame, text="Переключение режимов монитора", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        hdr_status = "Включена" if hdr_settings["auto_set_preset"] else "Отключена"
        info_text = (
            "Горячая клавиша: Ctrl+Alt+Z\n\n"
            "Текущие настройки (SDR):\n"
            f"• Стандартный: {get_local_dimming_name(modes[0]['local_dimming'])} ({modes[0]['local_dimming']}), яркость {modes[0]['brightness']}\n"
            f"• Игровой: {get_local_dimming_name(modes[1]['local_dimming'])} ({modes[1]['local_dimming']}), яркость {modes[1]['brightness']}\n\n"
            "Исключены из определения игр:\n"
            "Wallpaper Engine, Chrome, Firefox, Edge, Brave, Opera, Проводник\n\n"
            "Версия: 3.8"
        )
        info_label = ttk.Label(main_frame, text=info_text, justify=tk.LEFT)
        info_label.pack(pady=10)
        close_button = ttk.Button(main_frame, text="Закрыть", command=about_window.destroy)
        close_button.pack(pady=10)
        about_window.protocol("WM_DELETE_WINDOW", about_window.destroy)
        about_window.focus_force()
    tk_queue.put(('window', create_about_window))

def on_quit(icon, item):
    global stop_hotkey_thread, media_timer
    stop_hotkey_thread = True
    with media_timer_lock:
        if media_timer is not None:
            media_timer.cancel()
            media_timer = None
    try:
        user32.UnregisterHotKey(None, HOTKEY_ID)
    except:
        pass
    icon.stop()

def hotkey_listener(icon):
    global hotkey_thread_id, stop_hotkey_thread
    hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_Z):
        log("Не удалось зарегистрировать горячую клавишу")
        return
    try:
        msg = ctypes.wintypes.MSG()
        while not stop_hotkey_thread:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                break
            if ret == -1:
                break
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                hdr_check = is_hdr_enabled(force_refresh=True)
                if hdr_check == "hdr":
                    set_hdr_color_preset()
                else:
                    toggle_mode(icon)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)

def start_tkinter():
    root = tk.Tk()
    root.withdraw()
    def process_queue():
        try:
            while True:
                try:
                    command_type, command_func = tk_queue.get_nowait()
                    if command_type in ['notification', 'window']:
                        command_func()
                except queue.Empty:
                    break
        except Exception as e:
            log(f"Ошибка обработки очереди: {e}")
        root.after(100, process_queue)
    root.after(100, process_queue)
    root.mainloop()

# ===================== ЗАПУСК =====================
if __name__ == "__main__":
    load_settings()
    print("=== Запуск программы ===")
    print(f"Стандартный: LD {modes[0]['local_dimming']}, яркость {modes[0]['brightness']}")
    print(f"Игровой: LD {modes[1]['local_dimming']}, яркость {modes[1]['brightness']}")
    print(f"HDR: автоустановка={hdr_settings['auto_set_preset']}, пресет={hdr_settings['preset_number']}")
    print(f"Авто-переключение: {'включено' if auto_switch_enabled else 'выключено'}")
    print(f"Учёт медиаплееров: {'включён' if media_players_enabled else 'выключен'}")
    print(f"Задержка медиаплееров: {media_delay_seconds} сек")
    print(f"Режим отладки: {'ВКЛЮЧЁН' if DEBUG else 'ВЫКЛЮЧЕН'}")

    if not find_titan_army_monitor():
        monitor_index = 0
    sync_current_mode()

    tk_thread = threading.Thread(target=start_tkinter, daemon=True)
    tk_thread.start()

    tray_icon = pystray.Icon("monitor_toggle")
    tray_icon.menu = Menu(
        item('О программе', on_about),
        item('Настройки', on_settings),
        item('Закрыть', on_quit)
    )
    tray_icon.icon = create_image()
    tray_icon.title = f"Режим {modes[current_mode_index]['name']}"

    threading.Thread(target=lambda: hotkey_listener(tray_icon), daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()

    print(f"\nПрограмма запущена. Текущий режим: {modes[current_mode_index]['name']}")
    if auto_switch_enabled:
        print("Автоматическое переключение активно (проверка каждую секунду)")
        if media_players_enabled:
            print(f"Учёт медиаплееров включён, задержка {media_delay_seconds} сек")
        else:
            print("Учёт медиаплееров выключен")
    else:
        print("Автоматическое переключение отключено")
    print("Исключены из определения игр: Wallpaper Engine, браузеры, Проводник")
    print("Ручное переключение (Ctrl+Alt+Z) включает/выключает авто-режим")
    tray_icon.run()