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
import webbrowser

# ===================== НАСТРОЙКИ =====================
advanced_settings_enabled = False
debug_enabled = False
DEBUG_LOG_FILE = "monitor_debug.log"

# ===================== ЛОКАЛИЗАЦИЯ / LOCALIZATION =====================
SUPPORTED_LANGUAGES = ["ru", "en"]
current_language = "ru"

def detect_system_language():
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary_lang = lang_id & 0x3FF
        LANG_RUSSIAN = 0x19
        return "ru" if primary_lang == LANG_RUSSIAN else "en"
    except Exception:
        return "en"

TRANSLATIONS = {
    "ru": {
        "lang_name": "Русский",
        "mode_standard_name": "Стандартный",
        "mode_gaming_name": "Игровой",
        "dimming_off": "Выкл", "dimming_off_desc": "Local Dimming выключен",
        "dimming_low": "Низкий", "dimming_low_desc": "Низкий уровень",
        "dimming_medium": "Средний", "dimming_medium_desc": "Средний уровень",
        "dimming_medium_plus": "Средний+", "dimming_medium_plus_desc": "Повышенный средний уровень",
        "dimming_high": "Высокий", "dimming_high_desc": "Максимальный уровень",
        "dimming_unknown": "Неизвестно",
        "notif_hdr_enabled": "⚠️ Включен HDR",
        "notif_preset_set": "✅ Цветовой пресет {preset} установлен",
        "notif_preset_not_supported": "❌ Пресет {preset} не поддерживается в HDR",
        "notif_preset_may_not_work": "⚠️ Пресет {preset} может не работать в HDR",
        "notif_mode": "Режим: {mode}",
        "notif_hotkey": "Горячая клавиша: {hotkey}",
        "notif_hotkey_fail": "❌ Не удалось зарегистрировать горячую клавишу",
        "notif_settings_saved": "Настройки сохранены",
        "notif_error": "Ошибка: {error}",
        "notif_save_error": "Ошибка сохранения: {error}",
        "notif_delay_field_error": "Ошибка в поле задержки: {error}",
        "notif_restart_required": "Язык изменён. Перезапустите программу, чтобы применить изменения полностью.",
        "err_brightness_range": "Яркость должна быть от 0 до 100",
        "err_select_dimming": "Выберите режим локального затемнения",
        "err_preset_range": "Номер пресета должен быть от 0 до 255",
        "err_delay_min": "Задержка должна быть не менее 1 секунды",
        "err_delay_max": "Задержка не должна превышать 60 секунд",
        "settings_title": "Настройки",
        "settings_auto_switch": "Автоматическое переключение игровых режимов",
        "settings_media_players": "Включать медиаплееры (MPC, VLC, PotPlayer) в игровой режим",
        "settings_media_delay_label": "Задержка перед переключением для медиаплееров (сек):",
        "settings_range_1_60": "(1-60)",
        "settings_standard_mode": "Стандартный режим (SDR)",
        "settings_gaming_mode": "Игровой режим (SDR)",
        "settings_brightness_label": "Яркость (0-100):",
        "settings_dimming_label": "Локальное затемнение:",
        "settings_hdr_group": "Настройки HDR",
        "settings_advanced_settings": "Дополнительные настройки",
        "settings_debug_group": "Отладка",
        "settings_debug_enable": "Включить debug (запись лога в файл)",
        "settings_debug_file_label": "Файл лога: {file}",
        "settings_hdr_autoset": "Устанавливать цветовой пресет при нажатии горячей клавиши (если HDR включен)",
        "settings_hdr_autoset_warning": "⚠️ Внимание: неправильный номер пресета может исказить цвета и потребовать сброса монитора к заводским настройкам. Убедитесь, что знаете поддерживаемые значения для вашего монитора.",
        "settings_hdr_preset_label": "Номер цветового пресета (0-255):",
        "settings_hotkey_group": "Горячая клавиша переключения режима",
        "settings_hotkey_record": "Записать новую комбинацию",
        "settings_hotkey_cancel_record": "Отмена записи",
        "settings_hotkey_hint": "Любое сочетание клавиш (Ctrl/Alt/Shift + клавиша), кроме клавиши Win.",
        "settings_hotkey_win_forbidden": "Клавиша Win запрещена — попробуйте ещё раз",
        "settings_hotkey_need_modifier": "Добавьте Ctrl/Alt/Shift и обычную клавишу",
        "settings_hotkey_press_combo": "Нажмите комбинацию клавиш (кроме Win)...",
        "settings_language_group": "Язык / Language",
        "btn_save": "Сохранить",
        "btn_cancel": "Отмена",
        "btn_close": "Закрыть",
        "about_title": "О программе",
        "about_app_title": "Переключение режимов монитора",
        "about_hotkey": "Горячая клавиша: {hotkey}",
        "about_current_settings": "Текущие настройки (SDR):",
        "about_standard_line": "• Стандартный: {dimming} ({value}), яркость {brightness}",
        "about_gaming_line": "• Игровой: {dimming} ({value}), яркость {brightness}",
        "about_excluded_title": "Исключены из определения игр:",
        "about_excluded_list": "Wallpaper Engine, Chrome, Firefox, Edge, Brave, Opera, Проводник,\ncmd, powershell, notepad, mspaint",
        "about_version": "Версия: {version}",
        "menu_about": "О программе",
        "menu_settings": "Настройки",
        "menu_exit": "Закрыть",
        "tray_title": "Режим {mode}",
        "console_start": "=== Запуск программы ===",
        "console_standard": "Стандартный: LD {dimming}, яркость {brightness}",
        "console_gaming": "Игровой: LD {dimming}, яркость {brightness}",
        "console_hdr": "HDR: автоустановка={auto}, пресет={preset}",
        "console_auto_switch": "Авто-переключение: {state}",
        "console_media": "Учёт медиаплееров: {state}",
        "console_media_delay": "Задержка медиаплееров: {delay} сек",
        "console_debug": "Режим отладки: {state}",
        "console_hotkey": "Горячая клавиша: {hotkey}",
        "console_on": "включено", "console_off": "выключено",
        "console_enabled": "включён", "console_disabled": "выключен",
        "console_debug_on": "ВКЛЮЧЁН", "console_debug_off": "ВЫКЛЮЧЕН",
        "console_started": "\nПрограмма запущена. Текущий режим: {mode}",
        "console_auto_active": "Автоматическое переключение активно (проверка каждую секунду)",
        "console_media_on": "Учёт медиаплееров включён, задержка {delay} сек",
        "console_media_off": "Учёт медиаплееров выключен",
        "console_auto_off": "Автоматическое переключение отключено",
        "console_excluded": "Исключены из определения игр: Wallpaper Engine, браузеры, Проводник, консоль, блокнот и др.",
        "console_manual_toggle": "Ручное переключение ({hotkey}) включает/выключает авто-режим",
    },
    "en": {
        "lang_name": "English",
        "mode_standard_name": "Standard",
        "mode_gaming_name": "Gaming",
        "dimming_off": "Off", "dimming_off_desc": "Local Dimming disabled",
        "dimming_low": "Low", "dimming_low_desc": "Low level",
        "dimming_medium": "Medium", "dimming_medium_desc": "Medium level",
        "dimming_medium_plus": "Medium+", "dimming_medium_plus_desc": "Increased medium level",
        "dimming_high": "High", "dimming_high_desc": "Maximum level",
        "dimming_unknown": "Unknown",
        "notif_hdr_enabled": "⚠️ HDR is enabled",
        "notif_preset_set": "✅ Color preset {preset} applied",
        "notif_preset_not_supported": "❌ Preset {preset} is not supported in HDR",
        "notif_preset_may_not_work": "⚠️ Preset {preset} may not work in HDR",
        "notif_mode": "Mode: {mode}",
        "notif_hotkey": "Hotkey: {hotkey}",
        "notif_hotkey_fail": "❌ Failed to register hotkey",
        "notif_settings_saved": "Settings saved",
        "notif_error": "Error: {error}",
        "notif_save_error": "Save error: {error}",
        "notif_delay_field_error": "Error in delay field: {error}",
        "notif_restart_required": "Language changed. Restart the program to fully apply the change.",
        "err_brightness_range": "Brightness must be between 0 and 100",
        "err_select_dimming": "Please select a local dimming mode",
        "err_preset_range": "Preset number must be between 0 and 255",
        "err_delay_min": "Delay must be at least 1 second",
        "err_delay_max": "Delay must not exceed 60 seconds",
        "settings_title": "Settings",
        "settings_auto_switch": "Automatic game mode switching",
        "settings_media_players": "Treat media players (MPC, VLC, PotPlayer) as gaming mode",
        "settings_media_delay_label": "Delay before switching for media players (sec):",
        "settings_range_1_60": "(1-60)",
        "settings_standard_mode": "Standard mode (SDR)",
        "settings_gaming_mode": "Gaming mode (SDR)",
        "settings_brightness_label": "Brightness (0-100):",
        "settings_dimming_label": "Local dimming:",
        "settings_hdr_group": "HDR settings",
        "settings_advanced_settings": "Advanced settings",
        "settings_debug_group": "Debug",
        "settings_debug_enable": "Enable debug (write log to file)",
        "settings_debug_file_label": "Log file: {file}",
        "settings_hdr_autoset": "Set color preset on hotkey press (if HDR is enabled)",
        "settings_hdr_autoset_warning": "⚠️ Warning: incorrect preset number may distort colors and require factory reset of the monitor. Make sure you know the supported values for your monitor.",
        "settings_hdr_preset_label": "Color preset number (0-255):",
        "settings_hotkey_group": "Mode switch hotkey",
        "settings_hotkey_record": "Record new combination",
        "settings_hotkey_cancel_record": "Cancel recording",
        "settings_hotkey_hint": "Any key combination (Ctrl/Alt/Shift + key), except the Win key.",
        "settings_hotkey_win_forbidden": "The Win key is not allowed — try again",
        "settings_hotkey_need_modifier": "Add Ctrl/Alt/Shift and a regular key",
        "settings_hotkey_press_combo": "Press a key combination (except Win)...",
        "settings_language_group": "Язык / Language",
        "btn_save": "Save",
        "btn_cancel": "Cancel",
        "btn_close": "Close",
        "about_title": "About",
        "about_app_title": "Monitor Mode Switcher",
        "about_hotkey": "Hotkey: {hotkey}",
        "about_current_settings": "Current settings (SDR):",
        "about_standard_line": "• Standard: {dimming} ({value}), brightness {brightness}",
        "about_gaming_line": "• Gaming: {dimming} ({value}), brightness {brightness}",
        "about_excluded_title": "Excluded from game detection:",
        "about_excluded_list": "Wallpaper Engine, Chrome, Firefox, Edge, Brave, Opera, Explorer,\ncmd, powershell, notepad, mspaint",
        "about_version": "Version: {version}",
        "menu_about": "About",
        "menu_settings": "Settings",
        "menu_exit": "Exit",
        "tray_title": "Mode {mode}",
        "console_start": "=== Program starting ===",
        "console_standard": "Standard: LD {dimming}, brightness {brightness}",
        "console_gaming": "Gaming: LD {dimming}, brightness {brightness}",
        "console_hdr": "HDR: auto-set={auto}, preset={preset}",
        "console_auto_switch": "Auto-switch: {state}",
        "console_media": "Media player detection: {state}",
        "console_media_delay": "Media player delay: {delay} sec",
        "console_debug": "Debug mode: {state}",
        "console_hotkey": "Hotkey: {hotkey}",
        "console_on": "enabled", "console_off": "disabled",
        "console_enabled": "enabled", "console_disabled": "disabled",
        "console_debug_on": "ON", "console_debug_off": "OFF",
        "console_started": "\nProgram started. Current mode: {mode}",
        "console_auto_active": "Automatic switching is active (checking every second)",
        "console_media_on": "Media player detection enabled, delay {delay} sec",
        "console_media_off": "Media player detection disabled",
        "console_auto_off": "Automatic switching is disabled",
        "console_excluded": "Excluded from game detection: Wallpaper Engine, browsers, Explorer, console, notepad, etc.",
        "console_manual_toggle": "Manual toggle ({hotkey}) turns auto-mode on/off",
    },
}

def t(key, **kwargs):
    lang_dict = TRANSLATIONS.get(current_language, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

def get_default_modes():
    return [
        {"name": t("mode_standard_name"), "local_dimming": 2, "brightness": 20},
        {"name": t("mode_gaming_name"), "local_dimming": 3, "brightness": 36}
    ]

def get_local_dimming_options():
    return [
        {"value": 2, "name": t("dimming_off"), "description": t("dimming_off_desc")},
        {"value": 3, "name": t("dimming_low"), "description": t("dimming_low_desc")},
        {"value": 5, "name": t("dimming_medium"), "description": t("dimming_medium_desc")},
        {"value": 4, "name": t("dimming_medium_plus"), "description": t("dimming_medium_plus_desc")},
        {"value": 6, "name": t("dimming_high"), "description": t("dimming_high_desc")}
    ]

# ===================== WINAPI =====================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

HOTKEY_ID = 1
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_Z = 0x5A

DEFAULT_HOTKEY_MOD = MOD_CONTROL | MOD_ALT
DEFAULT_HOTKEY_VK = VK_Z
HOTKEY_MODIFIERS = DEFAULT_HOTKEY_MOD
HOTKEY_VK = DEFAULT_HOTKEY_VK

WM_APP = 0x8000
WM_UPDATE_HOTKEY = WM_APP + 1
pending_hotkey_mod = HOTKEY_MODIFIERS
pending_hotkey_vk = HOTKEY_VK

WS_CAPTION = 0x00C00000
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

VCP_MODE_SWITCH = 0xE0
VCP_LOCAL_DIMMING = 0x99
VCP_LOCAL_DIMMING_ALT = 0x47
VCP_BRIGHTNESS = 0x10
VCP_COLOR_PRESET = 0x14

current_mode_index = 0
last_switch_time = 0
DELAY = 1

# Ручной режим
manual_override_active = False
manual_override_waiting = False

modes = []
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
media_delay_seconds = 2

tk_queue = queue.Queue()
active_connections = 0
connections_lock = threading.Lock()

game_counter = 0
GAME_THRESHOLD = 2
game_window_hwnd = None
media_timer = None
media_timer_lock = threading.Lock()
last_reported_state = None
last_excluded_process_logged = None  # чтобы не спамить лог одним и тем же исключённым процессом

hdr_status_cache = None
hdr_cache_time = 0
HDR_CACHE_TIME = 2
hdr_cache_lock = threading.Lock()

# Подтверждённый HDR (именно HDR, не ошибка чтения) запоминается на всю
# игровую/медиа-сессию, чтобы не долбить DDC/CI каждую секунду.
# Сбрасывается при закрытии игры/медиаплеера или при ручной попытке
# переключения режима (хоткей всегда делает force_refresh и сам сбросит флаг).
confirmed_hdr_active = False

MEDIA_PLAYER_PROCESSES = [
    "mpc-hc.exe", "mpc-be.exe", "mpc-hc64.exe", "mpc-be64.exe",
    "vlc.exe", "potplayer.exe", "kmplayer.exe", "mediaplayerclassic.exe"
]

EXCLUDED_PROCESSES = [
    "wallpaper32.exe", "wallpaper64.exe", "chrome.exe", "firefox.exe",
    "msedge.exe", "brave.exe", "opera.exe", "explorer.exe", "StartMenuExperienceHost.exe",
    "cmd.exe", "powershell.exe", "notepad.exe", "mspaint.exe"
]

def is_debug_active():
    return advanced_settings_enabled and debug_enabled

def log(msg):
    if is_debug_active():
        print(msg)
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {msg}\n")
        except Exception:
            pass

def get_key_name(vk_code):
    try:
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        lparam = (scan_code & 0xFF) << 16
        buffer = ctypes.create_unicode_buffer(64)
        result = user32.GetKeyNameTextW(lparam, buffer, 64)
        if result > 0 and buffer.value:
            return buffer.value
    except Exception as e:
        log(f"Ошибка получения имени клавиши: {e}")
    return f"VK_{vk_code:02X}"

def hotkey_to_string(mod, vk):
    parts = []
    if mod & MOD_CONTROL:
        parts.append("Ctrl")
    if mod & MOD_ALT:
        parts.append("Alt")
    if mod & MOD_SHIFT:
        parts.append("Shift")
    parts.append(get_key_name(vk))
    return "+".join(parts)

def request_hotkey_update(new_mod, new_vk):
    global pending_hotkey_mod, pending_hotkey_vk
    pending_hotkey_mod = new_mod
    pending_hotkey_vk = new_vk
    if hotkey_thread_id:
        try:
            user32.PostThreadMessageW(hotkey_thread_id, WM_UPDATE_HOTKEY, 0, 0)
        except Exception as e:
            log(f"Ошибка отправки сообщения об обновлении горячей клавиши: {e}")

def load_settings():
    global modes, hdr_settings, auto_switch_enabled, media_players_enabled, media_delay_seconds
    global HOTKEY_MODIFIERS, HOTKEY_VK, current_language, advanced_settings_enabled, debug_enabled
    language_loaded = False
    modes_loaded = False
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'language' in data and data['language'] in SUPPORTED_LANGUAGES:
                    current_language = data['language']
                    language_loaded = True
                if 'modes' in data and isinstance(data['modes'], list) and len(data['modes']) == 2:
                    modes = data['modes']
                    modes_loaded = True
                if 'hdr_settings' in data:
                    hdr_settings.update(data['hdr_settings'])
                if 'auto_switch_enabled' in data:
                    auto_switch_enabled = data['auto_switch_enabled']
                if 'media_players_enabled' in data:
                    media_players_enabled = data['media_players_enabled']
                if 'media_delay_seconds' in data:
                    media_delay_seconds = data['media_delay_seconds']
                if 'advanced_settings_enabled' in data:
                    advanced_settings_enabled = data['advanced_settings_enabled']
                if 'debug_enabled' in data:
                    debug_enabled = data['debug_enabled']
                if 'hotkey_modifiers' in data and 'hotkey_vk' in data:
                    mod_val = data['hotkey_modifiers']
                    vk_val = data['hotkey_vk']
                    if isinstance(mod_val, int) and isinstance(vk_val, int) and not (mod_val & MOD_WIN):
                        HOTKEY_MODIFIERS = mod_val
                        HOTKEY_VK = vk_val
                        log(f"Горячая клавиша загружена: {hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)}")
    except Exception as e:
        log(f"Ошибка загрузки: {e}")

    if not language_loaded:
        current_language = detect_system_language()
        log(f"Язык определён автоматически: {current_language}")

    if not modes_loaded:
        modes = get_default_modes()

def save_settings():
    try:
        data = {
            'language': current_language,
            'modes': modes,
            'hdr_settings': hdr_settings,
            'auto_switch_enabled': auto_switch_enabled,
            'media_players_enabled': media_players_enabled,
            'media_delay_seconds': media_delay_seconds,
            'advanced_settings_enabled': advanced_settings_enabled,
            'debug_enabled': debug_enabled,
            'hotkey_modifiers': HOTKEY_MODIFIERS,
            'hotkey_vk': HOTKEY_VK
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log("Настройки сохранены")
        return True
    except Exception as e:
        log(f"Ошибка сохранения: {e}")
        return False

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
    global hdr_status_cache, hdr_cache_time
    with hdr_cache_lock:
        now = time.time()
        if force_refresh or hdr_status_cache is None or (now - hdr_cache_time) >= HDR_CACHE_TIME:
            def check_hdr(monitor):
                try:
                    current_brightness, max_brightness = monitor.vcp.get_vcp_feature(VCP_BRIGHTNESS)
                    return "hdr" if current_brightness == 100 else "ok"
                except Exception as e:
                    log(f"Ошибка чтения яркости: {e}")
                    return "error"
            result = safe_monitor_operation(check_hdr)
            if result is None:
                result = "error"
            hdr_status_cache = result
            hdr_cache_time = now
        return hdr_status_cache

def is_hdr_blocked(force_refresh=False):
    """Возвращает True, если переключение режима должно быть заблокировано:
    либо подтверждён HDR (значение "hdr"), либо не удалось прочитать
    яркость (значение "error"). В обоих случаях итог для вызывающего кода
    одинаковый (блокировка), но кэшировать на всю сессию можно только
    подтверждённый HDR — ошибка чтения не является подтверждением."""
    result = is_hdr_enabled(force_refresh=force_refresh)
    return result in ("hdr", "error"), result

def reset_confirmed_hdr():
    global confirmed_hdr_active
    if confirmed_hdr_active:
        log("Сброс запомненного состояния HDR")
    confirmed_hdr_active = False

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
    # ВАЖНО: режим считается полностью применённым, только если ОБА параметра
    # (яркость и локальное затемнение) реально выставлены. Раньше здесь было
    # "or", из-за чего частичный успех (например, только яркость) засчитывался
    # как полное применение режима, а local dimming мог молча остаться от
    # предыдущего режима без каких-либо дальнейших попыток его исправить.
    return (success_dimming and success_brightness), success_dimming, success_brightness

def retry_brightness_only(mode_index, attempts=5, delay=0.5):
    mode = modes[mode_index]
    for attempt in range(attempts):
        time.sleep(delay)
        if current_mode_index != mode_index:
            log("Дожим яркости отменён: режим уже изменился")
            return
        # Проверяем текущую яркость
        current_brightness, _ = get_current_monitor_settings()
        if current_brightness is not None and current_brightness == mode["brightness"]:
            log(f"Яркость уже {mode['brightness']}, дожим не требуется")
            return
        def set_brightness(monitor):
            try:
                monitor.vcp.set_vcp_feature(VCP_BRIGHTNESS, mode["brightness"])
                return True
            except Exception as e:
                log(f"Дожим яркости (попытка {attempt+1}/{attempts}): {e}")
                return False
        if safe_monitor_operation(set_brightness):
            log(f"Яркость {mode['brightness']} дожата успешно (попытка {attempt+1}/{attempts})")
            return
    log("Не удалось дожать яркость после дополнительных попыток")

def retry_dimming_only(mode_index, attempts=5, delay=0.5):
    mode = modes[mode_index]
    for attempt in range(attempts):
        time.sleep(delay)
        if current_mode_index != mode_index:
            log("Дожим LD отменён: режим уже изменился")
            return
        # Проверяем текущее значение local dimming
        _, current_local_dimming = get_current_monitor_settings()
        if current_local_dimming is not None and current_local_dimming == mode["local_dimming"]:
            log(f"LD уже {mode['local_dimming']}, дожим не требуется")
            return
        def set_dimming(monitor):
            return set_local_dimming(monitor, mode["local_dimming"])
        if safe_monitor_operation(set_dimming):
            log(f"LD {mode['local_dimming']} дожат успешно (попытка {attempt+1}/{attempts})")
            return
    log("Не удалось дожать LD после дополнительных попыток")

def apply_mode_by_index(index, force_hdr_check=False):
    global current_mode_index, tray_icon, last_excluded_process_logged
    global confirmed_hdr_active
    if current_mode_index == index:
        return True

    # Если HDR уже был подтверждён ранее в этой же игровой/медиа-сессии и
    # сессия ещё не сбрасывалась (игра не закрыта, ручного переключения не
    # было) – не дёргаем DDC/CI повторно, а сразу считаем переключение
    # заблокированным.
    if confirmed_hdr_active and not force_hdr_check:
        log("HDR ранее подтверждён в этой сессии – переключение заблокировано (без опроса монитора)")
        return False

    blocked, hdr_check = is_hdr_blocked(force_refresh=force_hdr_check)
    if blocked:
        if hdr_check == "hdr":
            confirmed_hdr_active = True
            log("HDR подтверждён – переключение режимов заблокировано (запомнено до конца сессии)")
        else:
            log("Ошибка чтения яркости – переключение режимов заблокировано (не запоминается)")
        return False

    # Свежая проверка (обычно force_hdr_check=True) подтвердила, что HDR не
    # активен – если флаг оставался True с прошлого раза, снимаем его, иначе
    # он "залипнет" и будет блокировать следующие попытки без опроса монитора.
    if confirmed_hdr_active:
        confirmed_hdr_active = False
        log("Свежая проверка не подтвердила HDR – запомненное состояние снято")

    success_dimming = False
    success_brightness = False
    for attempt in range(3):
        log(f"Попытка переключения на режим {index} (шаг {attempt+1}/3)")
        apply_success, success_dimming, success_brightness = apply_mode_settings(index)
        if apply_success:
            break
        log(f"Режим {index} применён не полностью (LD={success_dimming}, яркость={success_brightness}), попытка {attempt+1}/3")
        if attempt < 2:
            time.sleep(1)

    if not success_dimming and not success_brightness:
        log(f"Не удалось переключить на режим {index} после 3 попыток")
        return False

    # Хотя бы один из параметров (яркость или LD) выставлен успешно.
    # Считаем режим применённым, а недостающий параметр дожимаем в фоне,
    # чтобы он не "залипал" на значении от предыдущего режима.
    current_mode_index = index
    last_excluded_process_logged = None  # после смены режима разрешаем залогировать исключённый процесс заново
    if not success_brightness:
        threading.Thread(target=retry_brightness_only, args=(index,), daemon=True).start()
    if not success_dimming:
        threading.Thread(target=retry_dimming_only, args=(index,), daemon=True).start()
    if tray_icon:
        try:
            tray_icon.title = t("tray_title", mode=modes[current_mode_index]['name'])
        except:
            pass
    show_notification(t("notif_mode", mode=modes[current_mode_index]['name']))
    return True

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
    global last_excluded_process_logged
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
    covers_most = (width_ratio >= 0.90 and height_ratio >= 0.90)
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
            if process_name != last_excluded_process_logged:
                log(f"Исключён процесс {process_name}")
                last_excluded_process_logged = process_name
            return False
    if not is_game and media_players_enabled:
        if process_name and process_name.lower() in [m.lower() for m in MEDIA_PLAYER_PROCESSES]:
            media_covers = (width_ratio >= 0.70 and height_ratio >= 0.70)
            if media_covers:
                log(f"Медиаплеер {process_name} – игровой режим")
                return True
    return is_game

def delayed_media_switch(hwnd):
    global media_timer, game_window_hwnd, last_reported_state, confirmed_hdr_active
    with media_timer_lock:
        media_timer = None
    if confirmed_hdr_active:
        log("HDR ранее подтверждён в этой сессии – переключение медиаплеера отменено (без опроса монитора)")
        return
    blocked, hdr_check = is_hdr_blocked()
    if blocked:
        if hdr_check == "hdr":
            confirmed_hdr_active = True
            log("HDR подтверждён – переключение медиаплеера отменено (запомнено до конца сессии)")
        else:
            log("Ошибка чтения яркости – переключение медиаплеера отменено")
        return
    if not user32.IsWindow(hwnd):
        log("Медиаплеер закрыт до срабатывания таймера – отмена")
        return
    if not is_game_window(hwnd):
        log("Окно перестало быть медиаплеером за время задержки – отмена")
        return
    blocked, hdr_check = is_hdr_blocked(force_refresh=True)
    if blocked:
        if hdr_check == "hdr":
            confirmed_hdr_active = True
            log("HDR включился перед финальным переключением – отмена (запомнено до конца сессии)")
        else:
            log("Ошибка чтения яркости перед финальным переключением – отмена")
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

def monitor_loop():
    global current_mode_index, stop_hotkey_thread, game_counter, game_window_hwnd
    global auto_switch_enabled, media_timer, media_delay_seconds, last_reported_state
    global manual_override_active, manual_override_waiting
    global confirmed_hdr_active

    while not stop_hotkey_thread:
        try:
            if not auto_switch_enabled:
                time.sleep(1)
                continue

            hwnd = user32.GetForegroundWindow()

            # ==================== РУЧНОЙ РЕЖИМ ====================
            if manual_override_active:
                if game_window_hwnd is None:
                    if manual_override_waiting:
                        if hwnd and is_game_window(hwnd):
                            game_window_hwnd = hwnd
                            manual_override_waiting = False
                            log(f"[Ручной режим] Запомнено игровое окно {hex(hwnd)}")
                    else:
                        manual_override_waiting = True
                        log("[Ручной режим] Нет запомненного окна, переходим в ожидание")
                else:
                    if not user32.IsWindow(game_window_hwnd):
                        log(f"[Ручной режим] Окно {hex(game_window_hwnd)} закрыто – сброс")
                        manual_override_active = False
                        manual_override_waiting = False
                        game_window_hwnd = None
                        last_reported_state = None
                        game_counter = 0
                        reset_confirmed_hdr()
                        if current_mode_index != 0:
                            apply_mode_by_index(0)
                        time.sleep(1)
                        continue
                    # Окно существует, ручной режим остаётся активным
                # Пропускаем авто-переключения
                time.sleep(1)
                continue

            # ==================== СТАНДАРТНАЯ АВТО-ЛОГИКА ====================
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
                        elif confirmed_hdr_active:
                            pass  # HDR уже подтверждён в этой сессии – не опрашиваем монитор повторно
                        else:
                            blocked, hdr_check = is_hdr_blocked()
                            if blocked:
                                if hdr_check == "hdr":
                                    confirmed_hdr_active = True
                                    log("HDR подтверждён – медиаплеер не активирует игровой режим (запомнено до конца сессии)")
                                else:
                                    log("Ошибка чтения яркости – медиаплеер не активирует игровой режим")
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
                # Сбрасываем запомненный HDR, только когда игра/медиаплеер
                # действительно перестали определяться (счётчик выбрал
                # весь запас), а не на каждый одиночный alt-tab.
                if game_counter == 0:
                    reset_confirmed_hdr()
                with media_timer_lock:
                    if media_timer is not None:
                        media_timer.cancel()
                        media_timer = None
                        log("Активное окно не игра – таймер медиа отменён")

                if game_window_hwnd is not None:
                    if not user32.IsWindow(game_window_hwnd):
                        log("Игра закрыта (окно уничтожено) – возврат стандартного режима")
                        reset_confirmed_hdr()  # окно закрыто – однозначный конец сессии
                        if apply_mode_by_index(0):
                            game_window_hwnd = None
                            last_reported_state = False
                    else:
                        if last_reported_state != True:
                            log("Игра уже запущена (свёрнута) – переключаем на игровой")
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

        time.sleep(1)

# ========== ИСПРАВЛЕННАЯ ФУНКЦИЯ toggle_mode ==========
def toggle_mode(icon=None):
    global current_mode_index, last_switch_time, last_reported_state
    global manual_override_active, manual_override_waiting
    global game_window_hwnd, game_counter, confirmed_hdr_active
    
    now = time.time()
    if now - last_switch_time < DELAY:
        return
    
    try:
        log("\n" + "="*50)
        log("Начало переключения режима")

        # Ручная попытка переключения – всегда делаем свежий опрос монитора
        # и пересматриваем запомненное состояние HDR по его результату,
        # независимо от того, что было запомнено ранее в этой сессии.
        blocked, hdr_check_result = is_hdr_blocked(force_refresh=True)
        confirmed_hdr_active = (hdr_check_result == "hdr")
        if blocked:
            log("HDR включен или ошибка чтения - переключение заблокировано (ручная попытка)")
            show_notification(t("notif_hdr_enabled"))
            return
        
        if monitor_index is None:
            if not find_titan_army_monitor():
                return
        
        sync_current_mode()
        new_mode_index = 1 - current_mode_index
        
        if apply_mode_by_index(new_mode_index, force_hdr_check=True):
            last_switch_time = now
            mode_name = modes[current_mode_index]["name"]
            
            if new_mode_index == 0:
                # Ручное переключение на стандартный
                active_hwnd = user32.GetForegroundWindow()
                if active_hwnd and is_game_window(active_hwnd):
                    # Игра активна – включаем ручной режим с целевым стандартным и запоминаем окно
                    manual_override_active = True
                    game_window_hwnd = active_hwnd
                    manual_override_waiting = False
                    last_reported_state = False
                    log(f"Ручной режим включён (стандартный), запомнено окно игры {hex(active_hwnd)}")
                else:
                    # Игра не активна – выключаем ручной режим полностью
                    manual_override_active = False
                    manual_override_waiting = False
                    game_window_hwnd = None
                    last_reported_state = False
                    log("Ручной режим выключен (переключение на стандартный, игра не активна)")
            else:  # new_mode_index == 1
                # Ручное переключение на игровой
                manual_override_active = True
                log(f"Ручной режим включён, целевой режим: {mode_name}")
                
                active_hwnd = user32.GetForegroundWindow()
                if active_hwnd and is_game_window(active_hwnd):
                    game_window_hwnd = active_hwnd
                    manual_override_waiting = False
                    log(f"Запомнено окно игры {hex(active_hwnd)} для ручного режима")
                else:
                    game_window_hwnd = None
                    manual_override_waiting = True
                    log("Ручной режим включён, игра не запущена – ожидаем появления игры")
                
                last_reported_state = True
            
            show_notification(t("notif_mode", mode=mode_name))
            if icon:
                try:
                    icon.title = t("tray_title", mode=mode_name)
                except Exception:
                    pass
        
        log("="*50)
    except Exception as e:
        log(f"Ошибка переключения: {e}")

# ========== КОНЕЦ ИЗМЕНЕНИЙ ==========

def get_local_dimming_name(value):
    for option in get_local_dimming_options():
        if option["value"] == value:
            return option["name"]
    return t("dimming_unknown")

def create_settings_window():
    def create_window():
        new_hotkey_mod = HOTKEY_MODIFIERS
        new_hotkey_vk = HOTKEY_VK
        recording_modifiers = set()

        def save_all_settings():
            nonlocal auto_switch_var, media_players_var, media_delay_var
            nonlocal new_hotkey_mod, new_hotkey_vk
            try:
                standard_brightness = int(standard_brightness_entry.get())
                if not (0 <= standard_brightness <= 100):
                    raise ValueError(t("err_brightness_range"))
                standard_dimming = standard_dimming_var.get()
                if standard_dimming == 0:
                    raise ValueError(t("err_select_dimming"))
                gaming_brightness = int(gaming_brightness_entry.get())
                if not (0 <= gaming_brightness <= 100):
                    raise ValueError(t("err_brightness_range"))
                gaming_dimming = gaming_dimming_var.get()
                if gaming_dimming == 0:
                    raise ValueError(t("err_select_dimming"))
                auto_set_preset = auto_set_var.get()
                preset_number = int(preset_entry.get())
                if not (0 <= preset_number <= 255):
                    raise ValueError(t("err_preset_range"))
                try:
                    delay_val = int(media_delay_var.get())
                    if delay_val < 1:
                        raise ValueError(t("err_delay_min"))
                    if delay_val > 60:
                        raise ValueError(t("err_delay_max"))
                except ValueError as e:
                    show_notification(t("notif_delay_field_error", error=e))
                    return

                global auto_switch_enabled, media_players_enabled, media_delay_seconds
                auto_switch_enabled = auto_switch_var.get()
                media_players_enabled = media_players_var.get()
                media_delay_seconds = delay_val

                global advanced_settings_enabled, debug_enabled
                advanced_settings_enabled = advanced_var.get()
                debug_enabled = debug_var.get()

                modes[0]["brightness"] = standard_brightness
                modes[0]["local_dimming"] = standard_dimming
                modes[1]["brightness"] = gaming_brightness
                modes[1]["local_dimming"] = gaming_dimming
                hdr_settings["auto_set_preset"] = auto_set_preset
                hdr_settings["preset_number"] = preset_number

                global HOTKEY_MODIFIERS, HOTKEY_VK
                hotkey_changed = (new_hotkey_mod != HOTKEY_MODIFIERS) or (new_hotkey_vk != HOTKEY_VK)
                if hotkey_changed:
                    HOTKEY_MODIFIERS, HOTKEY_VK = new_hotkey_mod, new_hotkey_vk
                    request_hotkey_update(new_hotkey_mod, new_hotkey_vk)

                global current_language
                selected_lang_code = language_code_by_name.get(language_var.get(), current_language)
                language_changed = selected_lang_code != current_language
                if language_changed:
                    current_language = selected_lang_code

                if save_settings():
                    show_notification(t("notif_settings_saved"))
                    blocked, hdr_check = is_hdr_blocked(force_refresh=True)
                    if not blocked:
                        apply_mode_settings(current_mode_index)

                if language_changed:
                    rebuild_tray_menu()
                    show_notification(t("notif_restart_required"))

                if auto_switch_enabled:
                    def check_now():
                        hwnd = user32.GetForegroundWindow()
                        if hwnd and is_game_window(hwnd):
                            log("Авто-переключение включено – игра/медиаплеер активна, переключаем")
                            apply_mode_by_index(1, force_hdr_check=True)
                    threading.Thread(target=check_now, daemon=True).start()

                window.destroy()
            except ValueError as e:
                show_notification(t("notif_error", error=str(e)))
            except Exception as e:
                show_notification(t("notif_save_error", error=e))

        def on_cancel():
            window.destroy()

        def on_standard_dimming_select():
            selected_value = standard_dimming_var.get()
            for option in get_local_dimming_options():
                if option["value"] == selected_value:
                    standard_desc_label.config(text=option["description"])
                    break

        def on_gaming_dimming_select():
            selected_value = gaming_dimming_var.get()
            for option in get_local_dimming_options():
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
        window.title(t("settings_title"))
        win_width = 600
        win_height = 920
        window.update_idletasks()
        max_height = window.winfo_screenheight() - 80
        win_height = min(win_height, max_height)
        window.geometry(f"{win_width}x{win_height}")
        window.resizable(False, False)
        x = (window.winfo_screenwidth() - win_width) // 2
        y = (window.winfo_screenheight() - win_height) // 2
        window.geometry(f"+{x}+{y}")

        canvas = tk.Canvas(window)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        main_frame = ttk.Frame(scrollable_frame, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # -------- Авто-переключение --------
        auto_switch_var = tk.BooleanVar(value=auto_switch_enabled)
        auto_switch_check = ttk.Checkbutton(
            main_frame,
            text=t("settings_auto_switch"),
            variable=auto_switch_var,
            command=toggle_media_players_state
        )
        auto_switch_check.pack(anchor=tk.W, pady=(0, 5))

        media_players_var = tk.BooleanVar(value=media_players_enabled)
        media_players_check = ttk.Checkbutton(
            main_frame,
            text=t("settings_media_players"),
            variable=media_players_var,
            command=toggle_media_delay_state
        )
        media_players_check.pack(anchor=tk.W, pady=(0, 5))

        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 15))
        ttk.Label(delay_frame, text=t("settings_media_delay_label")).pack(side=tk.LEFT, padx=(0, 5))
        media_delay_var = tk.StringVar(value=str(media_delay_seconds))
        media_delay_entry = ttk.Entry(delay_frame, width=10, textvariable=media_delay_var)
        media_delay_entry.pack(side=tk.LEFT)
        ttk.Label(delay_frame, text=t("settings_range_1_60")).pack(side=tk.LEFT, padx=5)

        if not (auto_switch_var.get() and media_players_var.get()):
            media_delay_entry.config(state="disabled")

        auto_switch_var.trace('w', toggle_media_players_state)
        media_players_var.trace('w', toggle_media_delay_state)

        # -------- Стандартный режим --------
        standard_frame = ttk.LabelFrame(main_frame, text=t("settings_standard_mode"), padding="10")
        standard_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(standard_frame, text=t("settings_brightness_label")).pack(anchor=tk.W, pady=(0, 5))
        standard_brightness_entry = ttk.Entry(standard_frame, width=20)
        standard_brightness_entry.insert(0, str(modes[0]["brightness"]))
        standard_brightness_entry.pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(standard_frame, text=t("settings_dimming_label"), font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        standard_dimming_var = tk.IntVar(value=modes[0]["local_dimming"])
        radio_frame_standard = ttk.Frame(standard_frame)
        radio_frame_standard.pack(anchor=tk.W, fill=tk.X)
        for i, option in enumerate(get_local_dimming_options()):
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

        # -------- Игровой режим --------
        gaming_frame = ttk.LabelFrame(main_frame, text=t("settings_gaming_mode"), padding="10")
        gaming_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(gaming_frame, text=t("settings_brightness_label")).pack(anchor=tk.W, pady=(0, 5))
        gaming_brightness_entry = ttk.Entry(gaming_frame, width=20)
        gaming_brightness_entry.insert(0, str(modes[1]["brightness"]))
        gaming_brightness_entry.pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(gaming_frame, text=t("settings_dimming_label"), font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        gaming_dimming_var = tk.IntVar(value=modes[1]["local_dimming"])
        radio_frame_gaming = ttk.Frame(gaming_frame)
        radio_frame_gaming.pack(anchor=tk.W, fill=tk.X)
        for i, option in enumerate(get_local_dimming_options()):
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

        # -------- Дополнительные настройки (чекбокс) --------
        advanced_frame = ttk.Frame(main_frame)
        advanced_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 5))
        advanced_var = tk.BooleanVar(value=advanced_settings_enabled)
        advanced_check = ttk.Checkbutton(
            advanced_frame,
            text=t("settings_advanced_settings"),
            variable=advanced_var,
            command=lambda: toggle_advanced_container()
        )
        advanced_check.pack(anchor=tk.W)

        # Контейнер для скрываемых настроек
        advanced_container = ttk.Frame(main_frame)

        # -------- HDR настройки (внутри контейнера) --------
        hdr_frame = ttk.LabelFrame(advanced_container, text=t("settings_hdr_group"), padding="10")
        hdr_frame.pack(fill=tk.X, pady=(0, 15))

        auto_set_var = tk.BooleanVar(value=hdr_settings["auto_set_preset"])
        auto_set_check = ttk.Checkbutton(
            hdr_frame,
            text=t("settings_hdr_autoset"),
            variable=auto_set_var)
        auto_set_check.pack(anchor=tk.W, pady=(0, 10))

        warning_label = ttk.Label(hdr_frame, text=t("settings_hdr_autoset_warning"), foreground="orange", wraplength=500)
        warning_label.pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(hdr_frame, text=t("settings_hdr_preset_label")).pack(anchor=tk.W, pady=(0, 5))
        preset_entry = ttk.Entry(hdr_frame, width=20)
        preset_entry.insert(0, str(hdr_settings["preset_number"]))
        preset_entry.pack(anchor=tk.W)

        # -------- Debug настройки (внутри контейнера) --------
        debug_frame = ttk.LabelFrame(advanced_container, text=t("settings_debug_group"), padding="10")
        debug_frame.pack(fill=tk.X, pady=(0, 15))

        debug_var = tk.BooleanVar(value=debug_enabled)
        debug_check = ttk.Checkbutton(
            debug_frame,
            text=t("settings_debug_enable"),
            variable=debug_var)
        debug_check.pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(debug_frame, text=t("settings_debug_file_label", file=DEBUG_LOG_FILE),
                  foreground="gray").pack(anchor=tk.W)

        def toggle_advanced_container():
            if advanced_var.get():
                advanced_container.pack(fill=tk.X, pady=(0, 15), before=language_frame)
            else:
                advanced_container.pack_forget()

        # -------- Язык --------
        language_frame = ttk.LabelFrame(main_frame, text=t("settings_language_group"), padding="10")
        language_frame.pack(fill=tk.X, pady=(0, 15))
        language_names = [TRANSLATIONS[code]["lang_name"] for code in SUPPORTED_LANGUAGES]
        language_code_by_name = {TRANSLATIONS[code]["lang_name"]: code for code in SUPPORTED_LANGUAGES}
        language_var = tk.StringVar(value=TRANSLATIONS[current_language]["lang_name"])
        language_combo = ttk.Combobox(language_frame, textvariable=language_var, values=language_names,
                                       state="readonly", width=20)
        language_combo.pack(anchor=tk.W)

        toggle_advanced_container()

        # -------- Горячая клавиша --------
        hotkey_frame = ttk.LabelFrame(main_frame, text=t("settings_hotkey_group"), padding="10")
        hotkey_frame.configure(takefocus=1)
        hotkey_frame.pack(fill=tk.X, pady=(0, 15))

        hotkey_display_var = tk.StringVar(value=hotkey_to_string(new_hotkey_mod, new_hotkey_vk))
        hotkey_value_label = ttk.Label(hotkey_frame, textvariable=hotkey_display_var, font=('Arial', 10, 'bold'))
        hotkey_value_label.pack(anchor=tk.W, pady=(0, 8))

        def finish_recording():
            hotkey_frame.unbind("<KeyPress>")
            hotkey_frame.unbind("<FocusOut>")
            record_button.config(text=t("settings_hotkey_record"))

        def on_hotkey_key_press(event):
            nonlocal new_hotkey_mod, new_hotkey_vk
            keysym = event.keysym

            if keysym in ("Super_L", "Super_R", "Win_L", "Win_R") or "Win" in keysym:
                hotkey_display_var.set(t("settings_hotkey_win_forbidden"))
                recording_modifiers.clear()
                return "break"

            if keysym in ("Control_L", "Control_R"):
                recording_modifiers.add("ctrl")
            elif keysym in ("Alt_L", "Alt_R"):
                recording_modifiers.add("alt")
            elif keysym in ("Shift_L", "Shift_R"):
                recording_modifiers.add("shift")
            else:
                if not recording_modifiers:
                    hotkey_display_var.set(t("settings_hotkey_need_modifier"))
                    return "break"
                mod_flags = 0
                if "ctrl" in recording_modifiers:
                    mod_flags |= MOD_CONTROL
                if "alt" in recording_modifiers:
                    mod_flags |= MOD_ALT
                if "shift" in recording_modifiers:
                    mod_flags |= MOD_SHIFT
                new_hotkey_mod = mod_flags
                new_hotkey_vk = event.keycode
                hotkey_display_var.set(hotkey_to_string(new_hotkey_mod, new_hotkey_vk))
                recording_modifiers.clear()
                finish_recording()
            return "break"

        def start_recording():
            recording_modifiers.clear()
            hotkey_display_var.set(t("settings_hotkey_press_combo"))
            record_button.config(text=t("settings_hotkey_cancel_record"))
            hotkey_frame.focus_set()
            hotkey_frame.bind("<KeyPress>", on_hotkey_key_press)
            hotkey_frame.bind("<FocusOut>", lambda e: (finish_recording(),
                               hotkey_display_var.set(hotkey_to_string(new_hotkey_mod, new_hotkey_vk))))

        def on_record_button():
            if record_button.cget("text") == t("settings_hotkey_cancel_record"):
                finish_recording()
                hotkey_display_var.set(hotkey_to_string(new_hotkey_mod, new_hotkey_vk))
            else:
                start_recording()

        record_button = ttk.Button(hotkey_frame, text=t("settings_hotkey_record"), command=on_record_button)
        record_button.pack(anchor=tk.W)
        ttk.Label(hotkey_frame,
                  text=t("settings_hotkey_hint"),
                  foreground="gray", wraplength=500).pack(anchor=tk.W, pady=(5, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text=t("btn_save"), command=save_all_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=t("btn_cancel"), command=on_cancel).pack(side=tk.LEFT, padx=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", on_mousewheel)

        window.protocol("WM_DELETE_WINDOW", on_cancel)
        window.focus_force()

    tk_queue.put(('window', create_window))

def set_hdr_color_preset():
    global confirmed_hdr_active
    try:
        log("Проверка HDR для пресета...")
        hdr_check_result = is_hdr_enabled(force_refresh=True)
        # Это тоже ручное действие (хоткей) – обновляем запомненное состояние
        # по свежему результату.
        confirmed_hdr_active = (hdr_check_result == "hdr")
        if hdr_check_result != "hdr":
            log("HDR не включен (или ошибка чтения – не подтверждено, пресет не трогаем)")
            return
        if not (advanced_settings_enabled and hdr_settings["auto_set_preset"]):
            log("Автоустановка пресета отключена (или скрыта в дополнительных настройках)")
            show_notification(t("notif_hdr_enabled"))
            return
        preset_number = hdr_settings["preset_number"]
        log(f"Установка цветового пресета {preset_number}...")
        if preset_number <= 20 and preset_number != 0:
            log(f"Предупреждение: Значение {preset_number} может не подходить для HDR")
            show_notification(t("notif_preset_may_not_work", preset=preset_number))
        def set_color_preset(monitor):
            try:
                monitor.vcp.set_vcp_feature(VCP_COLOR_PRESET, preset_number)
                return True
            except Exception as e:
                log(f"Ошибка установки: {e}")
                return False
        success = safe_monitor_operation(set_color_preset)
        if success:
            show_notification(t("notif_preset_set", preset=preset_number))
        else:
            show_notification(t("notif_preset_not_supported", preset=preset_number))
    except Exception as e:
        log(f"Ошибка: {e}")

def rebuild_tray_menu():
    global tray_icon
    if tray_icon:
        try:
            tray_icon.menu = Menu(
                item(t("menu_about"), on_about),
                item(t("menu_settings"), on_settings),
                item(t("menu_exit"), on_quit)
            )
            tray_icon.title = t("tray_title", mode=modes[current_mode_index]['name'])
        except Exception as e:
            log(f"Ошибка обновления меню трея: {e}")

def on_settings(icon, item):
    create_settings_window()

def on_about(icon, item):
    def create_about_window():
        about_window = tk.Toplevel()
        about_window.title(t("about_title"))
        about_window.geometry("500x460")
        about_window.resizable(False, False)
        about_window.update_idletasks()
        x = (about_window.winfo_screenwidth() - 500) // 2
        y = (about_window.winfo_screenheight() - 460) // 2
        about_window.geometry(f"+{x}+{y}")
        main_frame = ttk.Frame(about_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text=t("about_app_title"), font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        info_text = (
            t("about_hotkey", hotkey=hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)) + "\n\n" +
            t("about_current_settings") + "\n" +
            t("about_standard_line",
              dimming=get_local_dimming_name(modes[0]['local_dimming']),
              value=modes[0]['local_dimming'],
              brightness=modes[0]['brightness']) + "\n" +
            t("about_gaming_line",
              dimming=get_local_dimming_name(modes[1]['local_dimming']),
              value=modes[1]['local_dimming'],
              brightness=modes[1]['brightness']) + "\n\n" +
            t("about_excluded_title") + "\n" +
            t("about_excluded_list") + "\n\n" +
            t("about_version", version="1.3.1") + " \n"
        )
        info_label = ttk.Label(main_frame, text=info_text, justify=tk.LEFT)
        info_label.pack(pady=10)

        link_frame = ttk.Frame(main_frame)
        link_frame.pack(pady=(0, 10))
        link_label = tk.Label(
            link_frame,
            text="https://github.com/tawiss-cloud/TA-toggle",
            fg="blue",
            cursor="hand2",
            font=('Arial', 10, 'underline')
        )
        link_label.pack()
        link_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/tawiss-cloud/TA-toggle"))

        close_button = ttk.Button(main_frame, text=t("btn_close"), command=about_window.destroy)
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
    global hotkey_thread_id, stop_hotkey_thread, HOTKEY_MODIFIERS, HOTKEY_VK
    hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
    if not user32.RegisterHotKey(None, HOTKEY_ID, HOTKEY_MODIFIERS, HOTKEY_VK):
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
            elif msg.message == WM_UPDATE_HOTKEY:
                previous_mod, previous_vk = HOTKEY_MODIFIERS, HOTKEY_VK
                try:
                    user32.UnregisterHotKey(None, HOTKEY_ID)
                except Exception:
                    pass
                if user32.RegisterHotKey(None, HOTKEY_ID, pending_hotkey_mod, pending_hotkey_vk):
                    HOTKEY_MODIFIERS, HOTKEY_VK = pending_hotkey_mod, pending_hotkey_vk
                    log(f"Горячая клавиша обновлена: {hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)}")
                    show_notification(t("notif_hotkey", hotkey=hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)))
                else:
                    log("Не удалось зарегистрировать новую горячую клавишу, возвращаем прежнюю")
                    show_notification(t("notif_hotkey_fail"))
                    user32.RegisterHotKey(None, HOTKEY_ID, previous_mod, previous_vk)
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

if __name__ == "__main__":
    load_settings()
    print(t("console_start"))
    print(t("console_standard", dimming=modes[0]['local_dimming'], brightness=modes[0]['brightness']))
    print(t("console_gaming", dimming=modes[1]['local_dimming'], brightness=modes[1]['brightness']))
    print(t("console_hdr", auto=hdr_settings['auto_set_preset'], preset=hdr_settings['preset_number']))
    print(t("console_auto_switch", state=t("console_on") if auto_switch_enabled else t("console_off")))
    print(t("console_media", state=t("console_enabled") if media_players_enabled else t("console_disabled")))
    print(t("console_media_delay", delay=media_delay_seconds))
    print(t("console_debug", state=t("console_debug_on") if is_debug_active() else t("console_debug_off")))
    print(t("console_hotkey", hotkey=hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)))

    if not find_titan_army_monitor():
        monitor_index = 0
    sync_current_mode()

    tk_thread = threading.Thread(target=start_tkinter, daemon=True)
    tk_thread.start()

    tray_icon = pystray.Icon("monitor_toggle")
    tray_icon.icon = create_image()
    rebuild_tray_menu()

    threading.Thread(target=lambda: hotkey_listener(tray_icon), daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()

    print(t("console_started", mode=modes[current_mode_index]['name']))
    if auto_switch_enabled:
        print(t("console_auto_active"))
        if media_players_enabled:
            print(t("console_media_on", delay=media_delay_seconds))
        else:
            print(t("console_media_off"))
    else:
        print(t("console_auto_off"))
    print(t("console_excluded"))
    print(t("console_manual_toggle", hotkey=hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)))
    tray_icon.run()
