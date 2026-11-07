import ctypes
import ctypes.wintypes
import time
from monitorcontrol import get_monitors
import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw
import threading
import tkinter as tk
from tkinter import ttk, colorchooser
from tkinter import font as tkfont
import json
import math
import urllib.error
import urllib.request
import urllib.parse
import subprocess
import collections
import os
import re
import io
import base64
import queue
import sys
import webbrowser
import winreg

# ===================== НАСТРОЙКИ =====================
advanced_settings_enabled = False
debug_enabled = False

# Пути к настройкам и логу — от папки скрипта/исполняемого файла, а не от
# текущей рабочей директории. Иначе при автозапуске с другой cwd настройки
# (исключения и т.д.) «теряются»: читается другой monitor_settings.json.
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_data_dir():
    """Папка настроек: %APPDATA%\\TA-toggle. Не зависит от места запуска и от прав на папку программы.
    Если AppData недоступна, остаётся папка программы."""
    base = os.environ.get("APPDATA")
    if base:
        path = os.path.join(base, "TA-toggle")
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError:
            pass
    return _APP_DIR

DATA_DIR = _resolve_data_dir()
# Отладочный лог пишется рядом с программой (не в AppData), в отличие от настроек.
DEBUG_LOG_FILE = os.path.join(_APP_DIR, "monitor_debug.log")

# Номер сборки Windows нужен только в запасном пути (когда V2-запрос HDR недоступен):
# чтобы понять, возможно ли на этой системе автоуправление цветом (ACM), из-за которого
# флаг V1 бывает включён и без HDR, а также для записи в лог.
try:
    _WIN_BUILD = sys.getwindowsversion().build
except Exception:
    _WIN_BUILD = 0
_WIN11_22H2_BUILD = 22621  # с этой сборки в Windows 11 есть «Автоматическое управление цветом» (ACM)

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
        "notif_hotkey_busy": "❌ {hotkey} занята или недоступна. Смените её в настройках.",
        "notif_settings_saved": "Настройки сохранены",
        "notif_error": "Ошибка: {error}",
        "notif_save_error": "Ошибка сохранения: {error}",
        "notif_save_failed": "Не удалось сохранить настройки (действуют до перезапуска): {error}",
        "notif_delay_field_error": "Ошибка в поле задержки: {error}",
        "notif_restart_required": "Язык изменён. Перезапустите программу, чтобы применить изменения полностью.",
        "err_brightness_range": "Яркость должна быть от 0 до 100",
        "err_select_dimming": "Выберите режим локального затемнения",
        "err_preset_range": "Номер пресета должен быть от 0 до 255",
        "err_icon_color": "Неверный цвет иконки. Формат: #RRGGBB (например, #63B03D)",
        "err_delay_min": "Задержка должна быть не менее 1 секунды",
        "err_delay_max": "Задержка не должна превышать 60 секунд",
        "settings_title": "Настройки",
        "settings_auto_switch": "Автоматическое переключение игровых режимов",
        "settings_autostart": "Запускать вместе с Windows",
        "notif_autostart_error": "Не удалось изменить автозапуск: {error}",
        "settings_media_players": "Включать медиаплееры (MPC, VLC, PotPlayer) в игровой режим",
        "settings_media_delay_label": "Задержка перед переключением для медиаплееров (сек):",
        "settings_exclusions_group": "Свои исключения",
        "settings_exclusions_hint": "Программы из этого списка не считаются играми и не включают игровой режим. Имя процесса окна может отличаться от запускаемого exe (например, у игр на Unreal Engine) – надёжнее выбирать из запущенных. Встроенные исключения (браузеры, Проводник и др.) остаются в силе. Изменения применяются после сохранения.",
        "settings_exclusions_add": "Добавить",
        "settings_exclusions_running": "Выбрать из запущенных",
        "settings_exclusions_running_title": "Запущенные программы",
        "settings_exclusions_running_hint": "Программы с видимыми окнами. Выберите нужную (двойной щелчок или кнопка «Добавить») – будет добавлено точное имя процесса окна.",
        "settings_exclusions_refresh": "Обновить",
        "settings_exclusions_remove": "Удалить выбранное",
        "settings_exclusions_name_label": "Название процесса",
        "err_exclusion_invalid": "Введите имя процесса, например game.exe",
        "err_exclusion_duplicate": "{name} уже есть в исключениях",
        "settings_range_1_60": "(1-60)",
        "settings_standard_mode": "Стандартный режим (SDR)",
        "settings_gaming_mode": "Игровой режим (SDR)",
        "settings_icon_color_label": "Цвет иконки в трее:",
        "settings_icon_color_enabled": "Менять цвет иконки в трее при смене режима",
        "settings_icon_color_reset": "Сбросить",
        "settings_icon_color_dialog": "Цвет иконки в трее",
        "settings_notification_group": "Всплывающее окно",
        "settings_notification_win10": "Win 10",
        "settings_notification_win11": "Win 11",
        "settings_notification_off": "Выключено",
        "settings_brightness_label": "Яркость (0-100):",
        "settings_dimming_label": "Локальное затемнение:",
        "toggle_on": "Вкл",
        "toggle_off": "Выкл",
        "err_not_a_number": "Введите целое число",
        "settings_version": "Версия {version}",
        "update_available": "Доступна новая версия",
        "update_checking": "Проверка…",
        "update_latest": "Установлена последняя версия",
        "update_error": "Не удалось проверить обновления",
        "settings_auto_update": "Проверять обновления автоматически",
        "settings_auto_update_desc": "Раз в 14 дней. Если выйдет новая версия, появится уведомление при запуске и значок со ссылкой слева внизу в настройках.",
        "notif_update_available": "Доступна новая версия {version}. Ссылка доступна в настройках.",
        "settings_nav_about": "О программе",
        "settings_reset_title": "Сброс настроек",
        "settings_reset_desc": "Вернуть все настройки программы к значениям по умолчанию.",
        "settings_reset_button": "Сбросить",
        "settings_reset_confirm": "Все настройки программы будут возвращены к значениям по умолчанию: режимы, Halo Control, горячая клавиша, исключения, тема, язык и автозапуск. Продолжить?",
        "notif_settings_reset": "Настройки сброшены по умолчанию",
        "settings_file_title": "Файл настроек",
        "settings_open_folder": "Открыть папку",
        "about_source_title": "Исходный код",
        "settings_nav_general": "Общие",
        "settings_nav_auto": "Автопереключение",
        "settings_nav_modes": "Режимы монитора",
        "settings_nav_advanced": "Дополнительно",
        "settings_theme_title": "Тема оформления",
        "settings_theme_desc": "Применяется при следующем открытии окон.",
        "theme_dark": "Тёмная",
        "theme_light": "Светлая",
        "theme_system": "Как в системе",
        "err_halo_range": "Halo Control: значение от 0 до 100",
        "settings_section_general": "Общие",
        "settings_section_auto": "Автоматическое переключение",
        "settings_section_modes": "Режимы монитора",
        "settings_exclusions_toggle_desc": "Не считать выбранные программы играми. Пока выключено, список не действует.",
        "settings_brightness_title": "Яркость",
        "settings_dimming_title": "Локальное затемнение",
        "settings_halo_title": "Halo Control",
        "settings_halo_desc": "Регулирует баланс подсветки: низкие значения подавляют ореолы (blooming), высокие — повышают яркость и детализацию мелких объектов.",
        "settings_halo_value": "Уровень Halo (0–100)",
        "about_hotkey_title": "Горячая клавиша",
        "about_brightness_part": "яркость {brightness}",
        "about_dimming_part": "локальное затемнение: {dimming}",
        "about_halo_part": "Halo {halo}",
        "about_excluded_custom": "Плюс свои исключения из настроек: {count}.",
        "err_already_running": "Программа уже запущена (значок в области уведомлений).",
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
        "about_excluded_list": "Wallpaper Engine, браузеры (Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Яндекс и др.), Проводник, cmd, powershell, notepad, mspaint.",
        "about_version": "Версия: {version}",
        "menu_about": "О программе",
        "menu_settings": "Настройки",
        "menu_exit": "Закрыть",
        "settings_report_title": "Сообщить о проблеме",
        "settings_monitor_title": "Монитор",
        "settings_journal_title": "Журнал работы",
        "settings_journal_desc": "Что делала программа и какие ошибки встретила. Поможет разобраться, если что-то работает не так.",
        "settings_journal_open": "Открыть",
        "btn_copy": "Копировать",
        "settings_monitor_desc": "Если автоопределение ошиблось, выберите монитор вручную.",
        "monitor_current": "Сейчас используется: {name}",
        "monitor_incompatible_warning": "Этот монитор не похож на Titan Army. Программа будет менять на нём яркость и другие настройки изображения, и они могут работать иначе.",
        "monitor_auto": "Автоопределение",
        "monitor_loading": "Поиск мониторов…",
        "monitor_missing": "Выбранный монитор (не подключён)",
        "monitor_unnamed": "Универсальный монитор PnP",
        "monitor_display_number": "Дисплей {n}",
        "report_title": "Сообщить о проблеме",
        "report_intro": "Отчёт создаётся как Issue в репозитории программы на GitHub. Страница откроется в браузере, для отправки нужен аккаунт GitHub.",
        "report_steps_title": "Как это работает",
        "report_step1": "1. Если проблему можно повторить, повторите её сейчас: журнал работы программы хранится в памяти, и недавние записи попадут в отчёт.",
        "report_step2": "2. Заполните форму ниже и нажмите «{create}»: откроется страница нового Issue на GitHub.",
        "report_step3": "3. Если поле описания на этой странице пустое или в нём подсказка, вставьте текст из буфера обмена (Ctrl+V) и отправьте Issue.",
        "report_log_title": "Файл лога (необязательно)",
        "report_log_on": "Запись в файл включена. Приложите его к Issue, если проблема проявляется не сразу. Файл: {file}",
        "report_log_off": "Запись в файл выключена. Нужна, только если ошибка проявляется не сразу: включите её в настройках и приложите файл к Issue. Файл: {file}",
        "report_open_settings": "Открыть настройки",
        "report_show_log": "Показать файл",
        "report_log_missing": "Файла лога пока нет: включите запись в файл в настройках и повторите действия, вызывающие ошибку.",
        "report_form_title": "Отчёт",
        "report_field_title": "Заголовок",
        "report_field_desc": "Описание",
        "report_desc_hint": "Что произошло, что вы ожидали и как это повторить",
        "report_include_log": "Добавить журнал работы",
        "report_include_log_desc": "Последние записи работы программы ({count} строк). В них могут быть названия запущенных программ и пути на компьютере, в том числе имя пользователя Windows. Посмотрите, что будет отправлено.",
        "report_preview": "Просмотр",
        "report_preview_title": "Журнал работы",
        "report_log_empty": "(журнал пуст)",
        "report_include_system": "Добавить сведения о системе",
        "report_include_system_desc": "Версия программы, сборка Windows, язык, режим и состояние debug.",
        "report_create": "Создать отчёт",
        "report_err_title": "Введите заголовок.",
        "report_err_desc": "Опишите проблему.",
        "report_err_desc_long": "Описание слишком длинное (не больше {limit} символов). Сократите его: подробности можно добавить на странице GitHub.",
        "report_opened": "Страница GitHub открыта.",
        "report_clipboard_note": "Текст отчёта скопирован в буфер обмена: вставьте его в поле описания на странице GitHub (Ctrl+V).",
        "report_clipboard_failed": "Не удалось скопировать текст в буфер обмена: введите описание на странице GitHub вручную.",
        "report_open_failed": "Не удалось открыть браузер. Откройте страницу вручную: {url}",
        "report_body_description": "Описание",
        "report_body_log": "Журнал",
        "report_body_log_summary": "Журнал работы ({count} строк)",
        "report_body_system": "Система",
        "report_body_paste": "Текст отчёта скопирован в буфер обмена: вставьте его сюда (Ctrl+V) вместо этой строки.",
        "tray_title": "Режим {mode}",
        "tray_title_with_process": "Режим {mode} ({process})",
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
        "notif_hotkey_busy": "❌ {hotkey} is busy or unavailable. Change it in Settings.",
        "notif_settings_saved": "Settings saved",
        "notif_error": "Error: {error}",
        "notif_save_error": "Save error: {error}",
        "notif_save_failed": "Could not save settings (active until restart): {error}",
        "notif_delay_field_error": "Error in delay field: {error}",
        "notif_restart_required": "Language changed. Restart the program to fully apply the change.",
        "err_brightness_range": "Brightness must be between 0 and 100",
        "err_select_dimming": "Please select a local dimming mode",
        "err_preset_range": "Preset number must be between 0 and 255",
        "err_icon_color": "Invalid icon color. Use #RRGGBB format (e.g. #63B03D)",
        "err_delay_min": "Delay must be at least 1 second",
        "err_delay_max": "Delay must not exceed 60 seconds",
        "settings_title": "Settings",
        "settings_auto_switch": "Automatic game mode switching",
        "settings_autostart": "Start with Windows",
        "notif_autostart_error": "Could not change autostart: {error}",
        "settings_media_players": "Treat media players (MPC, VLC, PotPlayer) as gaming mode",
        "settings_media_delay_label": "Delay before switching for media players (sec):",
        "settings_exclusions_group": "Custom exclusions",
        "settings_exclusions_hint": "Programs in this list are not treated as games and do not trigger gaming mode. The window's process name can differ from the launched exe (e.g. Unreal Engine games) – picking from running programs is more reliable. Built-in exclusions (browsers, Explorer, etc.) still apply. Changes take effect after saving.",
        "settings_exclusions_add": "Add",
        "settings_exclusions_running": "Choose from running...",
        "settings_exclusions_running_title": "Running programs",
        "settings_exclusions_running_hint": "Programs with visible windows. Select one (double-click or the Add button) – the exact process name of the window will be added.",
        "settings_exclusions_refresh": "Refresh",
        "settings_exclusions_remove": "Remove selected",
        "settings_exclusions_name_label": "Process name",
        "err_exclusion_invalid": "Enter a process name, e.g. game.exe",
        "err_exclusion_duplicate": "{name} is already excluded",
        "settings_range_1_60": "(1-60)",
        "settings_standard_mode": "Standard mode (SDR)",
        "settings_gaming_mode": "Gaming mode (SDR)",
        "settings_icon_color_label": "Tray icon color:",
        "settings_icon_color_enabled": "Change tray icon color when the mode changes",
        "settings_icon_color_reset": "Reset",
        "settings_icon_color_dialog": "Tray icon color",
        "settings_notification_group": "Pop-up notification",
        "settings_notification_win10": "Win 10",
        "settings_notification_win11": "Win 11",
        "settings_notification_off": "Off",
        "settings_brightness_label": "Brightness (0-100):",
        "settings_dimming_label": "Local dimming:",
        "toggle_on": "On",
        "toggle_off": "Off",
        "err_not_a_number": "Enter a whole number",
        "settings_version": "Version {version}",
        "update_available": "A new version is available",
        "update_checking": "Checking…",
        "update_latest": "You have the latest version",
        "update_error": "Could not check for updates",
        "settings_auto_update": "Check for updates automatically",
        "settings_auto_update_desc": "Every 14 days. If a new version is released, you get a notification at startup and an icon with a link at the bottom left of Settings.",
        "notif_update_available": "A new version {version} is available. The link is available in Settings.",
        "settings_nav_about": "About",
        "settings_reset_title": "Reset settings",
        "settings_reset_desc": "Restore all program settings to their defaults.",
        "settings_reset_button": "Reset",
        "settings_reset_confirm": "All program settings will be restored to their defaults: modes, Halo Control, hotkey, exclusions, theme, language and autostart. Continue?",
        "notif_settings_reset": "Settings reset to defaults",
        "settings_file_title": "Settings file",
        "settings_open_folder": "Open folder",
        "about_source_title": "Source code",
        "settings_nav_general": "General",
        "settings_nav_auto": "Auto-switching",
        "settings_nav_modes": "Monitor modes",
        "settings_nav_advanced": "Advanced",
        "settings_theme_title": "Theme",
        "settings_theme_desc": "Applies the next time windows are opened.",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "theme_system": "Follow system",
        "err_halo_range": "Halo Control: value from 0 to 100",
        "settings_section_general": "General",
        "settings_section_auto": "Automatic switching",
        "settings_section_modes": "Monitor modes",
        "settings_exclusions_toggle_desc": "Don't treat selected programs as games. While off, the list has no effect.",
        "settings_brightness_title": "Brightness",
        "settings_dimming_title": "Local dimming",
        "settings_halo_title": "Halo Control",
        "settings_halo_desc": "Balances the backlight: low values suppress halos (blooming), high values increase brightness and detail of small objects.",
        "settings_halo_value": "Halo level (0–100)",
        "about_hotkey_title": "Hotkey",
        "about_brightness_part": "brightness {brightness}",
        "about_dimming_part": "local dimming: {dimming}",
        "about_halo_part": "Halo {halo}",
        "about_excluded_custom": "Plus your custom exclusions: {count}.",
        "err_already_running": "The program is already running (see the tray icon).",
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
        "settings_language_group": "Language",
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
        "about_excluded_list": "Wallpaper Engine, browsers (Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Yandex, etc.), Explorer, cmd, powershell, notepad, mspaint.",
        "about_version": "Version: {version}",
        "menu_about": "About",
        "menu_settings": "Settings",
        "menu_exit": "Exit",
        "settings_report_title": "Report a problem",
        "settings_monitor_title": "Monitor",
        "settings_journal_title": "Activity log",
        "settings_journal_desc": "What the program did and which errors it ran into. Helps to find out why something doesn't work.",
        "settings_journal_open": "Open",
        "btn_copy": "Copy",
        "settings_monitor_desc": "If auto-detect picks the wrong one, choose the monitor manually.",
        "monitor_current": "Currently in use: {name}",
        "monitor_incompatible_warning": "This monitor doesn't look like a Titan Army. The program will change its brightness and other picture settings, and they may not work as expected.",
        "monitor_auto": "Auto-detect",
        "monitor_loading": "Looking for monitors…",
        "monitor_missing": "Selected monitor (not connected)",
        "monitor_unnamed": "Generic PnP Monitor",
        "monitor_display_number": "Display {n}",
        "report_title": "Report a problem",
        "report_intro": "The report is created as an Issue in the program's GitHub repository. The page opens in your browser; a GitHub account is required to submit it.",
        "report_steps_title": "How it works",
        "report_step1": "1. If the problem can be reproduced, reproduce it now: the program keeps its activity log in memory, and the recent entries go into the report.",
        "report_step2": "2. Fill in the form below and click \"{create}\": the new Issue page opens on GitHub.",
        "report_step3": "3. If the description field on that page is empty or holds a hint, paste the text from the clipboard (Ctrl+V) and submit the Issue.",
        "report_log_title": "Log file (optional)",
        "report_log_on": "Writing to a file is on. Attach it to the Issue if the problem does not show up right away. File: {file}",
        "report_log_off": "Writing to a file is off. It is only needed if the problem does not show up right away: turn it on in Settings and attach the file to the Issue. File: {file}",
        "report_open_settings": "Open settings",
        "report_show_log": "Show file",
        "report_log_missing": "There is no log file yet: turn on writing to a file in Settings and repeat the actions that cause the problem.",
        "report_form_title": "Report",
        "report_field_title": "Title",
        "report_field_desc": "Description",
        "report_desc_hint": "What happened, what you expected, and how to reproduce it",
        "report_include_log": "Include the activity log",
        "report_include_log_desc": "Recent program activity ({count} lines). It may contain names of running programs and paths on your computer, including your Windows user name. Check what will be sent.",
        "report_preview": "Preview",
        "report_preview_title": "Activity log",
        "report_log_empty": "(the log is empty)",
        "report_include_system": "Include system information",
        "report_include_system_desc": "Program version, Windows build, language, mode and debug state.",
        "report_create": "Create report",
        "report_err_title": "Enter a title.",
        "report_err_desc": "Describe the problem.",
        "report_err_desc_long": "The description is too long (at most {limit} characters). Shorten it: you can add details on the GitHub page.",
        "report_opened": "The GitHub page is open.",
        "report_clipboard_note": "The report text was copied to the clipboard: paste it into the description field on the GitHub page (Ctrl+V).",
        "report_clipboard_failed": "Could not copy the text to the clipboard: enter the description on the GitHub page manually.",
        "report_open_failed": "Could not open the browser. Open the page manually: {url}",
        "report_body_description": "Description",
        "report_body_log": "Log",
        "report_body_log_summary": "Activity log ({count} lines)",
        "report_body_system": "System",
        "report_body_paste": "The report text was copied to the clipboard: paste it here (Ctrl+V) instead of this line.",
        "tray_title": "Mode {mode}",
        "tray_title_with_process": "Mode {mode} ({process})",
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

def get_mode_name(index):
    """Название режима по индексу, всегда на текущем языке.
    Не берём из modes: имена там закешированы на момент старта и не меняются
    при смене языка."""
    return t("mode_standard_name") if index == 0 else t("mode_gaming_name")

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

# Имя процесса читаем с минимальным правом (без доступа к памяти процесса) –
# это безопаснее для античитов и работает для большего числа процессов.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
kernel32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.LPWSTR,
    ctypes.POINTER(ctypes.wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = ctypes.wintypes.BOOL

HOTKEY_ID = 1
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # без автоповтора WM_HOTKEY при удержании клавиши
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
VCP_HALO = 0x46
# Пауза между записью 0x99 и парной записью (0x47 / 0x46): без неё вторая запись может молча теряться.
VCP_PAIR_DELAY = 0.08

# ===================== HDR через Windows (Display Config API) =====================
# Для всех сценариев, КРОМЕ медиаплеера: плееры с HDR passthrough шлют HDR мимо
# композитора Windows, этот флаг у них не меняется (для них – яркость по DDC/CI).
#
# V1 (type 9) смотрит только бит advancedColorEnabled. На Windows 11 с включённым
# «Автоматическим управлением цветом» (ACM) он может быть TRUE и без HDR.
# V2 (type 15, насколько известно, Win11 24H2+) добавляет activeColorMode, где HDR=2, WCG=1, SDR=0 –
# надёжный признак именно HDR.
_DC_GET_SOURCE_NAME = 1
_DC_GET_ADVANCED_COLOR_INFO = 9
_DC_GET_ADVANCED_COLOR_INFO_2 = 15
_DISPLAYCONFIG_ADVANCED_COLOR_MODE_HDR = 2
_QDC_ONLY_ACTIVE_PATHS = 0x00000002
_CCHDEVICENAME = 32

# Отдельные экземпляры DLL: argtypes задаём только для наших вызовов и не
# затрагиваем остальной код, использующий общий ctypes.windll.user32.
_dc_user32 = ctypes.WinDLL("user32", use_last_error=True)
_dc_dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)

class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.wintypes.DWORD), ("HighPart", ctypes.wintypes.LONG)]

class _DC_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", ctypes.wintypes.UINT), ("Denominator", ctypes.wintypes.UINT)]

class _DC_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [("adapterId", _LUID), ("id", ctypes.wintypes.UINT),
                ("modeInfoIdx", ctypes.wintypes.UINT), ("statusFlags", ctypes.wintypes.UINT)]

class _DC_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [("adapterId", _LUID), ("id", ctypes.wintypes.UINT),
                ("modeInfoIdx", ctypes.wintypes.UINT), ("outputTechnology", ctypes.wintypes.UINT),
                ("rotation", ctypes.wintypes.UINT), ("scaling", ctypes.wintypes.UINT),
                ("refreshRate", _DC_RATIONAL), ("scanLineOrdering", ctypes.wintypes.UINT),
                ("targetAvailable", ctypes.wintypes.BOOL), ("statusFlags", ctypes.wintypes.UINT)]

class _DC_PATH_INFO(ctypes.Structure):
    _fields_ = [("sourceInfo", _DC_PATH_SOURCE_INFO), ("targetInfo", _DC_PATH_TARGET_INFO),
                ("flags", ctypes.wintypes.UINT)]

class _DC_MODE_INFO(ctypes.Structure):
    # Содержимое нам не нужно, важен только размер (64 байта) для буфера.
    _fields_ = [("_opaque", ctypes.c_byte * 64)]

class _DC_HEADER(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.UINT), ("size", ctypes.wintypes.UINT),
                ("adapterId", _LUID), ("id", ctypes.wintypes.UINT)]

class _DC_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [("header", _DC_HEADER), ("value", ctypes.wintypes.UINT),
                ("colorEncoding", ctypes.wintypes.UINT), ("bitsPerColorChannel", ctypes.wintypes.UINT)]

class _DC_ADVANCED_COLOR_INFO_2(ctypes.Structure):
    _fields_ = [("header", _DC_HEADER), ("value", ctypes.wintypes.UINT),
                ("colorEncoding", ctypes.wintypes.UINT), ("bitsPerColorChannel", ctypes.wintypes.UINT),
                ("activeColorMode", ctypes.wintypes.UINT)]

class _DC_SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", _DC_HEADER),
                ("viewGdiDeviceName", ctypes.wintypes.WCHAR * _CCHDEVICENAME)]

class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("szDevice", ctypes.wintypes.WCHAR * _CCHDEVICENAME)]

_dc_user32.GetDisplayConfigBufferSizes.argtypes = [
    ctypes.wintypes.UINT, ctypes.POINTER(ctypes.wintypes.UINT), ctypes.POINTER(ctypes.wintypes.UINT)]
_dc_user32.GetDisplayConfigBufferSizes.restype = ctypes.c_long
_dc_user32.QueryDisplayConfig.argtypes = [
    ctypes.wintypes.UINT, ctypes.POINTER(ctypes.wintypes.UINT), ctypes.c_void_p,
    ctypes.POINTER(ctypes.wintypes.UINT), ctypes.c_void_p, ctypes.c_void_p]
_dc_user32.QueryDisplayConfig.restype = ctypes.c_long
_dc_user32.DisplayConfigGetDeviceInfo.argtypes = [ctypes.c_void_p]
_dc_user32.DisplayConfigGetDeviceInfo.restype = ctypes.c_long
_dc_user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_dc_user32.GetMonitorInfoW.restype = ctypes.wintypes.BOOL
_dc_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.wintypes.DWORD)]
_dc_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = ctypes.wintypes.BOOL

_DC_MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(RECT), ctypes.wintypes.LPARAM)
_dc_user32.EnumDisplayMonitors.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, _DC_MONITORENUMPROC, ctypes.wintypes.LPARAM]
_dc_user32.EnumDisplayMonitors.restype = ctypes.wintypes.BOOL


_DC_GET_TARGET_NAME = 2

class _DC_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", _DC_HEADER), ("flags", ctypes.wintypes.UINT),
                ("outputTechnology", ctypes.wintypes.UINT),
                ("edidManufactureId", ctypes.wintypes.WORD), ("edidProductCodeId", ctypes.wintypes.WORD),
                ("connectorInstance", ctypes.wintypes.UINT),
                ("monitorFriendlyDeviceName", ctypes.wintypes.WCHAR * 64),
                ("monitorDevicePath", ctypes.wintypes.WCHAR * 128)]


def _dc_active_paths():
    num_paths = ctypes.wintypes.UINT()
    num_modes = ctypes.wintypes.UINT()
    ret = _dc_user32.GetDisplayConfigBufferSizes(
        _QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_paths), ctypes.byref(num_modes))
    if ret != 0:
        raise OSError(f"GetDisplayConfigBufferSizes: {ret}")
    paths = (_DC_PATH_INFO * num_paths.value)()
    modes = (_DC_MODE_INFO * num_modes.value)()
    ret = _dc_user32.QueryDisplayConfig(
        _QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_paths), paths,
        ctypes.byref(num_modes), modes, None)
    if ret != 0:
        raise OSError(f"QueryDisplayConfig: {ret}")
    return [p for p in paths[:num_paths.value] if p.targetInfo.targetAvailable]


def _dc_source_gdi_name(adapter_id, source_id):
    req = _DC_SOURCE_DEVICE_NAME()
    req.header.type = _DC_GET_SOURCE_NAME
    req.header.size = ctypes.sizeof(_DC_SOURCE_DEVICE_NAME)
    req.header.adapterId = adapter_id
    req.header.id = source_id
    ret = _dc_user32.DisplayConfigGetDeviceInfo(ctypes.byref(req.header))
    if ret != 0:
        raise OSError(f"DisplayConfigGetDeviceInfo(source name): {ret}")
    return req.viewGdiDeviceName


def _dc_monitor_gdi_name(index):
    """GDI-имя физического монитора с индексом index (порядок как у monitorcontrol)."""
    hmonitors = []

    def _cb(hmonitor, hdc, lprect, lparam):
        hmonitors.append(hmonitor)
        return True
    cb = _DC_MONITORENUMPROC(_cb)
    if not _dc_user32.EnumDisplayMonitors(None, None, cb, 0):
        raise OSError("EnumDisplayMonitors failed")
    count = ctypes.wintypes.DWORD()
    running = 0
    for hmon in hmonitors:
        if not _dc_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)):
            continue
        if count.value == 0:
            continue
        if running <= index < running + count.value:
            mi = _MONITORINFOEXW()
            mi.cbSize = ctypes.sizeof(_MONITORINFOEXW)
            if _dc_user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                return mi.szDevice
            return None
        running += count.value
    return None


def _dc_target_path_for_monitor(index, paths):
    """Путь дисплея нашего монитора – по GDI-имени, а не по индексу (порядки перечислений не совпадают)."""
    gdi = None
    try:
        gdi = _dc_monitor_gdi_name(index)
    except Exception as e:
        log(f"HDR (Windows): не удалось получить GDI-имя монитора {index}: {e}")
    if gdi:
        for p in paths:
            try:
                if _dc_source_gdi_name(p.sourceInfo.adapterId, p.sourceInfo.id) == gdi:
                    return p, True
            except Exception:
                continue
    # Сопоставить по имени не удалось. Запасной вариант по индексу допустим только когда активный дисплей один:
    # порядки перечислений у monitorcontrol и DisplayConfig не совпадают, и по индексу можно попасть в чужой монитор.
    if len(paths) == 1:
        return paths[0], False
    return None, False


def _dc_target_info_for_monitor(index):
    """(device path, понятное имя) монитора с индексом index; None вместо того, что получить не удалось.
    Device path – устойчивый идентификатор цели DisplayConfig: в отличие от индекса monitorcontrol не меняется
    при смене порядка перечисления."""
    try:
        gdi = _dc_monitor_gdi_name(index)
        if not gdi:
            return None, None
        for p in _dc_active_paths():
            try:
                if _dc_source_gdi_name(p.sourceInfo.adapterId, p.sourceInfo.id) != gdi:
                    continue
            except Exception:
                continue
            req = _DC_TARGET_DEVICE_NAME()
            req.header.type = _DC_GET_TARGET_NAME
            req.header.size = ctypes.sizeof(_DC_TARGET_DEVICE_NAME)
            req.header.adapterId = p.targetInfo.adapterId
            req.header.id = p.targetInfo.id
            if _dc_user32.DisplayConfigGetDeviceInfo(ctypes.byref(req.header)) == 0 and req.monitorDevicePath:
                return req.monitorDevicePath, (req.monitorFriendlyDeviceName or None)
    except Exception as e:
        log(f"Не удалось получить device path монитора {index}: {e}")
    return None, None


def _dc_device_path_for_monitor(index):
    """Устойчивый идентификатор монитора с индексом index. None – не удалось."""
    return _dc_target_info_for_monitor(index)[0]


def _try_advanced_color_v2(path):
    """V2 (GET_ADVANCED_COLOR_INFO_2): активный режим цвета – HDR=2, WCG=1 (автоуправление
    цветом), SDR=0. Насколько известно, появился в Windows 11 24H2, на более ранних сборках
    вызов возвращает ошибку. Возвращает ('hdr'/'ok', None) или (None, код_ошибки)."""
    req2 = _DC_ADVANCED_COLOR_INFO_2()
    req2.header.type = _DC_GET_ADVANCED_COLOR_INFO_2
    req2.header.size = ctypes.sizeof(_DC_ADVANCED_COLOR_INFO_2)
    req2.header.adapterId = path.targetInfo.adapterId
    req2.header.id = path.targetInfo.id
    ret = _dc_user32.DisplayConfigGetDeviceInfo(ctypes.byref(req2.header))
    if ret != 0:
        return None, ret
    return ("hdr" if req2.activeColorMode == _DISPLAYCONFIG_ADVANCED_COLOR_MODE_HDR else "ok"), None


def _try_advanced_color_v1(path):
    """V1 (GET_ADVANCED_COLOR_INFO): (advancedColorEnabled, value). Бит «включён» равен TRUE и при
    HDR, и при «Автоматическом управлении цветом» (WCG), поэтому по нему одному HDR не определить."""
    req = _DC_ADVANCED_COLOR_INFO()
    req.header.type = _DC_GET_ADVANCED_COLOR_INFO
    req.header.size = ctypes.sizeof(_DC_ADVANCED_COLOR_INFO)
    req.header.adapterId = path.targetInfo.adapterId
    req.header.id = path.targetInfo.id
    ret = _dc_user32.DisplayConfigGetDeviceInfo(ctypes.byref(req.header))
    if ret != 0:
        raise OSError(f"DisplayConfigGetDeviceInfo(advanced color V1): {ret}")
    return bool(req.value & 0x2), req.value


def _query_windows_hdr():
    """"hdr" / "ok" / "unsure" по системному режиму цвета; если определить не удалось – бросает исключение.
    Без чтения монитора:
      - V2 есть (Win11 24H2+) – однозначный ответ: SDR, WCG (автоуправление цветом) и HDR различаются;
      - V2 нет, advanced color выключен – "ok" (нет ни HDR, ни ACM);
      - V2 нет, включён, сборка без ACM (старше Win11 22H2) – "hdr".
    "unsure" – единственный неоднозначный случай: сборка с ACM, но без V2, флаг включён – это HDR
    или просто автоуправление цветом. Вызывающий код уточняет его по яркости (одно чтение монитора)."""
    global last_windows_hdr_detail
    paths = _dc_active_paths()
    if not paths:
        raise OSError("активные дисплеи не найдены")
    idx = _resolve_monitor_index(redetect=False)
    if idx is None:
        idx = 0
    path, by_name = _dc_target_path_for_monitor(idx, paths)
    if path is None:
        # Лучше честная ошибка (проверка уйдёт на яркость), чем ответ по чужому монитору.
        raise OSError("не удалось сопоставить монитор с дисплеем Windows")
    if not by_name:
        log("HDR (Windows): монитор сопоставлен без имени: активный дисплей единственный (запасной вариант)")

    result, err = _try_advanced_color_v2(path)
    if err is None:
        last_windows_hdr_detail = "V2"
        return result

    enabled, value = _try_advanced_color_v1(path)
    last_windows_hdr_detail = f"V2 недоступен (ret={err}), V1 value=0x{value:x}, сборка {_WIN_BUILD}"
    if not enabled:
        return "ok"
    if _WIN_BUILD < _WIN11_22H2_BUILD:
        return "hdr"
    return "unsure"

current_mode_index = 0
last_switch_time = 0
DELAY = 1

manual_override_active = False
manual_override_waiting = False

modes = []
SETTINGS_FILE = os.path.join(DATA_DIR, "monitor_settings.json")

monitor_index = None
monitor_device_path = None  # устойчивый идентификатор выбранного монитора (DisplayConfig device path)
monitor_manual = False      # монитор выбран вручную в настройках: автоопределение и перепривязка не применяются
hotkey_thread_id = None
stop_hotkey_thread = False
app_exiting = False  # выставляется при выходе из программы: останавливает цикл Tk
tray_icon = None

# Цвет центра иконки в трее для каждого режима: [стандартный, игровой].
# Игровой по умолчанию зелёный #63B03D. Хранится в настройках (ключ icon_colors).
DEFAULT_ICON_COLORS = ["#FFFFFF", "#63B03D"]
# Прежний цвет по умолчанию для игрового режима: если он сохранён в настройках, считаем, что цвет не
# менялся вручную, и подставляем новый (иначе смена умолчания не дошла бы до уже сохранённых настроек).
LEGACY_GAMING_ICON_COLOR = "#4CAF50"
icon_colors = list(DEFAULT_ICON_COLORS)
# False (по умолчанию) – цвет иконки не зависит от режима (всегда белый центр), поля цвета в
# настройках скрыты. True – центр иконки меняет цвет вместе с режимом.
icon_color_enabled = False

# Стиль всплывающего окна: "win10" – прямые углы (как раньше), "win11" – скруглённые углы,
# "off" – не показывать (ошибку сохранения настроек показываем всегда). Хранится в настройках.
NOTIFICATION_STYLES = ("win10", "win11", "off")
notification_style = "win10"

hdr_settings = {
    "auto_set_preset": False,
    "preset_number": 5
}
auto_switch_enabled = True
media_players_enabled = True
media_delay_seconds = 2

tk_queue = queue.Queue()
# Сериализует обмен с монитором по DDC/CI (I2C не рассчитан на параллельный доступ).
monitor_io_lock = threading.Lock()

game_counter = 0
GAME_THRESHOLD = 2
game_window_hwnd = None
media_timer = None
media_timer_lock = threading.Lock()
last_reported_state = None
last_excluded_process_logged = None

# Защищает состояние игровой/медиа-сессии от гонки между monitor_loop(),
# delayed_media_switch() и toggle_mode() (разные потоки).
game_state_lock = threading.Lock()

# Кэш HDR хранится отдельно для каждого способа проверки ("windows" – по системному режиму цвета,
# "media" – для медиаплеера, "brightness" – только яркость), чтобы результат одного способа не
# использовался для другого. Значение: (результат, время реальной проверки).
hdr_method_cache = {}
# Последняя записанная в журнал HDR-проверка по способу: (результат, пояснение, время). Одинаковый результат
# повторно пишется не чаще раза в HDR_LOG_REPEAT секунд, иначе устойчивая ошибка забивает журнал каждые 2 секунды.
hdr_log_last = {}
HDR_LOG_REPEAT = 60.0
loop_log_gate = {"media_hdr_error": None}   # окно, для которого ошибка проверки в ветке медиаплеера уже записана
# Последняя ошибка Windows-проверки (одинаковую пишем в лог один раз) и подробности последней
# успешной проверки (версия API, сырое значение флагов) – для строки лога.
last_windows_hdr_error = None
last_windows_hdr_detail = ""
# True, пока медиа-сессия не завершена (стандартный режим не восстановлен) –
# по нему выбирается способ проверки HDR, когда окна уже нет.
last_session_media = False
HDR_CACHE_TIME = 2
# Окно коалесцирования force_refresh: одна логическая операция (нажатие
# хоткея) зовёт is_hdr_enabled(force_refresh=True) несколько раз подряд из
# разных мест (hotkey_listener → toggle_mode → sync_current_mode →
# apply_mode_by_index). Без коалесцирования это N одинаковых строк в логе и
# N лишних чтений монитора. DELAY хоткея = 1 сек, так что 0.5 сек безопасно:
# два разных нажатия в это окно всё равно не попадут. Возраст считается по
# записи кэша ЭТОГО способа проверки, а не по любой последней проверке.
HDR_FORCE_COALESCE_TIME = 0.5
hdr_cache_lock = threading.Lock()

# Возврат в стандартный режим не кэшируется по сессии и при блокировке опрашивает монитор
# каждые HDR_CACHE_TIME сек; STANDARD_RETURN_RETRY_INTERVAL троттлит повторы в monitor_loop
# (HDR_CACHE_TIME общий для других вызовов, его не меняем).
STANDARD_RETURN_RETRY_INTERVAL = 10
standard_return_last_attempt_time = 0.0

# Долг "вернуть SDR, но пока не удалось". Отдельно от last_reported_state,
# который значит только "идёт ли сейчас игра/медиа".
standard_restore_pending = False

# Подтверждённый HDR кэшируется по окну, а не по времени: действует, пока
# hdr_confirmed_for_hwnd – то же существующее окно, иначе – свежая проверка.
confirmed_hdr_active = False
hdr_confirmed_for_hwnd = None

# Гейт лога "Обнаружена игра (подтверждено)": один раз на окно, не каждую секунду.
game_switch_attempt_logged = False
game_switch_attempt_hwnd = None

# Гейты логов блокировки при возврате в стандартный режим (index==0): сессионный кэш там
# не используется (автовозврат срабатывает сразу после выключения HDR), без гейтов лог шёл
# бы каждую секунду. attempt_logged – в monitor_loop, blocked_logged – в apply_mode_by_index.
standard_return_attempt_logged = False
standard_return_blocked_logged = False

# Последний медиаплеер, для которого уже писали в лог "Медиаплеер X – игровой
# режим". Сбрасывается только при реальной смене сессии: закрытие игрового
# окна (monitor_loop), ручное переключение режима (toggle_mode). НЕ
# сбрасывается в конце is_game_window, иначе лог дублировался бы при каждом
# сворачивании/разворачивании одного и того же плеера.
last_media_player_logged = None

# Имя процесса, которое сейчас показано в подсказке трея (только для игрового
# режима, установленного автоматически). Используется в rebuild_tray_menu(),
# чтобы после смены языка подсказка не потеряла суффикс с процессом.
last_tray_process_name = None

MEDIA_PLAYER_PROCESSES = [
    "mpc-hc.exe", "mpc-be.exe", "mpc-hc64.exe", "mpc-be64.exe",
    "vlc.exe", "potplayer.exe", "kmplayer.exe", "mediaplayerclassic.exe"
]
_MEDIA_PLAYER_NAMES = {m.lower() for m in MEDIA_PLAYER_PROCESSES}

EXCLUDED_PROCESSES = [
    "wallpaper32.exe", "wallpaper64.exe", "explorer.exe", "StartMenuExperienceHost.exe",
    "cmd.exe", "powershell.exe", "notepad.exe", "mspaint.exe",
    "chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "vivaldi.exe", "chromium.exe",
    "browser.exe", "yandex.exe", "whale.exe", "thorium.exe", "iron.exe", "epic.exe",
    "dragon.exe", "slimjet.exe", "torch.exe", "kinza.exe", "amigo.exe", "sidekick.exe",
    "wavebox.exe", "arc.exe", "duckduckgo.exe", "avastbrowser.exe", "avgbrowser.exe",
    "ccleanerbrowser.exe", "ucbrowser.exe", "maxthon.exe", "360chrome.exe", "360se.exe",
    "qqbrowser.exe", "sogouexplorer.exe", "baidubrowser.exe",
    "firefox.exe", "waterfox.exe", "librewolf.exe", "floorp.exe", "zen.exe",
    "palemoon.exe", "basilisk.exe", "seamonkey.exe", "k-meleon.exe",
    "iexplore.exe", "falkon.exe", "midori.exe", "otter-browser.exe", "qutebrowser.exe",
    "dooble.exe", "slimbrowser.exe", "lunascape.exe"
]

# Исключения, добавленные пользователем (имена exe в нижнем регистре); хранятся в настройках.
custom_excluded_processes = []
custom_exclusions_enabled = False  # по умолчанию выключено: список не действует, блок настроек скрыт
halo_enabled = False  # Halo Control: общий переключатель для обоих режимов
halo_verified_value = None  # значение Halo, уже сверенное с монитором (одинаковые уровни в обоих режимах)
halo_readable = None  # умеет ли монитор отдавать текущий Halo (0x46): None – не проверяли, False – нет
ui_theme = "dark"  # тема окон: dark (по умолчанию) / light / system
# Версия программы и репозиторий для проверки обновлений. При выпуске новой версии меняется только APP_VERSION.
APP_VERSION = "1.5.1"
GITHUB_REPO = "tawiss-cloud/TA-toggle"
UPDATE_CHECK_INTERVAL = 14 * 24 * 3600  # автоматическая проверка – раз в 14 дней
auto_update_check = False   # автоматическая проверка обновлений (по умолчанию выключена)
last_update_check = 0.0     # время последней проверки (unix-секунды)
update_info = None          # {"version": ..., "url": ...} – найденная новая версия, пока она новее установленной
legacy_migrated = False     # настройки уже перенесены из папки программы в AppData

# Последние позиции окон ("settings", "about"): {"x": int, "y": int}; хранятся в настройках.
window_positions = {}

def normalize_process_name(text):
    """Приводит ввод к имени exe в нижнем регистре или возвращает None, если ввод некорректен."""
    if not isinstance(text, str):
        return None
    name = text.strip().strip('"').replace("/", "\\").split("\\")[-1].strip().lower()
    if not name or any(c in name for c in '<>:"|?*'):
        return None
    if "." not in name:
        name += ".exe"
    return name if name.endswith(".exe") and len(name) > 4 else None

def is_excluded_process(process_name):
    name = process_name.lower()
    return (name in [p.lower() for p in EXCLUDED_PROCESSES]
            or (custom_exclusions_enabled and name in custom_excluded_processes))

def _win32_window_origin(win):
    """Реальная позиция окна от самой Windows (GetWindowRect внешней рамки) или None.
    Не зависит от кэша Tk: geometry() у некоторых окон остаётся прежним после перетаскивания."""
    try:
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        rect = RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return rect.left, rect.top
    except Exception:
        pass
    return None

def get_window_origin(win):
    """Левый верхний угол окна в тех же координатах, что принимает geometry().
    Если Windows и Tk расходятся – верим Windows (она знает, где окно на самом деле) и пишем в лог."""
    tk_pos = None
    try:
        m = re.match(r"\d+x\d+\+(-?\d+)\+(-?\d+)", win.geometry())
        if m:
            tk_pos = (int(m.group(1)), int(m.group(2)))
    except Exception:
        pass
    if tk_pos is None:
        tk_pos = (win.winfo_x(), win.winfo_y())
    win_pos = _win32_window_origin(win)
    if win_pos is not None and win_pos != tk_pos:
        return win_pos
    return tk_pos

def get_window_start_position(key, width, height):
    """Сохранённая позиция окна, приведённая к видимой области экранов, или None."""
    pos = window_positions.get(key)
    if not pos:
        return None
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    if vw <= 0 or vh <= 0:
        return None
    x = max(vx, min(pos["x"], vx + vw - width))
    y = max(vy, min(pos["y"], vy + vh - height))
    return x, y

# Все записи файла настроек идут под одной блокировкой: save_settings() вызывается из окна настроек, из фонового
# потока проверки обновлений и из потока монитора, а remember_window_position() читает и переписывает тот же файл.
# Блокировка охватывает и сборку данных, и запись, поэтому устаревший снимок не затрёт более свежий.
_settings_lock = threading.RLock()

def remember_window_position(key, win):
    with _settings_lock:
        _remember_window_position_unlocked(key, win)

def _remember_window_position_unlocked(key, win):
    """Запоминает позицию окна и дописывает её в файл настроек (остальные поля не трогает)."""
    try:
        x, y = get_window_origin(win)
        window_positions[key] = {"x": x, "y": y}
        data = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data['window_positions'] = window_positions
        write_json_atomic(SETTINGS_FILE, data)
    except Exception as e:
        log(f"Ошибка сохранения позиции окна: {e}")

def is_debug_active():
    return advanced_settings_enabled and debug_enabled

# Журнал работы всегда копится в памяти (сколько-то первых записей – запуск программы – и последние записи),
# чтобы его можно было приложить к отчёту о проблеме и при выключенном debug. В файл и в консоль пишет
# только включённый debug, как и раньше.
_LOG_HEAD_LINES = 100
_LOG_TAIL_LINES = 400
_log_head = []
_log_tail = collections.deque(maxlen=_LOG_TAIL_LINES)
_log_skipped = [0]   # сколько записей между началом и концом журнала уже вытеснено

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    if len(_log_head) < _LOG_HEAD_LINES:
        _log_head.append(line)
    else:
        if len(_log_tail) == _LOG_TAIL_LINES:
            _log_skipped[0] += 1
        _log_tail.append(line)
    if is_debug_active():
        print(msg)
        try:
            with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{line}\n")
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
    global pending_hotkey_mod, pending_hotkey_vk, HOTKEY_MODIFIERS, HOTKEY_VK
    pending_hotkey_mod = new_mod
    pending_hotkey_vk = new_vk
    posted = False
    if hotkey_thread_id:
        try:
            posted = bool(user32.PostThreadMessageW(hotkey_thread_id, WM_UPDATE_HOTKEY, 0, 0))
        except Exception as e:
            log(f"Ошибка отправки сообщения об обновлении горячей клавиши: {e}")
    if not posted and not app_exiting and not stop_hotkey_thread:
        # Поток горячей клавиши не работает (например, завершился из-за ошибки): запускаем его заново,
        # он зарегистрирует новое сочетание.
        log("Поток горячей клавиши не отвечает – запускаем заново")
        HOTKEY_MODIFIERS, HOTKEY_VK = new_mod, new_vk
        threading.Thread(target=lambda: hotkey_listener(tray_icon), daemon=True).start()

def _migrate_legacy_settings():
    """Прежние версии хранили monitor_settings.json рядом с программой. Переносим его в папку данных
    (AppData\\TA-toggle) и удаляем старый файл. Старый файл читаем и проверяем до любой записи, поэтому
    повреждённый файл ничего не затирает. В перенесённый файл пишется отметка migrated_from_legacy: если удалить
    старый файл не получилось (например, нет прав на папку программы), он больше не копируется повторно поверх
    новых настроек, а удаление пробуется снова."""
    legacy = os.path.join(_APP_DIR, "monitor_settings.json")
    try:
        if not os.path.exists(legacy) or os.path.abspath(legacy) == os.path.abspath(SETTINGS_FILE):
            return
        already = False
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    already = bool(json.load(f).get('migrated_from_legacy'))
            except Exception:
                already = False
        if not already:
            with open(legacy, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['migrated_from_legacy'] = True
            # Имя временного файла уникально для процесса и потока: load_settings() вызывается до проверки
            # единственного экземпляра, и второй запуск мог писать в тот же ".tmp".
            write_json_atomic(SETTINGS_FILE, data)
            log(f"Настройки перенесены: {legacy} -> {SETTINGS_FILE}")
        try:
            os.remove(legacy)
            log("Старый файл настроек удалён")
        except FileNotFoundError:
            pass   # одновременно запущенный второй экземпляр уже удалил файл
    except Exception as e:
        log(f"Не удалось перенести настройки в AppData: {e}")

def _sanitize_modes(raw):
    """Проверяет режимы из файла настроек. Не список из двух словарей – None (останутся режимы по умолчанию).
    Некорректные поля отдельного режима заменяются значениями по умолчанию, так что вручную испорченный файл
    не приводит к KeyError/TypeError при запуске или сохранении."""
    if not isinstance(raw, list) or len(raw) != 2 or not all(isinstance(m, dict) for m in raw):
        if raw is not None:
            log("Режимы в файле настроек повреждены – используются значения по умолчанию")
        return None
    def valid_int(value, low, high):
        return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    valid_dimming = {o["value"] for o in get_local_dimming_options()}
    result = []
    for default, item in zip(get_default_modes(), raw):
        mode = dict(default)
        if valid_int(item.get("brightness"), 0, 100):
            mode["brightness"] = item["brightness"]
        if item.get("local_dimming") in valid_dimming and not isinstance(item.get("local_dimming"), bool):
            mode["local_dimming"] = item["local_dimming"]
        if valid_int(item.get("halo"), 0, 100):
            mode["halo"] = item["halo"]
        result.append(mode)
    return result

def load_settings():
    _migrate_legacy_settings()
    global modes, hdr_settings, auto_switch_enabled, media_players_enabled, media_delay_seconds
    global HOTKEY_MODIFIERS, HOTKEY_VK, current_language, advanced_settings_enabled, debug_enabled
    global notification_style, icon_color_enabled, monitor_device_path, monitor_manual, custom_exclusions_enabled, halo_enabled, ui_theme
    global auto_update_check, last_update_check, update_info, legacy_migrated
    language_loaded = False
    modes_loaded = False
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'language' in data and data['language'] in SUPPORTED_LANGUAGES:
                    current_language = data['language']
                    language_loaded = True
                repaired_modes = _sanitize_modes(data.get('modes'))
                if repaired_modes is not None:
                    modes = repaired_modes
                    modes_loaded = True
                if isinstance(data.get('hdr_settings'), dict):
                    hs = data['hdr_settings']
                    if isinstance(hs.get('auto_set_preset'), bool):
                        hdr_settings['auto_set_preset'] = hs['auto_set_preset']
                    pn = hs.get('preset_number')
                    if isinstance(pn, int) and not isinstance(pn, bool) and 0 <= pn <= 255:
                        hdr_settings['preset_number'] = pn
                if isinstance(data.get('icon_colors'), list) and len(data['icon_colors']) == 2:
                    icon_colors[:] = [normalize_icon_color(c) or d
                                      for c, d in zip(data['icon_colors'], DEFAULT_ICON_COLORS)]
                    if icon_colors[1] == LEGACY_GAMING_ICON_COLOR:
                        icon_colors[1] = DEFAULT_ICON_COLORS[1]
                if isinstance(data.get('icon_color_enabled'), bool):
                    icon_color_enabled = data['icon_color_enabled']
                if data.get('notification_style') in NOTIFICATION_STYLES:
                    notification_style = data['notification_style']
                if isinstance(data.get('monitor_device_path'), str) and data['monitor_device_path']:
                    monitor_device_path = data['monitor_device_path']
                monitor_manual = bool(data.get('monitor_manual') is True and monitor_device_path)
                if isinstance(data.get('auto_switch_enabled'), bool):
                    auto_switch_enabled = data['auto_switch_enabled']
                if isinstance(data.get('media_players_enabled'), bool):
                    media_players_enabled = data['media_players_enabled']
                md = data.get('media_delay_seconds')
                if isinstance(md, int) and not isinstance(md, bool) and 1 <= md <= 60:
                    media_delay_seconds = md
                if isinstance(data.get('custom_excluded_processes'), list):
                    names = (normalize_process_name(x) for x in data['custom_excluded_processes'])
                    custom_excluded_processes[:] = list(dict.fromkeys(n for n in names if n))
                # Нет сохранённого флага (настройки старой версии): список, который пользователь уже собрал, не отключаем.
                if isinstance(data.get('custom_exclusions_enabled'), bool):
                    custom_exclusions_enabled = data['custom_exclusions_enabled']
                else:
                    custom_exclusions_enabled = bool(custom_excluded_processes)
                if isinstance(data.get('halo_enabled'), bool):
                    halo_enabled = data['halo_enabled']
                else:  # настройки старой версии: Halo был включён, если задан хотя бы в одном режиме
                    halo_enabled = any(isinstance(m.get('halo'), int) for m in modes)
                if data.get('ui_theme') in ('dark', 'light', 'system'):
                    ui_theme = data['ui_theme']
                legacy_migrated = bool(data.get('migrated_from_legacy', False))
                auto_update_check = bool(data.get('auto_update_check', False))
                if isinstance(data.get('last_update_check'), (int, float)):
                    last_update_check = float(data['last_update_check'])
                info = data.get('update_info')
                if (isinstance(info, dict) and isinstance(info.get('version'), str)
                        and isinstance(info.get('url'), str) and _version_newer(info['version'], APP_VERSION)):
                    update_info = {'version': info['version'], 'url': info['url']}
                else:
                    update_info = None
                if isinstance(data.get('window_positions'), dict):
                    for key in ("settings", "about"):
                        pos = data['window_positions'].get(key)
                        if (isinstance(pos, dict) and isinstance(pos.get('x'), int)
                                and isinstance(pos.get('y'), int)):
                            window_positions[key] = {"x": pos['x'], "y": pos['y']}
                if isinstance(data.get('advanced_settings_enabled'), bool):
                    advanced_settings_enabled = data['advanced_settings_enabled']
                if isinstance(data.get('debug_enabled'), bool):
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

# Текст последней ошибки save_settings() – чтобы вызывающий код мог показать пользователю причину.
last_save_error = ""

def write_json_atomic(path, data):
    """Пишет JSON во временный файл рядом и подменяет им целевой: оборванная запись (сбой, нехватка места)
    не оставит обрезанный файл настроек. Имя временного файла уникально для процесса и потока, а замена
    повторяется, если целевой файл на миг занят (антивирус, индексатор)."""
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        for attempt in range(3):
            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                break
            except RuntimeError:   # список или словарь изменили в другом потоке во время записи – пробуем ещё раз
                if attempt == 2:
                    raise
                time.sleep(0.02)
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

def save_settings():
    with _settings_lock:
        return _save_settings_unlocked()

def _save_settings_unlocked():
    global last_save_error
    try:
        data = {
            'language': current_language,
            'modes': modes,
            'hdr_settings': hdr_settings,
            'icon_colors': list(icon_colors),
            'icon_color_enabled': icon_color_enabled,
            'notification_style': notification_style,
            'monitor_device_path': monitor_device_path,
            'monitor_manual': monitor_manual,
            'auto_switch_enabled': auto_switch_enabled,
            'media_players_enabled': media_players_enabled,
            'media_delay_seconds': media_delay_seconds,
            'custom_exclusions_enabled': custom_exclusions_enabled,
            'halo_enabled': halo_enabled,
            'ui_theme': ui_theme,
            'migrated_from_legacy': legacy_migrated,
            'auto_update_check': auto_update_check,
            'last_update_check': last_update_check,
            'update_info': update_info,
            'custom_excluded_processes': list(custom_excluded_processes),
            'window_positions': window_positions,
            'advanced_settings_enabled': advanced_settings_enabled,
            'debug_enabled': debug_enabled,
            'hotkey_modifiers': HOTKEY_MODIFIERS,
            'hotkey_vk': HOTKEY_VK
        }
        write_json_atomic(SETTINGS_FILE, data)
        last_save_error = ""
        log("Настройки сохранены")
        return True
    except Exception as e:
        last_save_error = str(e)
        log(f"Ошибка сохранения: {e}")
        return False

# ===================== ПРОВЕРКА ОБНОВЛЕНИЙ =====================
def _parse_version(text):
    m = re.search(r"\d+(?:\.\d+)*", text or "")
    return tuple(int(x) for x in m.group(0).split(".")) if m else None

def _version_newer(candidate, current):
    a, b = _parse_version(candidate), _parse_version(current)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))

def _github_get(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}{path}",
                                 headers={"User-Agent": f"TA-toggle/{APP_VERSION}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.load(resp)

def fetch_latest_version():
    """(версия, ссылка на страницу версии) самой свежей версии на GitHub; None, если версий там нет.
    Сначала смотрим опубликованные релизы, а если их нет – теги репозитория."""
    try:
        data = _github_get("/releases/latest")
        version = _parse_version(data.get("tag_name", ""))
        if version:
            url = data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/tag/{data.get('tag_name')}"
            return ".".join(str(x) for x in version), url
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    best = None
    for tag in _github_get("/tags?per_page=50"):
        name = tag.get("name", "")
        if _parse_version(name) and (best is None or _version_newer(name, best)):
            best = name
    if best is None:
        return None
    return ".".join(str(x) for x in _parse_version(best)), f"https://github.com/{GITHUB_REPO}/releases/tag/{best}"

def check_for_update():
    """Сравнивает установленную версию с последней на GitHub и запоминает результат в настройках.
    Возвращает ("available", версия, ссылка), ("latest",) или ("error", текст)."""
    global last_update_check, update_info
    try:
        found = fetch_latest_version()
    except Exception as e:
        log(f"Проверка обновлений не удалась: {e}")
        return ("error", str(e))
    last_update_check = time.time()
    if found is None:   # в репозитории пока нет ни релизов, ни тегов – новее установленной ничего нет
        update_info = None
        save_settings()
        return ("latest",)
    version, url = found
    if _version_newer(version, APP_VERSION):
        update_info = {"version": version, "url": url}
        save_settings()
        return ("available", version, url)
    update_info = None
    save_settings()
    return ("latest",)

def check_update_and_notify():
    """Проверка обновлений с всплывающим уведомлением, если найдена новая версия (для автопроверки)."""
    result = check_for_update()
    if result[0] == "available":
        show_notification(t("notif_update_available", version=result[1]))
    return result

def maybe_auto_check_update():
    """Автопроверка при запуске: если включена и с прошлой проверки прошло 14 дней. Нашли новую версию – уведомление."""
    if not auto_update_check:
        return
    elapsed = time.time() - last_update_check
    if 0 <= elapsed < UPDATE_CHECK_INTERVAL:
        return
    check_update_and_notify()

# ===================== АВТОЗАПУСК С WINDOWS =====================
# Автозапуск – ярлык в папке автозагрузки пользователя (shell:startup): права администратора не нужны.
# Ярлык создаётся напрямую через COM (IShellLinkW) – без PowerShell и сторонних модулей.
# Источник истины – сама папка автозагрузки: файл можно удалить вручную или отключить в
# «Диспетчере задач → Автозагрузка».
AUTOSTART_LINK_NAME = "TA-toggle.lnk"
# Ярлык прежних версий: учитываем его и при сохранении заменяем новым (иначе программа стартовала бы дважды).
LEGACY_AUTOSTART_LINK_NAME = "Monitor Mode Switcher.lnk"
# Сюда «Диспетчер задач» записывает включение/выключение элементов папки автозагрузки.
_STARTUP_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"

_CLSID_SHELL_LINK = "{00021401-0000-0000-C000-000000000046}"
_IID_ISHELLLINK_W = "{000214F9-0000-0000-C000-000000000046}"
_IID_IPERSIST_FILE = "{0000010B-0000-0000-C000-000000000046}"
_CLSCTX_INPROC_SERVER = 1

class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.wintypes.DWORD), ("Data2", ctypes.wintypes.WORD),
                ("Data3", ctypes.wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

_ole32 = ctypes.WinDLL("ole32", use_last_error=True)
_ole32.CoInitialize.argtypes = [ctypes.c_void_p]
_ole32.CoInitialize.restype = ctypes.c_long
_ole32.CoUninitialize.argtypes = []
_ole32.CoUninitialize.restype = None
_ole32.CLSIDFromString.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.c_void_p]
_ole32.CLSIDFromString.restype = ctypes.c_long
_ole32.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.wintypes.DWORD,
                                    ctypes.c_void_p, ctypes.c_void_p]
_ole32.CoCreateInstance.restype = ctypes.c_long

def _guid(text):
    g = _GUID()
    hr = _ole32.CLSIDFromString(text, ctypes.byref(g))
    if hr != 0:
        raise OSError(f"CLSIDFromString: 0x{hr & 0xFFFFFFFF:08X}")
    return g

def _com_method(ptr, index, *argtypes):
    """Метод COM-интерфейса по номеру в таблице виртуальных методов. Ошибочный HRESULT -> OSError."""
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    func = proto(vtbl[index])
    return lambda *args: func(ptr, *args)

def _com_release(ptr):
    if not ptr.value:
        return
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(ptr)

def _create_shortcut(link_path, target, arguments, working_dir, description):
    init_hr = _ole32.CoInitialize(None)
    need_uninit = init_hr in (0, 1)   # S_OK / S_FALSE; иначе (например, другая модель потоков) не трогаем
    shell_link = ctypes.c_void_p()
    persist_file = ctypes.c_void_p()
    try:
        hr = _ole32.CoCreateInstance(ctypes.byref(_guid(_CLSID_SHELL_LINK)), None, _CLSCTX_INPROC_SERVER,
                                     ctypes.byref(_guid(_IID_ISHELLLINK_W)), ctypes.byref(shell_link))
        if hr != 0:
            raise OSError(f"CoCreateInstance: 0x{hr & 0xFFFFFFFF:08X}")
        _com_method(shell_link, 20, ctypes.wintypes.LPCWSTR)(target)        # SetPath
        _com_method(shell_link, 11, ctypes.wintypes.LPCWSTR)(arguments)     # SetArguments
        _com_method(shell_link, 9, ctypes.wintypes.LPCWSTR)(working_dir)    # SetWorkingDirectory
        _com_method(shell_link, 7, ctypes.wintypes.LPCWSTR)(description)    # SetDescription
        _com_method(shell_link, 0, ctypes.c_void_p, ctypes.c_void_p)(       # QueryInterface(IPersistFile)
            ctypes.byref(_guid(_IID_IPERSIST_FILE)), ctypes.byref(persist_file))
        _com_method(persist_file, 6, ctypes.wintypes.LPCWSTR, ctypes.wintypes.BOOL)(link_path, True)  # Save
    finally:
        _com_release(persist_file)
        _com_release(shell_link)
        if need_uninit:
            _ole32.CoUninitialize()

def _autostart_link_path(name=AUTOSTART_LINK_NAME):
    startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup")
    return os.path.join(startup, name)

def _autostart_target():
    """(программа, аргументы): для exe – он сам, для скрипта – pythonw.exe (без консольного окна) + путь к скрипту."""
    if getattr(sys, 'frozen', False):
        return sys.executable, ""
    interpreter = sys.executable
    pythonw = os.path.join(os.path.dirname(interpreter), "pythonw.exe")
    if os.path.basename(interpreter).lower() == "python.exe" and os.path.exists(pythonw):
        interpreter = pythonw
    return interpreter, f'"{os.path.abspath(__file__)}"'

def _delete_reg_value(key_path, value_name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, value_name)
    except FileNotFoundError:
        pass   # ключа или значения и так нет

def _startup_approved_disabled(name=AUTOSTART_LINK_NAME):
    """True, если ярлык отключён в «Диспетчере задач → Автозагрузка» (первый байт значения нечётный)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_APPROVED_KEY, 0, winreg.KEY_READ) as key:
            data, _ = winreg.QueryValueEx(key, name)
        return bool(data) and (data[0] & 1) == 1
    except OSError:
        return False

def _remove_autostart_link(name):
    try:
        os.remove(_autostart_link_path(name))
    except FileNotFoundError:
        pass
    _delete_reg_value(_STARTUP_APPROVED_KEY, name)

def is_autostart_enabled():
    try:
        for name in (AUTOSTART_LINK_NAME, LEGACY_AUTOSTART_LINK_NAME):
            if os.path.exists(_autostart_link_path(name)):
                return not _startup_approved_disabled(name)
        return False
    except Exception as e:
        log(f"Ошибка проверки автозапуска: {e}")
        return False

def set_autostart(enabled):
    """Включает/выключает автозапуск. Возвращает (успех, текст_ошибки).
    При включении ярлык всегда пересоздаётся с текущим путём – так автозапуск не указывает на
    старый файл, если программу переименовали или перенесли. Ярлык прежней версии удаляется."""
    try:
        if enabled:
            link_path = _autostart_link_path()
            target, arguments = _autostart_target()
            os.makedirs(os.path.dirname(link_path), exist_ok=True)
            _create_shortcut(link_path, target, arguments, _APP_DIR, "TA-toggle")
            log(f"Автозапуск включён: {link_path} -> {target} {arguments}".rstrip())
            _delete_reg_value(_STARTUP_APPROVED_KEY, AUTOSTART_LINK_NAME)   # снимаем «отключено в диспетчере задач»
            _remove_autostart_link(LEGACY_AUTOSTART_LINK_NAME)
        else:
            _remove_autostart_link(AUTOSTART_LINK_NAME)
            _remove_autostart_link(LEGACY_AUTOSTART_LINK_NAME)
            log("Автозапуск выключен")
        return True, ""
    except Exception as e:
        log(f"Ошибка изменения автозапуска: {e}")
        return False, str(e)

def migrate_legacy_autostart():
    """Прежняя версия создавала ярлык «Monitor Mode Switcher». Если автозапуск у пользователя был включён –
    заменяем его ярлыком TA-toggle; если был отключён в диспетчере задач – просто убираем прежний ярлык."""
    try:
        legacy = _autostart_link_path(LEGACY_AUTOSTART_LINK_NAME)
        if not os.path.exists(legacy):
            return
        if os.path.exists(_autostart_link_path()) or _startup_approved_disabled(LEGACY_AUTOSTART_LINK_NAME):
            _remove_autostart_link(LEGACY_AUTOSTART_LINK_NAME)
        else:
            set_autostart(True)
    except Exception as e:
        log(f"Ошибка переноса прежнего автозапуска: {e}")

# Индекс монитора в get_monitors() не постоянен: он меняется при подключении или отключении других мониторов,
# после выхода из сна, сброса драйвера. Поэтому индекс сверяется с сохранённым device path, а если монитор не найден
# (отключён, ещё не отвечает), поиск повторяется. Команды чужому монитору не отправляются. Сверка идёт по событиям, а
# не по таймеру: когда изменилось число мониторов, после ошибки операции, при смене выбора монитора и при запуске.
# В обычной работе никаких запросов к Windows и монитору ради этого не делается.
MONITOR_REDETECT_INTERVAL = 30.0     # как часто повторять поиск, если монитор не найден, секунды
_monitor_check = {"dirty": True, "count": None, "redetect": 0.0, "missing_logged": False}
monitor_marker_cache = {}   # device path -> True/False: признак Titan Army (VCP 0xE0), выясненный при поиске монитора
# monitor_index и monitor_device_path меняют разные потоки без общей блокировки. Это допустимо: присваивание числа или
# строки атомарно, а операция берёт индекс один раз (target_idx) и работает с тем монитором, который выбрала. Устаревшее
# значение исправляется следующей сверкой. Вызывать _resolve_monitor_index под monitor_io_lock нельзя: поиск монитора
# сам берёт эту (нереентрантную) блокировку.

def _resolve_monitor_index(monitors=None, redetect=True):
    """Актуальный индекс нашего монитора или None, если он не найден. Сверка идёт только когда индекс не определён,
    изменилось число мониторов или после ошибки операции (флаг dirty).
    redetect=False – только сверка по device path, без опроса мониторов по DDC/CI."""
    global monitor_index
    now = time.time()
    check = _monitor_check
    count = len(monitors) if monitors is not None else check["count"]
    due = monitor_index is None or check["count"] != count or check["dirty"]
    if not due:
        return monitor_index
    if monitors is None:
        try:
            monitors = get_monitors()
        except Exception as e:
            log(f"Ошибка перечисления мониторов: {e}")
            return monitor_index
    check["dirty"], check["count"] = False, len(monitors)
    saved = monitor_device_path
    if saved:
        if monitor_index is not None and monitor_index < len(monitors):
            current_path = _dc_device_path_for_monitor(monitor_index)
            if current_path == saved:
                return monitor_index
            if current_path is None:
                # DisplayConfig не ответил: сверить не удалось. Индекс не трогаем, проверим при следующем обращении.
                check["dirty"] = True
                return monitor_index
        for i in range(len(monitors)):
            if i != monitor_index and _dc_device_path_for_monitor(i) == saved:
                log(f"Индекс монитора изменился: {monitor_index} -> {i}")
                monitor_index = i
                return i
    elif monitor_index is not None and monitor_index < len(monitors):
        return monitor_index   # привязки нет (монитор выбран «по умолчанию»): сверять не с чем
    if not redetect:
        return monitor_index
    monitor_index = None   # монитор не найден: лучше не отвечать, чем отправить команду другому монитору
    if now - check["redetect"] < MONITOR_REDETECT_INTERVAL:
        return None
    check["redetect"] = now
    return monitor_index if find_titan_army_monitor() else None

def safe_monitor_operation(operation, monitor_idx=None):
    # get_monitors() может бросить исключение при перечислении мониторов –
    # поэтому весь блок, включая его, находится под try.
    try:
        monitors = get_monitors()
        if not monitors:
            log("Мониторы не найдены")
            return None
        target_idx = monitor_idx if monitor_idx is not None else _resolve_monitor_index(monitors)
        if target_idx is None:
            if not _monitor_check["missing_logged"]:
                _monitor_check["missing_logged"] = True
                log("Монитор не определён: поиск будет повторяться")
            return None
        _monitor_check["missing_logged"] = False
        if target_idx >= len(monitors):
            log(f"Неверный индекс монитора: {target_idx}")
            return None
        monitor = monitors[target_idx]
        # monitor_io_lock сериализует реальный обмен по DDC/CI между
        # потоками (см. её определение выше, зачем).
        with monitor_io_lock:
            with monitor:
                return operation(monitor)
    except Exception as e:
        log(f"Ошибка операции с монитором: {e}")
        _monitor_check["dirty"] = True   # после сбоя индекс перепроверяется при следующем обращении
        return None

def _is_media_player_name(name):
    return bool(name) and name.lower() in _MEDIA_PLAYER_NAMES

def _is_media_player_window(hwnd):
    if not hwnd or not media_players_enabled:
        return False
    try:
        name = get_process_name(hwnd)
    except Exception:
        return False
    return _is_media_player_name(name)

def media_player_window_open():
    """True, если открыто окно медиаплеера (в фокусе или нет). Нужно для ручного переключения: плеер может
    включать HDR в обход Windows, и это видно только по яркости, а не по системному режиму цвета."""
    if not media_players_enabled:
        return False
    try:
        return any(_is_media_player_name(name) for name, _ in list_windowed_processes())
    except Exception as e:
        log(f"Ошибка поиска окна медиаплеера: {e}")
        return False

def manual_hdr_method():
    """Способ проверки HDR для ручной попытки переключения. Если плеер открыт, но не в фокусе (и сессия
    не отслеживается: режим мог переключить плеер, а затем состояние сбросилось при потере фокуса), обычное
    определение дало бы «windows» – а он не видит HDR, включённый плеером. Поэтому при открытом
    медиаплеере всегда «media» (Windows → при «hdr» монитор не трогаем, иначе чтение яркости)."""
    if resolve_hdr_method() == "media" or media_player_window_open():
        return "media"
    return "windows"

def resolve_hdr_method(hwnd=None):
    """Способ проверки HDR: "media" – если задействован медиаплеер (окно hwnd, активное/запомненное
    окно или незавершённая медиа-сессия), иначе "windows". Подробности – в _measure_hdr()."""
    if hwnd is not None:
        return "media" if _is_media_player_window(hwnd) else "windows"
    if _is_media_player_window(user32.GetForegroundWindow()):
        return "media"
    gw = game_window_hwnd
    if gw is not None and user32.IsWindow(gw) and _is_media_player_window(gw):
        return "media"
    if last_session_media:
        return "media"
    return "windows"

def _query_brightness_hdr():
    """Одно реальное чтение яркости по DDC/CI: ровно 100 – признак HDR (монитор блокирует яркость).
    Это самый дорогой и самый «шумный» способ (шина DDC/CI, ложное срабатывание при яркости режима 100),
    поэтому он используется, только когда Windows не может ответить – см. _measure_hdr()."""
    def check_hdr(monitor):
        try:
            current_brightness, max_brightness = monitor.vcp.get_vcp_feature(VCP_BRIGHTNESS)
            return "hdr" if current_brightness == 100 else "ok"
        except Exception as e:
            log(f"Ошибка чтения яркости: {e}")
            return "error"
    result = safe_monitor_operation(check_hdr)
    return result if result is not None else "error"

def _measure_hdr(method):
    """Реальная проверка HDR: (результат "hdr"/"ok"/"error", пояснение для лога). Вызывать под hdr_cache_lock.
    Windows (системный режим цвета) отвечает без обращения к монитору, поэтому спрашиваем его первым,
    а яркость читаем, только когда без неё нельзя:
      "windows" – игры и обычные окна: яркость нужна лишь если Windows ответил "unsure" (сборка с
                  автоуправлением цветом без V2: флаг включён, но это может быть не HDR) или недоступен;
      "media"   – медиаплеер: если Windows говорит "hdr" – монитор не трогаем; иначе читаем яркость,
                  потому что плеер может включать HDR в обход Windows (проброс через драйвер);
      "brightness" – только яркость (явный запрос)."""
    global last_windows_hdr_error
    if method == "brightness":
        return _query_brightness_hdr(), "яркость"
    try:
        win = _query_windows_hdr()
        last_windows_hdr_error = None
    except Exception as e:
        # Одинаковую ошибку пишем в лог один раз, а не при каждой проверке.
        if str(e) != last_windows_hdr_error:
            log(f"HDR (Windows): ошибка проверки ({e}) – используем проверку по яркости")
            last_windows_hdr_error = str(e)
        return _query_brightness_hdr(), "яркость, Windows недоступен"
    detail = f"Windows, {last_windows_hdr_detail}" if last_windows_hdr_detail else "Windows"
    if method == "media":
        if win == "hdr":
            return "hdr", detail
        return _query_brightness_hdr(), f"{detail} → яркость (HDR-проброс плеера)"
    if win == "unsure":
        return _query_brightness_hdr(), f"{detail} → яркость (HDR или автоуправление цветом)"
    return win, detail

def is_hdr_enabled(force_refresh=False, hwnd=None, method=None):
    """"hdr" / "ok" / "error". Результат кэшируется на HDR_CACHE_TIME отдельно для каждого способа."""
    requested = method if method is not None else resolve_hdr_method(hwnd)
    with hdr_cache_lock:
        now = time.time()
        cached = hdr_method_cache.get(requested)
        # force_refresh уважаем, но не чаще, чем раз в HDR_FORCE_COALESCE_TIME (по записи кэша ЭТОГО
        # способа): одна логическая операция (нажатие хоткея) зовёт эту функцию несколько раз подряд.
        coalesced_force = force_refresh and (cached is None or (now - cached[1]) >= HDR_FORCE_COALESCE_TIME)
        if not (coalesced_force or cached is None or (now - cached[1]) >= HDR_CACHE_TIME):
            return cached[0]
        # Результат кладём под ЗАПРОШЕННЫЙ способ: иначе при сбое Windows-проверки запись не
        # появляется, кэш не срабатывает и каждый вызов идёт в монитор.
        result, how = _measure_hdr(requested)
        hdr_method_cache[requested] = (result, now)
        last = hdr_log_last.get(requested)
        if last is None or last[0] != (result, how) or now - last[1] >= HDR_LOG_REPEAT:
            hdr_log_last[requested] = ((result, how), now)
            log(f"HDR проверка [{requested}]: {result} ({how})")
        return result

def is_hdr_blocked(force_refresh=False, hwnd=None, method=None):
    """True, если переключение нужно заблокировать: HDR подтверждён ("hdr") или состояние не прочитано ("error").
    В сессионный кэш уместно запоминать только "hdr". Способ проверки – по hwnd (см. resolve_hdr_method)
    или явно через method."""
    result = is_hdr_enabled(force_refresh=force_refresh, hwnd=hwnd, method=method)
    return result in ("hdr", "error"), result

def reset_confirmed_hdr():
    global confirmed_hdr_active, hdr_confirmed_for_hwnd
    if confirmed_hdr_active:
        log("Сброс запомненного состояния HDR")
    confirmed_hdr_active = False
    hdr_confirmed_for_hwnd = None

def hdr_cache_valid_for(hwnd):
    """True, если confirmed_hdr_active относится именно к hwnd и это окно
    ещё существует. Другое окно или уже закрытое – кэш не годится, вызывающий
    код должен пойти на свежую проверку вместо использования кэша."""
    return (
        confirmed_hdr_active
        and hwnd is not None
        and hdr_confirmed_for_hwnd == hwnd
        and user32.IsWindow(hwnd)
    )

def update_tray_icon(mode_index=None):
    """Перерисовывает иконку трея цветом указанного (по умолчанию – текущего) режима."""
    if not tray_icon:
        return
    try:
        tray_icon.icon = create_image(mode_index)
    except Exception as e:
        log(f"Ошибка обновления иконки трея: {e}")

def update_tray_title(mode_index, process_name=None):
    """Единая точка обновления подсказки трея.
    process_name != None – суффикс с именем процесса (только для игрового
    режима, установленного автоматически). Иначе – просто название режима."""
    global tray_icon, last_tray_process_name
    last_tray_process_name = process_name
    if not tray_icon:
        return
    try:
        if process_name:
            tray_icon.title = t("tray_title_with_process",
                                mode=get_mode_name(mode_index),
                                process=process_name)
        else:
            tray_icon.title = t("tray_title", mode=get_mode_name(mode_index))
    except Exception as e:
        log(f"Ошибка обновления подсказки трея: {e}")
    # Подсказка и иконка меняются вместе – update_tray_title зовётся при каждой смене режима.
    update_tray_icon(mode_index)

def _round_notification_corners(win, width, height):
    """Скругляет углы всплывающего окна: на Windows 11 – средствами DWM (со сглаживанием),
    на более старых сборках – регионом окна (углы без сглаживания)."""
    win.update_idletasks()
    hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
    if _WIN_BUILD >= 22000:
        dwmapi = ctypes.windll.dwmapi
        corner = ctypes.c_int(2)            # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 33, ctypes.byref(corner), ctypes.sizeof(corner))
        border = ctypes.c_uint(0x003C3C3C)  # DWMWA_BORDER_COLOR: тонкая тёмно-серая рамка (BGR)
        dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 34, ctypes.byref(border), ctypes.sizeof(border))
    else:
        gdi32 = ctypes.windll.gdi32
        gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
        region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, 16, 16)
        user32.SetWindowRgn(ctypes.c_void_p(hwnd), ctypes.c_void_p(region), True)

def show_notification(message, error=False):
    # "off" – уведомления выключены. Ошибку (error=True: не сохранились настройки) показываем всё
    # равно: иначе изменения молча пропали бы после перезапуска.
    if notification_style == "off" and not error:
        return
    rounded = (notification_style == "win11")
    def create_notification():
        try:
            notification = tk.Toplevel()
            notification.overrideredirect(True)
            notification.attributes('-topmost', True)
            notification.attributes('-alpha', 0.95)
            notification.configure(bg='#2b2b2b', highlightbackground='#000000',
                                   highlightthickness=0 if rounded else 1)
            screen_width = notification.winfo_screenwidth()
            screen_height = notification.winfo_screenheight()
            window_width = 350
            window_height = 110 if error else 70
            x = screen_width - window_width - 10
            y = screen_height - window_height - 50
            notification.geometry(f'{window_width}x{window_height}+{x}+{y}')
            if rounded:
                try:
                    _round_notification_corners(notification, window_width, window_height)
                except Exception as e:
                    log(f"Не удалось скруглить углы уведомления: {e}")
            message_label = tk.Label(notification, text=message, fg='#F44336' if error else '#4CAF50',
                                     bg='#2b2b2b', font=('Arial', 11, 'bold'),
                                     wraplength=window_width - 20, justify='center')
            message_label.pack(expand=True)
            def close_notification():
                try:
                    notification.destroy()
                except:
                    pass
            notification.after(6000 if error else 2000, close_notification)
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
    # Если HDR активен, яркость читается как 100 и не отражает режим SDR.
    try:
        if is_hdr_enabled(force_refresh=True) == "hdr":
            log("HDR активен при старте – синхронизация режима по яркости пропущена (считаем стандартным)")
            current_mode_index = 0
            return
    except Exception as e:
        log(f"Не удалось проверить HDR при старте: {e}")

    # При старте это первое обращение к монитору за всю сессию – DDC/CI чаще всего «спотыкается» именно
    # на нём (контроллер ещё не готов сразу после открытия соединения). Без повторов единственная неудача
    # давала бы current_mode_index=0, даже если монитор реально в игровом режиме.
    brightness = local_dimming = None
    for attempt in range(3):
        result = get_current_monitor_settings()
        if result is None:
            log(f"get_current_monitor_settings вернул None (попытка {attempt+1}/3)")
            if attempt < 2:
                time.sleep(0.5)
            continue
        brightness, local_dimming = result
        if brightness is not None and local_dimming is not None:
            break
        log(f"Не удалось определить текущий режим при старте (попытка {attempt+1}/3)")
        if attempt < 2:
            time.sleep(0.5)
    if brightness is None or local_dimming is None:
        log("Режим при старте не определён – считаем стандартным")
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

def _remember_monitor(i):
    """Запоминает device path выбранного монитора (сохраняет настройки, только если он изменился)."""
    global monitor_device_path
    path = _dc_device_path_for_monitor(i)
    if path and path != monitor_device_path:
        monitor_device_path = path
        log(f"Монитор привязан к device path: {path}")
        save_settings()

def _probe_mode_switch(monitor, attempts=3, delay=0.3):
    """Признак Titan Army: VCP 0xE0 читается, максимум не меньше 14. Вызывать внутри `with monitor`.
    (True/False, пояснение) – монитор ответил (подходит / не подходит); (None, пояснение) – ответа не было.
    DDC/CI часто спотыкается на первом обращении, поэтому ошибка чтения не считается отрицательным ответом:
    чтение повторяется."""
    error = None
    for attempt in range(attempts):
        try:
            _, maximum = monitor.vcp.get_vcp_feature(VCP_MODE_SWITCH)
            return maximum >= 14, f"максимум {maximum}"
        except Exception as e:
            error = e
            if attempt < attempts - 1:
                time.sleep(delay)
    return None, f"ошибка чтения ({error})"

def find_titan_army_monitor():
    """Ищет монитор: сначала по сохранённому device path, затем по признаку Titan Army (VCP 0xE0 с максимумом
    не меньше 14 – подходит любой монитор этой серии). Если привязки ещё не было, берётся первый доступный
    монитор. Если привязка была, а монитор не найден, чужой монитор не выбирается: поиск повторится позже.
    Если монитор выбран вручную (monitor_manual), используется только он: без автоопределения."""
    global monitor_index
    # get_monitors() может бросить исключение при перечислении – перехватываем,
    # иначе упадёт вызывающий код (__main__ или toggle_mode).
    try:
        monitors = get_monitors()
    except Exception as e:
        log(f"Ошибка перечисления мониторов: {e}")
        return False
    log(f"Найдено мониторов: {len(monitors)}")
    infos = [_dc_target_info_for_monitor(i) for i in range(len(monitors))]
    for i, (path, name) in enumerate(infos):
        log(f"Монитор {i}: {name or '?'} ({path or 'device path не определён'})")
    saved = monitor_device_path
    manual = monitor_manual and bool(saved)
    found = None
    remember = False
    # Пробуем мониторы по DDC/CI только под monitor_io_lock, чтобы не мешать обмену из других потоков.
    with monitor_io_lock:
        if saved:
            for i, monitor in enumerate(monitors):
                if infos[i][0] != saved:
                    continue
                try:
                    with monitor:
                        pass
                except Exception as e:
                    log(f"Сохранённый монитор (индекс {i}) недоступен: {e}")
                    continue
                found = i
                log(f"Найден сохранённый монитор по device path (индекс {i})")
                break
            if found is None:
                log("Выбранный вручную монитор не найден" if manual else "Сохранённый монитор не найден – автоопределение")
        if found is None and not manual:
            for i, monitor in enumerate(monitors):
                try:
                    with monitor:
                        matches, detail = _probe_mode_switch(monitor)
                        if matches is not None and infos[i][0]:
                            monitor_marker_cache[infos[i][0]] = matches
                        if matches:
                            found = i
                            remember = True
                            log(f"Найден Titan Army (индекс {i}, VCP 0xE0: {detail})")
                            break
                        log(f"Монитор {i}: VCP 0xE0 не подходит ({detail})")
                except Exception as e:
                    log(f"Монитор {i}: ошибка доступа - {e}")
                    continue
        if found is None and not saved:
            for i, monitor in enumerate(monitors):
                try:
                    with monitor:
                        pass
                except Exception:
                    continue
                found = i
                log(f"Выбран первый доступный монитор (индекс {i})")
                break
    if found is None:
        monitor_index = None
        log("Подходящий монитор не найден!")
        return False
    monitor_index = found
    _monitor_check["dirty"], _monitor_check["count"] = False, len(monitors)
    if remember:
        _remember_monitor(found)
    return True

def probe_monitor_marker(path):
    """Проверяет признак Titan Army у монитора с этим device path (опрос по DDC/CI) и запоминает результат.
    True / False / None – как у _probe_mode_switch. Вызывать из рабочего потока."""
    try:
        monitors = get_monitors()
        with monitor_io_lock:
            for i, monitor in enumerate(monitors):
                if _dc_device_path_for_monitor(i) != path:
                    continue
                with monitor:
                    result, detail = _probe_mode_switch(monitor)
                log(f"Монитор {i}: проверка признака Titan Army: {detail}")
                if result is not None:
                    monitor_marker_cache[path] = result
                return result
    except Exception as e:
        log(f"Не удалось проверить монитор: {e}")
    return None

def list_monitor_choices(probe=False):
    """Мониторы для списка в настройках: [{"path", "name", "label", "compatible", "in_use"}]. Имя и номер дисплея
    берутся у Windows (DisplayConfig). compatible: True – признак Titan Army есть, False – нет, None – неизвестно.
    probe=False: к мониторам не обращаемся, признак берётся из памяти (его выяснил поиск монитора).
    probe=True: признак перечитывается по DDC/CI (кнопка обновления); это занимает время, вызывать из рабочего потока."""
    try:
        monitors = get_monitors()
    except Exception as e:
        log(f"Ошибка перечисления мониторов: {e}")
        return []
    choices = []
    for i in range(len(monitors)):
        path, name = _dc_target_info_for_monitor(i)
        if not path:
            continue   # без device path выбор не сохранить
        try:
            gdi = _dc_monitor_gdi_name(i)
        except Exception:
            gdi = None
        number = re.search(r"(\d+)$", gdi or "")
        label = name or t("monitor_unnamed")
        if number:
            label += f" ({t('monitor_display_number', n=number.group(1))})"
        if probe:
            probe_monitor_marker(path)
        compatible = monitor_marker_cache.get(path)
        choices.append({"path": path, "name": label, "compatible": compatible, "in_use": i == monitor_index,
                        "label": ("\u26a0 " if compatible is False else "") + label})   # \u26a0 – монитор не похож на Titan Army
    return choices

def rebind_monitor_selection():
    """После смены выбора монитора в настройках: индекс определяется заново (вызывать из рабочего потока)."""
    global monitor_index
    monitor_index = None
    _monitor_check["dirty"] = True
    _monitor_check["redetect"] = 0.0
    _monitor_check["missing_logged"] = False
    log("Выбор монитора изменён – поиск монитора заново")
    if not find_titan_army_monitor():
        log("Монитор не найден: поиск будет повторяться")

def normalize_icon_color(text):
    """'#RRGGBB' (пробелы по краям игнорируются) -> '#RRGGBB' в верхнем регистре, иначе None."""
    if not isinstance(text, str):
        return None
    value = text.strip()
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
        return None
    return value.upper()

def _render_icon(color_hex, size=64):
    """Чёрный фон и квадрат в центре цвета color_hex (#RRGGBB)."""
    r, g, b = (int(color_hex[i:i + 2], 16) for i in (1, 3, 5))
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    margin = 16
    d.rectangle([margin, margin, 64 - margin - 1, 64 - margin - 1],
                fill=(r, g, b, 255))
    d.rectangle([margin, margin, 64 - margin - 1, 64 - margin - 1],
                outline=(0, 0, 0, 255), width=1)
    if size != 64:
        img = img.resize((size, size), Image.NEAREST)
    return img

def create_image(mode_index=None):
    """Иконка трея: чёрный фон и квадрат в центре цвета режима mode_index (по умолчанию – текущего).
    При выключенной настройке цвета – всегда стандартный (белый) центр."""
    if not icon_color_enabled:
        return _render_icon(DEFAULT_ICON_COLORS[0])
    if mode_index is None:
        mode_index = current_mode_index
    try:
        color_hex = normalize_icon_color(icon_colors[mode_index]) or DEFAULT_ICON_COLORS[0]
    except (IndexError, TypeError):
        color_hex = DEFAULT_ICON_COLORS[0]
    return _render_icon(color_hex)

_window_icon_photos = []

def apply_window_icon(win):
    """Иконка программы (чёрная с белым центром) в углу окна вместо пера Tk. Вызывать из потока Tk."""
    try:
        if not _window_icon_photos:
            for size in (64, 32, 16):
                buf = io.BytesIO()
                _render_icon("#FFFFFF", size).save(buf, format="PNG")
                _window_icon_photos.append(
                    tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii")))
        win.iconphoto(False, *_window_icon_photos)
    except Exception as e:
        log(f"Ошибка установки иконки окна: {e}")

def ensure_halo(monitor, target):
    """Halo Control для текущего режима. Одинаковые уровни в обоих режимах: один раз сверяем с монитором
    (читаем 0x46) и пишем только при расхождении, дальше не трогаем. Разные уровни: пишем при каждой смене режима.
    Многие мониторы не отдают текущее значение Halo (код 0x46 только для записи): тогда сверка невозможна,
    значение один раз записывается без неё, и попытки чтения в этом сеансе больше не повторяются.
    Возвращает "cached" (уже сверено/записано ранее, монитор не трогали), "verified" (на мониторе уже нужное
    значение), "written" (значение записано) или False (записать не удалось)."""
    global halo_verified_value, halo_readable
    same = len(modes) == 2 and modes[0].get("halo") == modes[1].get("halo")
    if same and halo_verified_value == target:
        return "cached"
    time.sleep(VCP_PAIR_DELAY)   # пауза после записи затемнения, прежде чем обращаться к монитору снова
    if same and halo_readable is not False:
        try:
            current = monitor.vcp.get_vcp_feature(VCP_HALO)[0]
            halo_readable = True
        except Exception as e:
            current = None
            halo_readable = False
            log(f"Монитор не отдаёт текущее значение Halo (VCP 0x46): {str(e).rstrip('.')}. Сверка невозможна – значение записывается без неё")
        if current == target:
            halo_verified_value = target
            log(f"Halo уже {target} на мониторе, дальше не трогаем")
            return "verified"
    ok = set_halo(monitor, target)
    halo_verified_value = target if (ok and same) else None
    return "written" if ok else False

class PairWriteError(Exception):
    """Первая запись пары (0x99) удалась, а вторая (0x47 для LD, 0x46 для Halo) – нет."""

# Пауза между записью 0x99 и парной записью. Подбирается на ходу: если после паузы парная запись даёт
# ошибку шины, следующая попытка идёт с другой паузой (с 0 – как работали прежние версии), и рабочий
# вариант запоминается до конца сеанса.
ld_pair_delay = VCP_PAIR_DELAY

def write_vcp_pair(monitor, code, value, delay):
    """Пишет 0x99, ждёт delay секунд и пишет парный регистр code (0x47 для LD, 0x46 для Halo).
    Ошибка первой записи пробрасывается как есть, второй – как PairWriteError."""
    monitor.vcp.set_vcp_feature(VCP_LOCAL_DIMMING, value)
    if delay:
        time.sleep(delay)
    try:
        monitor.vcp.set_vcp_feature(code, value)
    except Exception as e:
        raise PairWriteError(str(e)) from e

def _set_with_pair(monitor, code, value, label, retries=3):
    """Записывает пару 0x99 + code с повторами. Провал парной записи – провал всей установки (раньше он
    молча считался успехом, и режим оставался со старым значением без повторов и «дожима»).
    Исключение: ошибка без упоминания шины I2C значит, что монитор не принимает сам код (не сбой передачи) –
    тогда, как и раньше, считаем успешной запись 0x99."""
    global ld_pair_delay
    second_write_failed = False
    for attempt in range(retries):
        delay = ld_pair_delay
        try:
            write_vcp_pair(monitor, code, value, delay)
            if second_write_failed:
                log(f"{label}: запись удалась с паузой {int(delay * 1000)} мс – используем её дальше")
            return True
        except PairWriteError as e:
            second_write_failed = True
            log(f"{label}: запись VCP 0x{code:02X} не удалась (пауза {int(delay * 1000)} мс, "
                f"попытка {attempt + 1}/{retries}): {e}")
            if "I2C" not in str(e):
                log(f"{label}: монитор не принимает VCP 0x{code:02X} – считаем установленным через 0x99")
                return True
            ld_pair_delay = 0.0 if delay > 0 else VCP_PAIR_DELAY   # следующая попытка – с другой паузой
        except Exception as e:
            log(f"Ошибка установки {label} (попытка {attempt + 1}/{retries}): {e}")
        if attempt < retries - 1:
            time.sleep(0.3)
    log(f"Не удалось установить {label} после нескольких попыток")
    return False

def set_local_dimming(monitor, value, retries=3):
    return _set_with_pair(monitor, VCP_LOCAL_DIMMING_ALT, value, "LD", retries)

def set_halo(monitor, value, retries=3):
    return _set_with_pair(monitor, VCP_HALO, value, "Halo", retries)

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
        success_dimming = set_local_dimming(monitor, mode["local_dimming"])
        if success_dimming:
            log(f"LD {mode['local_dimming']} установлен успешно")
        if halo_enabled and mode.get("halo") is not None:
            halo_result = ensure_halo(monitor, mode["halo"])
            if halo_result == "written":
                log(f"Halo {mode['halo']} записан в монитор")
            elif not halo_result:
                log("Не удалось установить Halo после нескольких попыток")
        return success_dimming, success_brightness
    result = safe_monitor_operation(set_mode)
    if result is None:
        log("safe_monitor_operation вернула None")
        return False, False, False
    success_dimming, success_brightness = result
    # Режим применён полностью, только если ОБА параметра (яркость и LD) выставлены:
    # с "or" local dimming мог молча остаться от прошлого режима.
    return (success_dimming and success_brightness), success_dimming, success_brightness

def retry_brightness_only(mode_index, attempts=5, delay=0.5):
    mode = modes[mode_index]
    for attempt in range(attempts):
        time.sleep(delay)
        if current_mode_index != mode_index:
            log("Дожим яркости отменён: режим уже изменился")
            return
        # get_current_monitor_settings() может вернуть None (монитор недоступен) –
        # распаковка в две переменные дала бы TypeError.
        result = get_current_monitor_settings()
        if result is None:
            log(f"Дожим яркости: монитор недоступен (попытка {attempt+1}/{attempts})")
            continue
        current_brightness, _ = result
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
        # См. комментарий в retry_brightness_only.
        result = get_current_monitor_settings()
        if result is None:
            log(f"Дожим LD: монитор недоступен (попытка {attempt+1}/{attempts})")
            continue
        _, current_local_dimming = result
        if current_local_dimming is not None and current_local_dimming == mode["local_dimming"]:
            log(f"LD уже {mode['local_dimming']}, дожим не требуется")
            return
        def set_dimming(monitor):
            return set_local_dimming(monitor, mode["local_dimming"])
        if safe_monitor_operation(set_dimming):
            log(f"LD {mode['local_dimming']} дожат успешно (попытка {attempt+1}/{attempts})")
            return
    log("Не удалось дожать LD после дополнительных попыток")

def apply_mode_by_index(index, force_hdr_check=False, hwnd=None, hdr_method=None):
    global current_mode_index, last_excluded_process_logged
    global confirmed_hdr_active, hdr_confirmed_for_hwnd, standard_return_blocked_logged
    global last_session_media
    if current_mode_index == index:
        return True

    # Сессионный кэш HDR – только для входа в игровой режим (index==1) и для того же окна;
    # возврат в стандартный его не использует, чтобы восстановиться сразу после выключения HDR.
    use_session_cache = (index == 1)

    if use_session_cache and not force_hdr_check and hdr_cache_valid_for(hwnd):
        return False
    if use_session_cache and confirmed_hdr_active and not force_hdr_check:
        # confirmed_hdr_active стоит, но hwnd не совпал (или окно уже
        # закрылось) – это другая сессия, кэш к ней не относится.
        confirmed_hdr_active = False
        hdr_confirmed_for_hwnd = None

    # Состояние проверки ДО вызова – ниже оно перезапишется в is_hdr_blocked().
    _cached_now = hdr_method_cache.get(hdr_method or resolve_hdr_method(hwnd))
    was_blocking_before = bool(_cached_now) and _cached_now[0] in ("hdr", "error")

    blocked, hdr_check = is_hdr_blocked(force_refresh=force_hdr_check, hwnd=hwnd, method=hdr_method)
    if blocked:
        if hdr_check == "hdr":
            if use_session_cache:
                confirmed_hdr_active = True
                hdr_confirmed_for_hwnd = hwnd
                log("HDR подтверждён – переключение режимов заблокировано (запомнено для этого окна)")
            elif not standard_return_blocked_logged:
                log("HDR подтверждён – возврат в стандартный режим отложен (проверим ещё раз позже)")
                standard_return_blocked_logged = True
        elif use_session_cache or not standard_return_blocked_logged:
            log("Ошибка чтения яркости – переключение режимов заблокировано (не запоминается)")
            if not use_session_cache:
                standard_return_blocked_logged = True
        return False

    # Свежая проверка подтвердила, что HDR не активен – если флаг оставался
    # True с прошлого раза, снимаем его, иначе он "залипнет".
    if confirmed_hdr_active:
        confirmed_hdr_active = False
        hdr_confirmed_for_hwnd = None
        log("Свежая проверка не подтвердила HDR – запомненное состояние снято")
    if standard_return_blocked_logged:
        standard_return_blocked_logged = False

    if was_blocking_before:
        # HDR только что перестал блокировать – монитор мог не закончить переход HDR->SDR,
        # и запись VCP молча игнорируется (так терялся Local Dimming). Даём паузу.
        log("HDR/ошибка только что снята – короткая пауза перед записью настроек")
        time.sleep(0.5)

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

    # Хотя бы один параметр выставлен – режим считаем применённым, недостающий дожимаем в фоне.
    current_mode_index = index
    if index == 0:
        last_session_media = False
    last_excluded_process_logged = None
    if not success_brightness:
        threading.Thread(target=retry_brightness_only, args=(index,), daemon=True).start()
    if not success_dimming:
        threading.Thread(target=retry_dimming_only, args=(index,), daemon=True).start()

    # Подсказка трея: суффикс с процессом – только для игрового режима,
    # установленного автоматически (hwnd передан вызывающим кодом).
    tray_process = None
    if index == 1 and hwnd is not None:
        try:
            tray_process = get_process_name(hwnd)
        except Exception as e:
            log(f"Не удалось получить имя процесса для подсказки трея: {e}")
            tray_process = None
    update_tray_title(current_mode_index, tray_process)

    show_notification(t("notif_mode", mode=get_mode_name(current_mode_index)))
    return True

def reset_manual_override_state():
    """Сбрасывает ручной режим (вызывать под game_state_lock). Режим монитора не трогает: если он остался
    игровым, ставится долг на возврат в стандартный – monitor_loop выполнит его, когда автоматика работает
    (если к тому времени игра активна, долг гасится при её обнаружении). True, если ручной режим был активен."""
    global manual_override_active, manual_override_waiting, game_window_hwnd, last_reported_state
    global game_counter, standard_restore_pending
    global standard_return_attempt_logged, standard_return_blocked_logged, standard_return_last_attempt_time
    if not (manual_override_active or manual_override_waiting):
        return False
    manual_override_active = False
    manual_override_waiting = False
    game_window_hwnd = None
    last_reported_state = None
    game_counter = 0
    if current_mode_index != 0:
        standard_restore_pending = True
        standard_return_attempt_logged = False
        standard_return_blocked_logged = False
        standard_return_last_attempt_time = 0.0
    log("Ручной режим сброшен (изменена настройка автопереключения)")
    return True

def on_auto_switch_changed(enabled):
    """Реакция на смену настройки автопереключения. Вызывать из отдельного потока, не из UI: берёт
    game_state_lock, который monitor_loop может держать на время обмена с монитором.
    Ручной режим относится к прежнему состоянию автоматики: если его оставить, после повторного включения
    monitor_loop продолжит ждать закрытия «ручного» окна и пропускать обычное определение игр – со стороны
    это выглядит как неработающая галочка. Таймер медиаплеера отменяем: при выключенной автоматике он не
    должен сменить режим."""
    global media_timer, last_session_media
    with game_state_lock:
        with media_timer_lock:
            if media_timer is not None:
                media_timer.cancel()
                media_timer = None
        reset_manual_override_state()
        if not enabled and last_session_media:
            last_session_media = False
            log("Авто-переключение выключено – сброс last_session_media")

def check_active_game_exclusion(newly_added):
    """Если текущая игровая сессия была запущена автоматически процессом, который
    только что добавлен в исключения, вернуть стандартный режим.
    Ручной режим (manual_override_active) не трогаем."""
    def worker():
        global game_window_hwnd, last_reported_state, game_counter
        global game_switch_attempt_logged, game_switch_attempt_hwnd
        global standard_restore_pending, standard_return_attempt_logged
        global standard_return_blocked_logged, standard_return_last_attempt_time
        global media_timer, last_media_player_logged

        with game_state_lock:
            if manual_override_active:
                return
            if game_window_hwnd is None or not user32.IsWindow(game_window_hwnd):
                return
            try:
                proc = get_process_name(game_window_hwnd)
            except Exception:
                proc = None
            if not proc or proc.lower() not in newly_added:
                return
            log(f"Процесс {proc} добавлен в исключения – возврат в стандартный режим")
            with media_timer_lock:
                if media_timer is not None:
                    media_timer.cancel()
                    media_timer = None
            # Сбрасываем состояние игровой сессии, чтобы monitor_loop
            # не пытался снова уйти в игровой по этому окну.
            game_window_hwnd = None
            last_reported_state = False
            game_counter = 0
            game_switch_attempt_logged = False
            game_switch_attempt_hwnd = None
            last_media_player_logged = None
            reset_confirmed_hdr()
            standard_restore_pending = False
            standard_return_attempt_logged = False
            standard_return_blocked_logged = False
            standard_return_last_attempt_time = 0.0
            if current_mode_index != 0:
                # apply_mode_by_index сам удержит monitor_io_lock и покажет уведомление.
                if not apply_mode_by_index(0):
                    # Если HDR/ошибка помешали – довозврат сделает monitor_loop.
                    standard_restore_pending = True
    threading.Thread(target=worker, daemon=True).start()

def get_process_name(hwnd):
    try:
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return None
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return os.path.basename(buffer.value)
        finally:
            kernel32.CloseHandle(handle)
        return None
    except Exception as e:
        log(f"Ошибка получения имени процесса: {e}")
        return None

def list_windowed_processes():
    """[(имя_процесса, заголовок_окна)] для окон, которые видны в Alt+Tab.
    Имя берётся тем же get_process_name(), что и при определении игры, поэтому
    совпадает с тем, что сравнивается со списком исключений."""
    found = {}
    own_pid = os.getpid()
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            ex_style = user32.GetWindowLongW(hwnd, -20)
            if (ex_style & 0x00000080) and not (ex_style & 0x00040000):
                return True
            cloaked = ctypes.wintypes.DWORD(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if cloaked.value:
                return True
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == own_pid:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            name = get_process_name(hwnd)
            if name:
                found.setdefault(name.lower(), buf.value)
        except Exception as e:
            log(f"Ошибка перечисления окон: {e}")
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    return sorted(found.items())

def is_game_window(hwnd):
    global last_excluded_process_logged, last_media_player_logged
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
        if is_excluded_process(process_name):
            if process_name != last_excluded_process_logged:
                log(f"Исключён процесс {process_name}")
                last_excluded_process_logged = process_name
            return False
    if _is_media_player_name(process_name):
        if not media_players_enabled:
            # Учёт медиаплееров выключен: полноэкранный плеер не должен считаться игрой по размеру и
            # стилю окна (is_game выше) – иначе настройка ничего не отключает.
            return False
        # Плеер – и на весь экран (is_game), и в окне, занимающем от половины экрана по обеим осям.
        if is_game or (width_ratio >= 0.50 and height_ratio >= 0.50):
            # Логируем только при смене медиаплеера, а не на каждой
            # секунде, пока то же самое окно остаётся на весь экран.
            if process_name != last_media_player_logged:
                log(f"Медиаплеер {process_name} – игровой режим")
                last_media_player_logged = process_name
            return True
        return False
    # last_media_player_logged НЕ сбрасываем здесь: иначе при сворачивании
    # плеера (foreground = рабочий стол) гейт обнулится, и при разворачивании
    # та же строка в логе появится снова. Сброс – только в точках реальной
    # смены сессии (закрытие игрового окна, ручное переключение режима).
    return is_game

def delayed_media_switch(hwnd):
    global media_timer, game_window_hwnd, last_reported_state
    global confirmed_hdr_active, hdr_confirmed_for_hwnd
    with media_timer_lock:
        media_timer = None
    # Другой поток (Timer) – берём тот же game_state_lock, что и monitor_loop()
    # (см. его определение выше, зачем).
    with game_state_lock:
        # Автопереключение могли выключить за время задержки – режим менять нельзя.
        if not auto_switch_enabled:
            log("Авто-переключение выключено – переключение медиаплеера отменено")
            return
        # Ручной режим пользователь выбрал вручную – автопереключение по медиа
        # срабатывать не должно (иначе через пару секунд после хоткея плеер
        # утянет режим обратно в игровой).
        if manual_override_active:
            log("Ручной режим активен – переключение медиаплеера отменено")
            return
        # Сначала дешёвые проверки (без DDC/CI): если плеер уже закрыт или больше
        # не медиаплеер/исключён, незачем лишний раз опрашивать монитор.
        if not user32.IsWindow(hwnd):
            log("Медиаплеер закрыт до срабатывания таймера – отмена")
            return
        if not is_game_window(hwnd):
            log("Окно перестало быть медиаплеером за время задержки – отмена")
            return
        if hdr_cache_valid_for(hwnd):
            log("HDR ранее подтверждён для этого окна – переключение медиаплеера отменено (без опроса монитора)")
            return
        blocked, hdr_check = is_hdr_blocked(force_refresh=True, hwnd=hwnd)
        if blocked:
            if hdr_check == "hdr":
                confirmed_hdr_active = True
                hdr_confirmed_for_hwnd = hwnd
                log("HDR подтверждён – переключение медиаплеера отменено (запомнено для этого окна)")
            else:
                log("Ошибка чтения яркости – переключение медиаплеера отменено")
            return
        if current_mode_index != 1:
            log(f"Медиаплеер подтверждён: {get_process_name(hwnd) or 'неизвестный процесс'} через {media_delay_seconds} сек – переключение на игровой режим")
            if apply_mode_by_index(1, hwnd=hwnd):
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
    global confirmed_hdr_active, hdr_confirmed_for_hwnd, game_switch_attempt_logged, game_switch_attempt_hwnd
    global standard_return_attempt_logged, standard_return_blocked_logged, standard_return_last_attempt_time
    global standard_restore_pending, last_session_media, last_media_player_logged

    while not stop_hotkey_thread:
        lock_held = False
        try:
            if not auto_switch_enabled:
                # Состояние при смене настройки сбрасывает on_auto_switch_changed() (под game_state_lock).
                time.sleep(1)
                continue

            hwnd = user32.GetForegroundWindow()

            # game_state_lock держим на всё решение и применение режима (release – перед каждым
            # выходом и в except), чтобы другие потоки не вклинились.
            game_state_lock.acquire()
            lock_held = True

            # ==================== РУЧНОЙ РЕЖИМ ====================
            if manual_override_active:
                if last_session_media and game_window_hwnd is None:
                    last_session_media = False
                    log("[Ручной режим] Сброс устаревшего last_session_media")

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
                        last_media_player_logged = None
                        reset_confirmed_hdr()
                        game_switch_attempt_logged = False
                        game_switch_attempt_hwnd = None
                        if current_mode_index != 0:
                            apply_mode_by_index(0)
                        game_state_lock.release()
                        lock_held = False
                        time.sleep(1)
                        continue
                game_state_lock.release()
                lock_held = False
                time.sleep(1)
                continue

            # ==================== СТАНДАРТНАЯ АВТО-ЛОГИКА ====================
            is_game = False
            is_media = False
            if hwnd:
                is_game = is_game_window(hwnd)
                if is_game and media_players_enabled:
                    process_name = get_process_name(hwnd)
                    if _is_media_player_name(process_name):
                        is_media = True

            if is_game:
                game_counter = min(game_counter + 1, GAME_THRESHOLD + 1)
                last_session_media = is_media
                # Обнаружена игра/медиа – мы больше не "застряли" в попытках
                # вернуться в стандартный режим, сбрасываем гейты этого лога.
                standard_return_attempt_logged = False
                standard_return_blocked_logged = False
                standard_return_last_attempt_time = 0.0
                standard_restore_pending = False

                if is_media:
                    if game_counter >= GAME_THRESHOLD:
                        if game_window_hwnd == hwnd and last_reported_state == True:
                            pass
                        elif hdr_cache_valid_for(hwnd):
                            pass
                        else:
                            # Предварительная проверка – только по Windows (без чтения монитора): окончательное
                            # решение принимает delayed_media_switch (способ "media", с проверкой яркости).
                            # Если Windows уже видит HDR – таймер запускать незачем.
                            blocked, hdr_check = is_hdr_blocked(hwnd=hwnd, method="windows")
                            if blocked:
                                if hdr_check == "hdr":
                                    confirmed_hdr_active = True
                                    hdr_confirmed_for_hwnd = hwnd
                                    log("HDR подтверждён – медиаплеер не активирует игровой режим (запомнено для этого окна)")
                                elif loop_log_gate["media_hdr_error"] != hwnd:
                                    # Цикл повторяет проверку каждую секунду: одну и ту же ошибку пишем один раз на окно.
                                    loop_log_gate["media_hdr_error"] = hwnd
                                    log("Ошибка чтения яркости – медиаплеер не активирует игровой режим")
                            else:
                                loop_log_gate["media_hdr_error"] = None
                                with media_timer_lock:
                                    if media_timer is None:
                                        log(f"Медиаплеер обнаружен: {process_name} – запускаем задержку {media_delay_seconds} сек")
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
                            # Логируем попытку один раз на окно – при смене окна
                            # (новая игра) лог пишется заново.
                            if not game_switch_attempt_logged or game_switch_attempt_hwnd != hwnd:
                                log(f"Обнаружена игра (подтверждено): {get_process_name(hwnd) or 'неизвестный процесс'} – переключение на игровой режим")
                                game_switch_attempt_logged = True
                                game_switch_attempt_hwnd = hwnd
                            if apply_mode_by_index(1, hwnd=hwnd):
                                game_window_hwnd = hwnd
                                last_reported_state = True
                                game_switch_attempt_logged = False
                                game_switch_attempt_hwnd = None
            else:
                game_counter = max(game_counter - 1, 0)
                # Таймер медиаплеера здесь НЕ отменяем: переключение должно произойти, даже если
                # плеер ушёл из фокуса (или активное окно на миг мигнуло при открытии файла/смене
                # размера). Актуальность окна проверяет delayed_media_switch: окно существует, не
                # свёрнуто и всё ещё медиаплеер.
                # last_session_media относится к сессии, начатой медиаплеером, и нужен, пока есть
                # что проверять способом "media": отслеживаемое окно (оно могло быть просто свёрнуто)
                # или невыполненный возврат в стандартный режим (standard_restore_pending). Закрытое
                # окно здесь НЕ считается концом сессии: его обработает ветка "Игра закрыта" ниже, и
                # возврат в SDR должен проверяться тем же способом, что и вход. Флаг снимается, когда
                # держать нечего – типично, если вход заблокировал HDR и переключения не было.
                # Условие game_counter == 0 – чтобы не сбрасывать при коротком переключении на другое окно.
                if (last_session_media and game_counter == 0
                        and game_window_hwnd is None and not standard_restore_pending):
                    log("Медиа-сессия завершена – сброс last_session_media")
                    last_session_media = False
                    last_media_player_logged = None

                if game_window_hwnd is not None:
                    if not user32.IsWindow(game_window_hwnd):
                        log("Игра закрыта (окно уничтожено) – возврат стандартного режима")
                        reset_confirmed_hdr()
                        game_switch_attempt_logged = False
                        game_switch_attempt_hwnd = None
                        # Окно закрыто – сессия завершена. Сбрасываем гейт лога
                        # «Медиаплеер X – игровой режим», чтобы следующая сессия
                        # того же плеера залогировалась заново.
                        last_media_player_logged = None
                        # Хендл сбрасываем ВСЕГДА, даже если переключение не удалось: иначе при блокировке
                        # HDR эта ветка срабатывала бы каждую секунду (окна уже нет, а условие очистки не
                        # наступило бы никогда).
                        game_window_hwnd = None
                        # Игра закрыта независимо от того, удастся ли применить SDR; долг по SDR –
                        # в отдельном флаге standard_restore_pending.
                        last_reported_state = False
                        if apply_mode_by_index(0):
                            standard_return_attempt_logged = False
                            standard_return_blocked_logged = False
                            standard_return_last_attempt_time = 0.0
                            standard_restore_pending = False
                        else:
                            # Не удалось – повтор сделает логика ниже по standard_restore_pending (с троттлингом).
                            standard_restore_pending = True
                    else:
                        if last_reported_state != True:
                            log("Игра уже запущена (свёрнута) – переключаем на игровой")
                            if apply_mode_by_index(1, hwnd=game_window_hwnd):
                                last_reported_state = True
                else:
                    if last_reported_state is None:
                        log("Игра/медиаплеер не обнаружена – состояние стандартное (без переключения)")
                        last_reported_state = False
                    if standard_restore_pending:
                        # Лог один раз за эпизод – иначе пишется каждую секунду, пока HDR заблокирован.
                        if not standard_return_attempt_logged:
                            log("Игра/медиаплеер не обнаружена – возврат стандартного режима")
                            standard_return_attempt_logged = True
                        # Опрос монитора троттлим отдельно от лога (первая попытка эпизода – сразу,
                        # standard_return_last_attempt_time сброшен в 0).
                        now_ts = time.time()
                        if now_ts - standard_return_last_attempt_time >= STANDARD_RETURN_RETRY_INTERVAL:
                            standard_return_last_attempt_time = now_ts
                            if apply_mode_by_index(0):
                                standard_restore_pending = False
                                standard_return_attempt_logged = False
                                standard_return_blocked_logged = False
                                standard_return_last_attempt_time = 0.0

            game_state_lock.release()
            lock_held = False

        except Exception as e:
            # Снимаем лок только если его держит эта итерация (lock_held): game_state_lock.locked()
            # мог быть True из-за другого потока, и release() сломал бы взаимоисключение.
            if lock_held:
                game_state_lock.release()
                lock_held = False
            log(f"Ошибка в мониторинге: {e}")

        time.sleep(1)

def toggle_mode(icon=None):
    global current_mode_index, last_switch_time, last_reported_state
    global manual_override_active, manual_override_waiting
    global game_window_hwnd, game_counter, confirmed_hdr_active, hdr_confirmed_for_hwnd
    global standard_return_attempt_logged, standard_return_blocked_logged, standard_return_last_attempt_time
    global standard_restore_pending, last_session_media, last_media_player_logged

    now = time.time()
    if now - last_switch_time < DELAY:
        return

    try:
        log("\n" + "="*50)
        log("Начало переключения режима")

        # Ручная попытка – всегда свежий опрос, независимо от запомненного.
        with game_state_lock:
            hdr_method = manual_hdr_method()
            blocked, hdr_check_result = is_hdr_blocked(force_refresh=True, method=hdr_method)
            # Ручное переключение не привязано к окну – сбрасываем hdr_confirmed_for_hwnd.
            confirmed_hdr_active = (hdr_check_result == "hdr")
            hdr_confirmed_for_hwnd = None
            standard_return_attempt_logged = False
            standard_return_blocked_logged = False
            standard_return_last_attempt_time = 0.0
            standard_restore_pending = False
            if blocked:
                log("HDR включен или ошибка чтения - переключение заблокировано (ручная попытка)")
                show_notification(t("notif_hdr_enabled"))
                return

            if monitor_index is None:
                if not find_titan_army_monitor():
                    return

            sync_current_mode()
            new_mode_index = 1 - current_mode_index

            if apply_mode_by_index(new_mode_index, force_hdr_check=True, hdr_method=hdr_method):
                last_switch_time = now
                mode_name = get_mode_name(current_mode_index)

                if new_mode_index == 0:
                    active_hwnd = user32.GetForegroundWindow()
                    if active_hwnd and is_game_window(active_hwnd):
                        manual_override_active = True
                        game_window_hwnd = active_hwnd
                        manual_override_waiting = False
                        last_reported_state = False
                        log(f"Ручной режим включён (стандартный), запомнено окно игры {hex(active_hwnd)}")
                    else:
                        manual_override_active = False
                        manual_override_waiting = False
                        game_window_hwnd = None
                        last_reported_state = False
                        log("Ручной режим выключен (переключение на стандартный, игра не активна)")
                else:
                    manual_override_active = True
                    last_session_media = False
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

                # Ручное переключение = смена сессии, гейт лога «Медиаплеер X –
                # игровой режим» сбрасываем, чтобы в новой сессии строка
                # появилась заново.
                last_media_player_logged = None
                # Подсказка трея и уведомление о режиме уже выведены в apply_mode_by_index – второй раз не нужны.

        log("="*50)
    except Exception as e:
        log(f"Ошибка переключения: {e}")

def get_local_dimming_name(value):
    for option in get_local_dimming_options():
        if option["value"] == value:
            return option["name"]
    return t("dimming_unknown")

# ===================== СОВРЕМЕННЫЙ ИНТЕРФЕЙС (стиль Windows 11) =====================
# Лёгкий набор виджетов на чистом tkinter: карточки со скруглёнными углами, переключатели,
# ползунки, кнопки. Цвета берутся из светлой/тёмной темы Windows (AppsUseLightTheme).
UI_FONT = "Segoe UI"
UI_FONT_SEMIBOLD = "Segoe UI Semibold"

# Акцентный цвет интерфейса совпадает с цветом текста всплывающих уведомлений (show_notification).
NOTIFY_ACCENT = "#4CAF50"

_UI_PALETTES = {
    "dark": {"bg": "#202020", "card": "#2B2B2B", "border": "#383838", "divider": "#383838",
             "text": "#FFFFFF", "muted": "#A0A0A0", "accent": NOTIFY_ACCENT, "on_accent": "#000000",
             "field": "#333333", "field_border": "#4A4A4A", "hover": "#383838", "pressed": "#2F2F2F",
             "thumb": "#6B6B6B", "off": "#A0A0A0", "disabled": "#6A6A6A", "warn": "#FFB84D",
             "accent_hover": "#66BB6A", "button": "#363636", "button_hover": "#404040",
             "nav_selected": "#323232", "nav_hover": "#292929"},
    "light": {"bg": "#F3F3F3", "card": "#FFFFFF", "border": "#E3E3E3", "divider": "#EBEBEB",
              "text": "#1A1A1A", "muted": "#5F5F5F", "accent": NOTIFY_ACCENT, "on_accent": "#000000",
              "field": "#FFFFFF", "field_border": "#C9C9C9", "hover": "#F0F0F0", "pressed": "#E8E8E8",
              "thumb": "#BDBDBD", "off": "#5F5F5F", "disabled": "#A8A8A8", "warn": "#9D5D00",
              "accent_hover": "#43A047", "button": "#FBFBFB", "button_hover": "#F3F3F3",
              "nav_selected": "#E4E4E4", "nav_hover": "#ECECEC"},
}

def ui_palette():
    """(палитра, это_тёмная_тема). Тема из настроек: «dark» (по умолчанию), «light» или «system»
    (по настройке «Режим приложений по умолчанию» в Windows)."""
    dark = True
    if ui_theme == "light":
        dark = False
    elif ui_theme == "system":
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                dark = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except Exception:
            pass
    return _UI_PALETTES["dark" if dark else "light"], dark

def _colorref(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return (b << 16) | (g << 8) | r

def ui_style_window(win, pal, dark):
    """Фон окна по палитре; тёмный/светлый заголовок и цвет шапки под фон (Windows 10 1809+ / 11)."""
    win.configure(bg=pal["bg"])
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi
        def set_attr(attr, value):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(v), ctypes.sizeof(v))
        set_attr(20, 1 if dark else 0)            # DWMWA_USE_IMMERSIVE_DARK_MODE
        set_attr(35, _colorref(pal["bg"]))        # DWMWA_CAPTION_COLOR (Windows 11)
        set_attr(36, _colorref(pal["text"]))      # DWMWA_TEXT_COLOR (Windows 11)
    except Exception:
        pass

def ui_setup_ttk(win, pal):
    """Стили ttk для выпадающих списков и полосы прокрутки (остальное рисуют свои виджеты)."""
    style = ttk.Style(win)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("W11.TCombobox", fieldbackground=pal["field"], background=pal["field"],
                    foreground=pal["text"], arrowcolor=pal["text"], bordercolor=pal["field_border"],
                    lightcolor=pal["field"], darkcolor=pal["field"], padding=(8, 5),
                    selectbackground=pal["field"], selectforeground=pal["text"])
    style.map("W11.TCombobox",
              fieldbackground=[("readonly", pal["field"]), ("disabled", pal["card"])],
              foreground=[("disabled", pal["disabled"])],
              bordercolor=[("focus", pal["accent"]), ("active", pal["accent"])],
              selectbackground=[("readonly", pal["field"])],
              selectforeground=[("readonly", pal["text"])],
              arrowcolor=[("disabled", pal["disabled"])])
    win.option_add("*TCombobox*Listbox.background", pal["card"])
    win.option_add("*TCombobox*Listbox.foreground", pal["text"])
    win.option_add("*TCombobox*Listbox.selectBackground", pal["accent"])
    win.option_add("*TCombobox*Listbox.selectForeground", pal["on_accent"])
    win.option_add("*TCombobox*Listbox.font", (UI_FONT, 10))
    style.layout("W11.Vertical.TScrollbar",
                 [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                     ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("W11.Vertical.TScrollbar", troughcolor=pal["bg"], background=pal["thumb"],
                    bordercolor=pal["bg"], lightcolor=pal["thumb"], darkcolor=pal["thumb"],
                    relief="flat", width=8, gripcount=0)
    style.map("W11.Vertical.TScrollbar", background=[("active", pal["muted"])],
              lightcolor=[("active", pal["muted"])], darkcolor=[("active", pal["muted"])])

def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


# Pillow нужен программе и для значка в трее, поэтому импортируется безусловно. Сглаживание использует
# rounded_rectangle (Pillow 8.2+): на более старой версии один раз отключаем его и рисуем примитивами canvas.
from PIL import Image as _PILImage, ImageDraw as _PILDraw
if not hasattr(_PILDraw.ImageDraw, "rounded_rectangle"):
    _PILImage = None

_AA_SCALE = 4
_aa_cache = {}


def _aa_image(w, h, bg, shapes, cache=True):
    """Изображение w×h со сглаживанием: фигуры рисуются в 4-кратном размере и уменьшаются. None – старый Pillow.
    Фигуры: ("rrect", x1, y1, x2, y2, r, fill, outline), ("circle", cx, cy, r, fill, outline),
    ("line", x1, y1, x2, y2, width, fill)."""
    if _PILImage is None or w < 1 or h < 1:
        return None
    key = (w, h, bg, tuple(shapes))
    photo = _aa_cache.get(key)
    if photo is not None:
        return photo
    try:
        s = _AA_SCALE
        img = _PILImage.new("RGB", (w * s, h * s), bg)
        draw = _PILDraw.Draw(img)
        for sh in shapes:
            if sh[0] == "rrect":
                _, x1, y1, x2, y2, r, fill, outline = sh
                draw.rounded_rectangle([x1 * s, y1 * s, x2 * s - 1, y2 * s - 1], radius=r * s,
                                       fill=fill or None, outline=outline or None, width=s)
            elif sh[0] == "circle":
                _, cx, cy, r, fill, outline = sh
                draw.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s - 1, (cy + r) * s - 1],
                             fill=fill or None, outline=outline or None, width=s)
            elif sh[0] == "arc":
                _, cx, cy, r, a0, a1, width, color = sh
                draw.arc([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], start=a0, end=a1,
                         fill=color, width=int(width * s))
            elif sh[0] == "poly":
                _, pts, fill = sh
                draw.polygon([c * s for c in pts], fill=fill)
                # Лёгкое скругление углов: обводка той же краской с круглым соединением.
                draw.line([c * s for c in pts] + [pts[0] * s, pts[1] * s], fill=fill, width=int(1.6 * s), joint="curve")
            elif sh[0] == "line":
                _, x1, y1, x2, y2, width, fill = sh
                draw.line([x1 * s, y1 * s, x2 * s, y2 * s], fill=fill, width=int(width * s))
                rr = width * s / 2
                for px, py in ((x1, y1), (x2, y2)):
                    draw.ellipse([px * s - rr, py * s - rr, px * s + rr, py * s + rr], fill=fill)
        resample = getattr(_PILImage, "Resampling", _PILImage).LANCZOS
        img = img.resize((w, h), resample)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        photo = tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        return None
    if cache and w * h <= 30000:
        if len(_aa_cache) > 400:
            _aa_cache.clear()
        _aa_cache[key] = photo
    return photo


def _track_focus(widget):
    """Кольцо фокуса рисуется только при переходе с клавиатуры (Tab). После щелчка мышью его нет:
    иначе обводка оставалась бы на последнем нажатом элементе, пока фокус не уйдёт на другой."""
    widget._ring = False
    widget._pointer = False

    def on_press(event):
        widget._pointer = True

    def on_in(event):
        widget._ring = not widget._pointer
        widget._pointer = False
        widget._draw()

    def on_out(event):
        widget._ring = False
        widget._pointer = False
        widget._draw()
    # Нажатие ловим на отдельном теге привязок, который идёт первым: собственный обработчик виджета может
    # вернуть "break", и тогда обычная привязка не сработала бы.
    tag = f"W11Focus{id(widget)}"
    widget.bindtags((tag,) + widget.bindtags())
    widget.bind_class(tag, "<ButtonPress-1>", on_press)
    widget.bind("<FocusIn>", on_in, add="+")
    widget.bind("<FocusOut>", on_out, add="+")


def _paint(canvas, w, h, bg, shapes, tag=None):
    """Рисует фигуры на canvas: сглаженным изображением, а без Pillow – примитивами canvas."""
    kw = {"tags": tag} if tag else {}
    photo = _aa_image(w, h, bg, shapes, cache=tag is None)
    if photo is not None:
        canvas._aa_photo = photo      # ссылка, чтобы изображение не удалил сборщик мусора
        canvas.create_image(0, 0, anchor="nw", image=photo, **kw)
        return
    for sh in shapes:
        if sh[0] == "rrect":
            _round_rect(canvas, sh[1], sh[2], sh[3], sh[4], sh[5], fill=sh[6] or "", outline=sh[7] or "", **kw)
        elif sh[0] == "circle":
            canvas.create_oval(sh[1] - sh[3], sh[2] - sh[3], sh[1] + sh[3], sh[2] + sh[3],
                               fill=sh[4] or "", outline=sh[5] or "", **kw)
        elif sh[0] == "arc":
            # В Tk углы идут против часовой стрелки, в Pillow – по часовой.
            canvas.create_arc(sh[1] - sh[3], sh[2] - sh[3], sh[1] + sh[3], sh[2] + sh[3], start=-sh[5],
                              extent=sh[5] - sh[4], style="arc", width=sh[6], outline=sh[7], **kw)
        elif sh[0] == "poly":
            canvas.create_polygon(*sh[1], fill=sh[2], outline=sh[2], **kw)
        elif sh[0] == "line":
            canvas.create_line(sh[1], sh[2], sh[3], sh[4], width=sh[5], fill=sh[6], capstyle="round", **kw)


class W11Toggle(tk.Canvas):
    """Переключатель как в Windows 11: включён – заливка акцентом и тёмный кружок справа."""
    def __init__(self, parent, pal, variable, command=None, bg=None):
        super().__init__(parent, width=46, height=24, bg=bg or pal["card"], highlightthickness=0,
                         bd=0, cursor="hand2", takefocus=1)
        self.pal, self.var, self.command, self.enabled = pal, variable, command, True
        self._bg = bg or pal["card"]
        self.bind("<Button-1>", self._click)
        self.bind("<space>", self._click)
        _track_focus(self)
        self._trace = variable.trace_add("write", lambda *a: self._draw())
        self.bind("<Destroy>", lambda e: self._untrace(), add="+")
        self._draw()

    def _untrace(self):
        try:
            self.var.trace_remove("write", self._trace)
        except Exception:
            pass

    def _click(self, event=None):
        if not self.enabled:
            return "break"
        self.focus_set()
        self.var.set(not self.var.get())
        if self.command:
            self.command()
        return "break"

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if self.enabled else "arrow")
        self._draw()

    def _draw(self):
        p = self.pal
        self.delete("all")
        on = bool(self.var.get())
        if on:
            track = p["accent"] if self.enabled else p["disabled"]
            shapes = [("rrect", 1, 1, 45, 23, 11, track, None),
                      ("circle", 34, 12, 7, p["on_accent"] if self.enabled else self._bg, None)]
        else:
            line = p["off"] if self.enabled else p["disabled"]
            shapes = [("rrect", 1, 1, 45, 23, 11, self._bg, line), ("circle", 12, 12, 5, line, None)]
        if self._ring and self.enabled:
            shapes.append(("rrect", 0, 0, 46, 24, 12, None, p["text"]))
        _paint(self, 46, 24, self._bg, shapes)


class W11Slider(tk.Canvas):
    """Ползунок: заполненная часть дорожки – акцентом, на бегунке акцентная точка. Работает и с клавиатурой."""
    PAD = 11

    def __init__(self, parent, pal, variable, from_=0, to=100, width=210, command=None, bg=None):
        super().__init__(parent, width=width, height=26, bg=bg or pal["card"], highlightthickness=0,
                         bd=0, cursor="hand2", takefocus=1)
        self.pal, self.var, self.lo, self.hi, self.command = pal, variable, from_, to, command
        self._bg = bg or pal["card"]
        self.enabled = True
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._mouse)
        self.bind("<B1-Motion>", self._mouse)
        for key, delta in (("<Left>", -1), ("<Down>", -1), ("<Right>", 1), ("<Up>", 1),
                           ("<Prior>", 10), ("<Next>", -10)):
            self.bind(key, lambda e, d=delta: self._nudge(d))
        _track_focus(self)
        self._trace = variable.trace_add("write", lambda *a: self._draw())
        self.bind("<Destroy>", lambda e: self._untrace(), add="+")

    def _untrace(self):
        try:
            self.var.trace_remove("write", self._trace)
        except Exception:
            pass

    def _value(self):
        try:
            return max(self.lo, min(self.hi, int(self.var.get())))
        except (tk.TclError, ValueError):
            return self.lo

    def _set(self, value):
        value = max(self.lo, min(self.hi, int(value)))
        if value != self._value():
            self.var.set(value)
            if self.command:
                self.command()

    def _mouse(self, event):
        if not self.enabled:
            return
        self.focus_set()
        span = max(1, (self.winfo_width() or int(self["width"])) - 2 * self.PAD)
        self._set(round(self.lo + (event.x - self.PAD) / span * (self.hi - self.lo)))

    def _nudge(self, delta):
        if self.enabled:
            self._set(self._value() + delta)
        return "break"

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if self.enabled else "arrow")
        self._draw()

    def _draw(self):
        p = self.pal
        self.delete("all")
        actual = self.winfo_width()   # до показа окна winfo_width() равен 1 – берём заданную ширину
        w = max(2 * self.PAD + 2, actual if actual > 1 else int(self["width"]))
        span = max(1, w - 2 * self.PAD)
        x = self.PAD + span * (self._value() - self.lo) / (self.hi - self.lo)
        cy = 13
        accent = p["accent"] if self.enabled else p["disabled"]
        ring = p["text"] if (self._ring and self.enabled) else p["field_border"]
        shapes = [("line", self.PAD, cy, w - self.PAD, cy, 4, p["thumb"] if self.enabled else p["field_border"])]
        if x > self.PAD:
            shapes.append(("line", self.PAD, cy, x, cy, 4, accent))
        shapes += [("circle", x, cy, 9, p["field"], ring), ("circle", x, cy, 5, accent, None)]
        _paint(self, w, 26, self._bg, shapes)


class W11Button(tk.Canvas):
    """Кнопка со скруглёнными углами. kind: 'accent' (главная) или 'default'."""
    def __init__(self, parent, pal, text, command, kind="default", bg=None, padx=18, pady=7, min_width=0):
        self.pal, self.command, self.kind, self._text = pal, command, kind, text
        self._bg = bg or pal["card"]
        self.font = tkfont.Font(family=UI_FONT, size=10)
        self.padx, self.pady, self.min_width = padx, pady, min_width
        w, h = self._size()
        super().__init__(parent, width=w, height=h, bg=bg or pal["card"], highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self._state = "normal"
        self.enabled = True
        self.bind("<Enter>", lambda e: self._set_state("hover"))
        self.bind("<Leave>", lambda e: self._set_state("normal"))
        self.bind("<ButtonPress-1>", lambda e: (self.focus_set(), self._set_state("pressed")))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda e: self._invoke())
        self.bind("<space>", lambda e: self._invoke())
        _track_focus(self)
        self._draw()

    def _size(self):
        return (max(self.min_width, self.font.measure(self._text) + 2 * self.padx),
                self.font.metrics("linespace") + 2 * self.pady)

    def set_text(self, text):
        self._text = text
        w, h = self._size()
        self.configure(width=w, height=h)
        self._draw()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if self.enabled else "arrow")
        self._draw()

    def _set_state(self, state):
        if self._state != state:
            self._state = state
            self._draw()

    def _release(self, event):
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self._set_state("hover" if inside else "normal")
        if inside:
            self._invoke()

    def _invoke(self):
        if self.enabled and self.command:
            self.command()

    def _draw(self):
        p = self.pal
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        if self.kind == "accent":
            fill = {"normal": p["accent"], "hover": p["accent_hover"], "pressed": p["accent"]}[self._state]
            outline, fg = fill, p["on_accent"]
        else:
            fill = {"normal": p["button"], "hover": p["button_hover"], "pressed": p["pressed"]}[self._state]
            outline, fg = p["field_border"], p["text"]
        if not self.enabled:
            fill, outline, fg = p["card"], p["field_border"], p["disabled"]
        elif self._ring:
            outline = p["text"]
        _paint(self, w, h, self._bg, [("rrect", 0, 0, w, h, 6, fill, outline)])
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self.font)


class W11NavItem(tk.Canvas):
    """Пункт бокового меню: выбранный отмечен плашкой и акцентной полоской слева, как в Параметрах Windows 11."""
    def __init__(self, parent, pal, text, command, bg=None):
        super().__init__(parent, height=40, bg=bg or pal["bg"], highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.pal, self.command, self._text = pal, command, text
        self._bg = bg or pal["bg"]
        self.font = tkfont.Font(family=UI_FONT, size=11)
        self.selected = False
        self.hover = False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: (self.focus_set(), self.command()))
        self.bind("<Return>", lambda e: self.command())
        self.bind("<space>", lambda e: self.command())
        _track_focus(self)

    def _set_hover(self, value):
        self.hover = value
        self._draw()

    def set_selected(self, value):
        self.selected = bool(value)
        self._draw()

    def _draw(self):
        p = self.pal
        self.delete("all")
        actual = self.winfo_width()
        w = max(20, actual if actual > 1 else 200)
        shapes = []
        if self.selected or self.hover:
            shapes.append(("rrect", 4, 3, w - 4, 37, 6, p["nav_selected"] if self.selected else p["nav_hover"], None))
        if self.selected:
            shapes.append(("line", 8, 12, 8, 28, 3, p["accent"]))
        if self._ring:
            shapes.append(("rrect", 4, 3, w - 4, 37, 6, None, p["muted"]))
        _paint(self, w, 40, self._bg, shapes)
        self.create_text(24, 20, text=self._text, anchor="w", font=self.font, fill=p["text"])


class W11Icon(tk.Canvas):
    """Маленький значок 28×28: 'refresh' (проверка обновлений), 'warn' (треугольник с восклицательным знаком)
    или 'report' (облачко с восклицательным знаком).
    С command ведёт себя как кнопка с подсветкой при наведении."""
    SIZE = 28
    _ring = False

    def __init__(self, parent, pal, icon, command=None, bg=None, size=None):
        size = size or self.SIZE   # размер задаётся только для значка 'report'; остальные нарисованы под 28
        super().__init__(parent, width=size, height=size, bg=bg or pal["bg"], highlightthickness=0,
                         bd=0, cursor="hand2" if command else "arrow", takefocus=1 if command else 0)
        self.size = size
        self.pal, self.icon, self.command, self._bg = pal, icon, command, bg or pal["bg"]
        self.hover = False
        self.busy = False
        if command:
            self.bind("<Enter>", lambda e: self._set_hover(True))
            self.bind("<Leave>", lambda e: self._set_hover(False))
            self.bind("<Button-1>", lambda e: self._invoke())
            self.bind("<Return>", lambda e: self._invoke())
            self.bind("<space>", lambda e: self._invoke())
            _track_focus(self)
        self._draw()

    def _set_hover(self, value):
        self.hover = value
        self._draw()

    def set_busy(self, busy):
        self.busy = bool(busy)
        self._draw()

    def _invoke(self):
        if self.command and not self.busy:
            self.command()

    def _draw(self):
        p = self.pal
        self.delete("all")
        shapes = []
        if self.command and (self.hover or self._ring) and not self.busy:
            shapes.append(("rrect", 0, 0, self.size, self.size, 6, p["nav_hover"], None))
        if self.icon == "refresh":
            color = p["disabled"] if self.busy else (p["text"] if self.hover else p["muted"])
            cx = cy = 14
            r, a1 = 6.5, 320
            shapes.append(("arc", cx, cy, r, 30, a1, 2, color))
            t_ = math.radians(a1)
            px, py = cx + r * math.cos(t_), cy + r * math.sin(t_)       # конец дуги
            tx, ty = -math.sin(t_), math.cos(t_)                         # касательная (по часовой)
            nx, ny = math.cos(t_), math.sin(t_)                          # радиус наружу
            tip = (px + tx * 4.2, py + ty * 4.2)
            b1 = (px - tx * 0.6 + nx * 3.6, py - ty * 0.6 + ny * 3.6)
            b2 = (px - tx * 0.6 - nx * 3.6, py - ty * 0.6 - ny * 3.6)
            shapes.append(("poly", (tip[0], tip[1], b1[0], b1[1], b2[0], b2[1]), color))
        elif self.icon == "report":   # облачко с «!»; знак рисуем цветом фона, чтобы он выглядел вырезом
            color = p["text"] if self.hover else p["muted"]
            cut = p["nav_hover"] if self.hover else self._bg
            # Рисунок задан на сетке 24×24 так, чтобы границы знака «!» попадали точно на пиксели (ось x=12, толщина 2):
            # при дробных координатах тонкий вырез получал размытые края и лишние светлые пиксели.
            k = self.size / 24.0
            shapes.append(("rrect", 2 * k, 3 * k, 22 * k, 19 * k, 5 * k, color, None))
            shapes.append(("poly", (6 * k, 17 * k, 6 * k, 22.5 * k, 12 * k, 17 * k), color))
            shapes.append(("rrect", 11 * k, 7 * k, 13 * k, 12 * k, 0.5 * k, cut, None))   # палочка «!»
            shapes.append(("rrect", 11 * k, 14 * k, 13 * k, 16 * k, 0.5 * k, cut, None))  # точка «!»
        else:   # warn: треугольник и восклицательный знак рисуем фигурами (шрифтовой «!» выходил за основание)
            shapes.append(("poly", (14, 4.5, 24.5, 22.5, 3.5, 22.5), p["warn"]))
            shapes.append(("line", 14, 10.6, 14, 15.6, 2.2, "#000000"))
            shapes.append(("circle", 14, 18.9, 1.35, "#000000", None))
        _paint(self, self.size, self.size, self._bg, shapes)


class W11Row:
    """Строка внутри карточки: слева заголовок и пояснение, справа элемент управления (self.right)."""
    def __init__(self, wrap, left, right, title_label, desc_label):
        self.wrap, self.left, self.right = wrap, left, right
        self.title_label, self.desc_label = title_label, desc_label

    def show(self):
        self.wrap.grid()

    def hide(self):
        self.wrap.grid_remove()

    def set_visible(self, visible):
        self.show() if visible else self.hide()

    def set_dim(self, dim, pal):
        """Приглушает заголовок строки (когда её элемент отключён)."""
        if self.title_label is not None:
            self.title_label.configure(fg=pal["disabled"] if dim else pal["text"])


class W11Card(tk.Canvas):
    """Карточка со скруглёнными углами и рамкой. Строки добавляются через add_row()."""
    INSET = 3

    def __init__(self, parent, pal):
        super().__init__(parent, bg=pal["bg"], highlightthickness=0, bd=0, height=10)
        self.pal = pal
        self.body = tk.Frame(self, bg=pal["card"])
        self.body.columnconfigure(0, weight=1)
        self._win = self.create_window(self.INSET, self.INSET, window=self.body, anchor="nw")
        self._rows = 0
        self.bind("<Configure>", self._on_canvas)
        self.body.bind("<Configure>", self._on_body)

    def _on_canvas(self, event):
        self.itemconfigure(self._win, width=max(1, event.width - 2 * self.INSET))
        self._redraw()

    def _on_body(self, event):
        self.configure(height=event.height + 2 * self.INSET)

    def _redraw(self):
        self.delete("bg")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 4 and h > 4:
            _paint(self, w, h, self.pal["bg"], [("rrect", 0, 0, w, h, 8, self.pal["card"], self.pal["border"])], tag="bg")
            self.tag_lower("bg")

    def add_row(self, title=None, desc=None, desc_color=None):
        p = self.pal
        n, self._rows = self._rows, self._rows + 1
        wrap = tk.Frame(self.body, bg=p["card"])
        wrap.grid(row=n, column=0, sticky="ew")
        if n > 0:
            tk.Frame(wrap, height=1, bg=p["divider"]).pack(fill="x")
        inner = tk.Frame(wrap, bg=p["card"])
        inner.pack(fill="x", padx=16, pady=9)
        right = tk.Frame(inner, bg=p["card"])
        right.pack(side="right", padx=(16, 0))
        left = tk.Frame(inner, bg=p["card"])
        left.pack(side="left", fill="x", expand=True)
        title_label = desc_label = None
        if title:
            title_label = tk.Label(left, text=title, bg=p["card"], fg=p["text"], font=(UI_FONT, 10),
                                   anchor="w", justify="left", wraplength=300)
            title_label.pack(anchor="w")
        if desc:
            desc_label = tk.Label(left, text=desc, bg=p["card"], fg=desc_color or p["muted"],
                                  font=(UI_FONT, 9), anchor="w", justify="left", wraplength=300)
            desc_label.pack(anchor="w", pady=(2, 0))
        if title_label or desc_label:
            labels = [lbl for lbl in (title_label, desc_label) if lbl is not None]
            left.bind("<Configure>", lambda e, ls=labels: [l.configure(wraplength=max(120, e.width - 4)) for l in ls])
        return W11Row(wrap, left, right, title_label, desc_label)


class W11Page(tk.Frame):
    """Колонка страницы: заголовки разделов и карточки (через grid, чтобы блоки можно было скрывать и показывать)."""
    def __init__(self, parent, pal):
        super().__init__(parent, bg=pal["bg"])
        self.pal = pal
        self.columnconfigure(0, weight=1)
        self._n = 0

    def _place(self, widget, pady):
        widget.grid(row=self._n, column=0, sticky="ew", pady=pady)
        self._n += 1
        return widget

    def title(self, text):
        return self._place(tk.Label(self, text=text, bg=self.pal["bg"], fg=self.pal["text"],
                                    font=(UI_FONT_SEMIBOLD, 20), anchor="w"), (0, 12))

    def section(self, text):
        return self._place(tk.Label(self, text=text, bg=self.pal["bg"], fg=self.pal["text"],
                                    font=(UI_FONT_SEMIBOLD, 11), anchor="w"), (14, 6))

    def card(self):
        return self._place(W11Card(self, self.pal), (0, 0))

    def gap(self, px=16):
        return self._place(tk.Frame(self, height=px, bg=self.pal["bg"]), 0)


def ui_entry(parent, pal, textvariable=None, width=8, justify="left"):
    return tk.Entry(parent, textvariable=textvariable, width=width, justify=justify, bg=pal["field"],
                    fg=pal["text"], insertbackground=pal["text"], relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=pal["field_border"],
                    highlightcolor=pal["accent"], disabledbackground=pal["card"],
                    disabledforeground=pal["disabled"], selectbackground=pal["accent"],
                    selectforeground=pal["on_accent"], font=(UI_FONT, 10))

def ui_combo(parent, values, variable, width=22):
    combo = ttk.Combobox(parent, style="W11.TCombobox", textvariable=variable, values=values,
                         state="readonly", width=width, font=(UI_FONT, 10))

    def release_focus(event):
        # После выбора значения фокус возвращается окну: рамка фокуса и подсветка текста не остаются на списке.
        event.widget.selection_clear()
        event.widget.winfo_toplevel().focus_set()
    combo.bind("<<ComboboxSelected>>", release_focus, add="+")
    return combo

def ui_label(parent, pal, text, muted=False, bold=False, size=10, bg=None, **kw):
    return tk.Label(parent, text=text, bg=bg or pal["card"], fg=pal["muted"] if muted else pal["text"],
                    font=(UI_FONT_SEMIBOLD if bold else UI_FONT, size), **kw)

def ui_toggle(parent, pal, variable, command=None, bg=None):
    """Переключатель с подписью «Вкл/Выкл» справа, как в Параметрах Windows 11."""
    frame = tk.Frame(parent, bg=bg or pal["card"])
    state_var = tk.StringVar()

    def refresh(*_):
        state_var.set(t("toggle_on") if variable.get() else t("toggle_off"))
    label = tk.Label(frame, textvariable=state_var, bg=bg or pal["card"], fg=pal["text"],
                     font=(UI_FONT, 10), width=5, anchor="w")
    toggle = W11Toggle(frame, pal, variable, command=command, bg=bg)
    label.pack(side="right", padx=(8, 0))
    toggle.pack(side="right")
    trace = variable.trace_add("write", refresh)
    frame.bind("<Destroy>", lambda e: _safe_untrace(variable, trace), add="+")
    refresh()
    frame.toggle, frame.state_label = toggle, label
    return frame

def _safe_untrace(variable, trace):
    try:
        variable.trace_remove("write", trace)
    except Exception:
        pass

def ui_bind_wheel(widget, canvas):
    """Прокрутка страницы колесом мыши над любым вложенным виджетом."""
    def on_wheel(event):
        canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")
        return "break"
    widget.bind("<MouseWheel>", on_wheel, add="+")
    for child in widget.winfo_children():
        ui_bind_wheel(child, canvas)

def ui_scrolled_page(window, pal, page_factory, footer_height=0):
    """Прокручиваемая страница. Возвращает (page, canvas, update_scroll)."""
    holder = tk.Frame(window, bg=pal["bg"])
    holder.pack(side="top", fill="both", expand=True)
    canvas = tk.Canvas(holder, bg=pal["bg"], highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(holder, orient="vertical", style="W11.Vertical.TScrollbar", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    outer = tk.Frame(canvas, bg=pal["bg"])
    outer.columnconfigure(0, weight=1)
    win_id = canvas.create_window(0, 0, window=outer, anchor="nw")
    page = page_factory(outer)
    page.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 20))
    state = {"scroll": None}

    def update_scroll(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        need = outer.winfo_reqheight() > canvas.winfo_height() > 1
        if need != state["scroll"]:
            state["scroll"] = need
            if need:
                scrollbar.pack(side="right", fill="y")
            else:
                scrollbar.pack_forget()
                canvas.yview_moveto(0)
    canvas.pack(side="left", fill="both", expand=True)
    outer.bind("<Configure>", update_scroll)
    canvas.bind("<Configure>", lambda e: (canvas.itemconfigure(win_id, width=e.width), update_scroll()))
    return page, canvas, update_scroll, holder


_settings_ui = {"window": None, "show_page": None}


# ===================== ОТЧЁТ О ПРОБЛЕМЕ (GitHub Issues) =====================
# Issue создаётся от имени самого пользователя: открывается страница «New issue» с заголовком и описанием.
# Ключ доступа к GitHub в программе не хранится. Журнал работы (он копится в памяти, см. log()) целиком в ссылку
# не помещается, поэтому текст отчёта уходит в буфер обмена, а пользователь вставляет его на странице (Ctrl+V).
_report_ui = {"window": None}
REPORT_URL_LIMIT = 1900     # ссылки длиннее надёжно открываются не во всех браузерах
REPORT_LOG_MAX_CHARS = 50000   # у описания Issue предел 65536 символов
REPORT_BODY_MAX = 64000        # итоговый текст отчёта не длиннее: с запасом до предела GitHub
REPORT_DESCRIPTION_MAX = 20000  # описание пользователя; остальное место получает журнал

def collect_system_info():
    """Сведения для отчёта: только версия, сборка Windows и состояние программы."""
    run = "exe" if getattr(sys, "frozen", False) else f"Python {sys.version.split()[0]}"
    try:
        mode_name = get_mode_name(current_mode_index)
    except Exception:
        mode_name = "?"
    return [("Version", APP_VERSION), ("Windows build", _WIN_BUILD or "?"), ("Language", current_language),
            ("Mode", mode_name), ("Debug", "on" if is_debug_active() else "off"), ("Run", run)]

def collect_recent_log():
    """(текст, число строк): начало журнала (запуск программы) и последние записи."""
    lines = list(_log_head)
    skipped = _log_skipped[0]
    tail = list(_log_tail)
    if skipped:
        lines.append(f"... {skipped} lines skipped ...")
    lines += tail
    text = "\n".join(lines)
    if len(text) > REPORT_LOG_MAX_CHARS:
        text = "...\n" + text[-REPORT_LOG_MAX_CHARS:]
    return text, len(lines)

def build_issue_body(description, include_system, log_text=None, log_lines=0):
    description = description.strip()
    if len(description) > REPORT_DESCRIPTION_MAX:
        description = description[:REPORT_DESCRIPTION_MAX] + "..."
    parts = [f"## {t('report_body_description')}", description or "-", ""]
    if log_text:
        # Журналу достаётся всё место, что осталось под предел GitHub (запас 1500 символов на заголовки и сведения о системе).
        budget = max(0, REPORT_BODY_MAX - len(description) - 1500)
        if len(log_text) > budget:
            log_text = "...\n" + log_text[-budget:]
        # Ограждение длиннее любой цепочки обратных кавычек в журнале, иначе блок закроется раньше времени.
        longest = max((len(run) for run in re.findall(r"`+", log_text)), default=0)
        fence = "`" * max(4, longest + 1)
        parts += [f"## {t('report_body_log')}", "<details>",
                  f"<summary>{t('report_body_log_summary', count=log_lines)}</summary>", "",
                  fence, log_text, fence, "", "</details>", ""]
    if include_system:
        parts.append(f"## {t('report_body_system')}")
        parts += [f"- {key}: {value}" for key, value in collect_system_info()]
    return "\n".join(parts).rstrip() + "\n"

def build_issue_url(title, body):
    query = urllib.parse.urlencode({"title": title, "body": body}, quote_via=urllib.parse.quote)
    return f"https://github.com/{GITHUB_REPO}/issues/new?{query}"

def _bind_clipboard_keys(widget):
    """Ctrl+C/V/X/A по коду клавиши: в Tk при русской раскладке они иначе не срабатывают."""
    def on_key(event):
        action = {86: "<<Paste>>", 67: "<<Copy>>", 88: "<<Cut>>"}.get(event.keycode)
        if action:
            widget.event_generate(action)
            return "break"
        if event.keycode == 65:
            if isinstance(widget, tk.Text):
                widget.tag_add("sel", "1.0", "end-1c")
            else:
                widget.select_range(0, "end")
                widget.icursor("end")
            return "break"
    widget.bind("<Control-KeyPress>", on_key)

def show_log_preview(parent, pal, dark, text):
    """Окно только для чтения: что именно из журнала попадёт в отчёт."""
    win = tk.Toplevel(parent)
    win.withdraw()
    apply_window_icon(win)
    win.title(t("report_preview_title"))
    ui_style_window(win, pal, dark)
    win.transient(parent)
    footer = tk.Frame(win, bg=pal["bg"])
    footer.pack(side="bottom", fill="x")
    tk.Frame(footer, height=1, bg=pal["divider"]).pack(fill="x")
    W11Button(footer, pal, t("btn_close"), win.destroy, bg=pal["bg"], min_width=110).pack(
        side="right", padx=(0, 24), pady=12)

    def copy_log():
        try:
            win.clipboard_clear()
            win.clipboard_append(text or "")
            win.update()
        except tk.TclError:
            pass
    W11Button(footer, pal, t("btn_copy"), copy_log, bg=pal["bg"], min_width=110).pack(
        side="right", padx=(0, 8), pady=12)
    frame = tk.Frame(win, bg=pal["bg"])
    frame.pack(fill="both", expand=True, padx=(20, 12), pady=(16, 12))
    scroll = ttk.Scrollbar(frame, orient="vertical", style="W11.Vertical.TScrollbar")
    scroll.pack(side="right", fill="y")
    view = tk.Text(frame, wrap="word", bg=pal["field"], fg=pal["text"], relief="flat", bd=0,
                   highlightthickness=1, highlightbackground=pal["field_border"], highlightcolor=pal["field_border"],
                   selectbackground=pal["accent"], selectforeground=pal["on_accent"], font=("Consolas", 9),
                   padx=8, pady=6, yscrollcommand=scroll.set)
    view.pack(side="left", fill="both", expand=True)
    scroll.configure(command=view.yview)
    view.insert("1.0", text or t("report_log_empty"))
    view.configure(state="disabled")
    _bind_clipboard_keys(view)
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    win.geometry(f"760x480+{px + 30}+{py + 30}")
    win.deiconify()
    ui_style_window(win, pal, dark)
    win.focus_force()

def show_issue_report_dialog():
    previous = _report_ui.get("window")
    try:
        if previous is not None and previous.winfo_exists():
            previous.deiconify()
            previous.lift()
            previous.focus_force()
            return
    except tk.TclError:
        pass
    pal, dark = ui_palette()
    width = 640
    inner_w = width - 48
    dialog = tk.Toplevel()
    dialog.withdraw()
    apply_window_icon(dialog)
    dialog.title(t("report_title"))
    dialog.resizable(False, False)
    ui_style_window(dialog, pal, dark)
    ui_setup_ttk(dialog, pal)
    _report_ui["window"] = dialog

    title_var = tk.StringVar()
    system_var = tk.BooleanVar(value=True)
    log_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar()
    ui = {}

    def set_status(text, color=None):
        status_var.set(text)
        ui["status"].configure(fg=color or pal["warn"])

    def refresh_log_state(*_):
        try:
            on = is_debug_active()
            ui["log_row"].desc_label.configure(
                text=t("report_log_on" if on else "report_log_off", file=DEBUG_LOG_FILE),
                fg=pal["accent"] if on else pal["muted"])
        except tk.TclError:
            pass

    def open_settings():
        create_settings_window(start_page="advanced")

    def show_log_file():
        try:
            if os.path.exists(DEBUG_LOG_FILE):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(DEBUG_LOG_FILE)])
            else:
                set_status(t("report_log_missing"))
        except Exception as e:
            log(f"Не удалось показать файл лога: {e}")

    def preview_log():
        show_log_preview(dialog, pal, dark, collect_recent_log()[0])

    def create_report():
        title = title_var.get().strip()[:120]
        description = ui["text"].get("1.0", "end").strip()
        if not title:
            set_status(t("report_err_title"))
            ui["entry"].focus_set()
            return
        if not description:
            set_status(t("report_err_desc"))
            ui["text"].focus_set()
            return
        if len(description) > REPORT_DESCRIPTION_MAX:
            set_status(t("report_err_desc_long", limit=REPORT_DESCRIPTION_MAX))
            ui["text"].focus_set()
            return
        include_log = log_var.get()
        log_text, log_lines = collect_recent_log() if include_log else (None, 0)
        body = build_issue_body(description, system_var.get(), log_text, log_lines)
        url = build_issue_url(title, body)
        note = None
        if include_log or len(url) > REPORT_URL_LIMIT:
            # Длинный текст в ссылку не кладём: он уходит в буфер обмена, а в ссылке остаётся только заголовок.
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(body)
                dialog.update()
                note = t("report_clipboard_note")
                url = build_issue_url(title, t("report_body_paste"))
            except tk.TclError:
                note = t("report_clipboard_failed")
                short_body = build_issue_body(description, system_var.get())
                url = build_issue_url(title, short_body)
                if len(url) > REPORT_URL_LIMIT:
                    url = build_issue_url(title, "")
        try:
            opened = webbrowser.open(url)
        except Exception as e:
            log(f"Не удалось открыть браузер: {e}")
            opened = False
        if not opened:
            set_status(t("report_open_failed", url=f"https://github.com/{GITHUB_REPO}/issues/new"))
            return
        log("Открыта страница нового Issue на GitHub")
        set_status(t("report_opened") + (" " + note if note else ""), pal["accent"])

    # ---------- нижняя панель ----------
    footer = tk.Frame(dialog, bg=pal["bg"])
    footer.pack(side="bottom", fill="x")
    tk.Frame(footer, height=1, bg=pal["divider"]).pack(fill="x")
    buttons = tk.Frame(footer, bg=pal["bg"])
    buttons.pack(fill="x", padx=24, pady=12)
    W11Button(buttons, pal, t("btn_close"), dialog.destroy, bg=pal["bg"], min_width=110).pack(side="right")
    W11Button(buttons, pal, t("report_create"), create_report, kind="accent", bg=pal["bg"],
              min_width=160).pack(side="right", padx=(0, 8))

    # ---------- содержимое ----------
    body = tk.Frame(dialog, bg=pal["bg"])
    body.pack(fill="both", expand=True, padx=24, pady=(20, 6))

    def heading(text, size, pady):
        tk.Label(body, text=text, bg=pal["bg"], fg=pal["text"], font=(UI_FONT_SEMIBOLD, size),
                 anchor="w").pack(fill="x", pady=pady)

    heading(t("report_title"), 15, 0)
    tk.Label(body, text=t("report_intro"), bg=pal["bg"], fg=pal["muted"], font=(UI_FONT, 10), anchor="w",
             justify="left", wraplength=inner_w).pack(fill="x", pady=(6, 0))

    heading(t("report_steps_title"), 11, (14, 6))
    card = W11Card(body, pal)
    card.pack(fill="x")
    steps_row = card.add_row()
    step_texts = (t("report_step1"), t("report_step2", create=t("report_create")), t("report_step3"))
    step_labels = []
    for text in step_texts:
        label = tk.Label(steps_row.left, text=text, bg=pal["card"], fg=pal["text"], font=(UI_FONT, 10),
                         anchor="w", justify="left", wraplength=inner_w - 60)
        label.pack(anchor="w", pady=2)
        step_labels.append(label)
    steps_row.left.bind("<Configure>",
                        lambda e: [l.configure(wraplength=max(120, e.width - 4)) for l in step_labels])
    log_row = card.add_row(t("report_log_title"), desc=" ")
    ui["log_row"] = log_row
    W11Button(log_row.right, pal, t("report_open_settings"), open_settings).pack(side="left", padx=(0, 8))
    W11Button(log_row.right, pal, t("report_show_log"), show_log_file).pack(side="left")
    refresh_log_state()

    heading(t("report_form_title"), 11, (14, 6))
    tk.Label(body, text=t("report_field_title"), bg=pal["bg"], fg=pal["text"], font=(UI_FONT, 10),
             anchor="w").pack(fill="x")
    entry = ui_entry(body, pal, textvariable=title_var, width=10)
    entry.pack(fill="x", pady=(4, 10), ipady=5)
    ui["entry"] = entry
    tk.Label(body, text=t("report_field_desc"), bg=pal["bg"], fg=pal["text"], font=(UI_FONT, 10),
             anchor="w").pack(fill="x")
    tk.Label(body, text=t("report_desc_hint"), bg=pal["bg"], fg=pal["muted"], font=(UI_FONT, 9),
             anchor="w").pack(fill="x")
    text_widget = tk.Text(body, height=6, wrap="word", bg=pal["field"], fg=pal["text"],
                          insertbackground=pal["text"], relief="flat", bd=0, highlightthickness=1,
                          highlightbackground=pal["field_border"], highlightcolor=pal["accent"],
                          selectbackground=pal["accent"], selectforeground=pal["on_accent"],
                          font=(UI_FONT, 10), padx=8, pady=6, undo=True)
    text_widget.pack(fill="x", pady=(4, 10))
    ui["text"] = text_widget
    _bind_clipboard_keys(entry)
    _bind_clipboard_keys(text_widget)

    options_card = W11Card(body, pal)
    options_card.pack(fill="x")
    log_count = collect_recent_log()[1]
    include_log_row = options_card.add_row(t("report_include_log"), desc=t("report_include_log_desc", count=log_count))
    W11Button(include_log_row.right, pal, t("report_preview"), preview_log).pack(side="left", padx=(0, 12))
    ui_toggle(include_log_row.right, pal, log_var).pack(side="left")
    system_row = options_card.add_row(t("report_include_system"), desc=t("report_include_system_desc"))
    ui_toggle(system_row.right, pal, system_var).pack()

    status = tk.Label(body, textvariable=status_var, bg=pal["bg"], fg=pal["warn"], font=(UI_FONT, 9),
                      anchor="w", justify="left", wraplength=inner_w)
    status.pack(fill="x", pady=(8, 0))
    ui["status"] = status

    # Состояние записи в файл обновляется, когда пользователь возвращается в окно из настроек.
    dialog.bind("<FocusIn>", refresh_log_state, add="+")

    # Окно показываем невидимым, чтобы все блоки успели принять размер, затем подгоняем высоту и ставим по центру.
    dialog.attributes("-alpha", 0.0)
    dialog.geometry(f"{width}x760+0+0")
    dialog.deiconify()
    for _ in range(3):
        dialog.update_idletasks()
    screen_w, screen_h = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    height = min(dialog.winfo_reqheight(), screen_h - 80)
    dialog.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{max(0, (screen_h - height) // 2 - 20)}")
    ui_style_window(dialog, pal, dark)
    dialog.attributes("-alpha", 1.0)
    dialog.lift()
    dialog.focus_force()
    entry.focus_set()

def parse_int_field(text):
    """Целое число из поля ввода; вместо сырого «invalid literal for int()» – понятное сообщение."""
    try:
        return int(str(text).strip())
    except ValueError:
        raise ValueError(t("err_not_a_number")) from None


def reset_settings_to_defaults():
    """Возвращает все настройки программы к значениям по умолчанию, сохраняет и применяет их."""
    global icon_color_enabled, notification_style, auto_switch_enabled, media_players_enabled
    global media_delay_seconds, custom_exclusions_enabled, halo_enabled, halo_verified_value, ui_theme
    global advanced_settings_enabled, debug_enabled, HOTKEY_MODIFIERS, HOTKEY_VK, monitor_device_path, monitor_manual
    global current_language, auto_update_check, last_update_check, update_info
    prev_auto_switch = auto_switch_enabled
    prev_manual = monitor_manual
    prev_hotkey = (HOTKEY_MODIFIERS, HOTKEY_VK)
    current_language = detect_system_language()
    modes[:] = get_default_modes()
    hdr_settings.clear()
    hdr_settings.update({"auto_set_preset": False, "preset_number": 5})
    icon_colors[:] = DEFAULT_ICON_COLORS
    icon_color_enabled = False
    notification_style = "win10"
    auto_switch_enabled = True
    media_players_enabled = True
    media_delay_seconds = 2
    custom_excluded_processes.clear()
    custom_exclusions_enabled = False
    halo_enabled = False
    halo_verified_value = None
    auto_update_check = False
    last_update_check = 0.0
    update_info = None
    ui_theme = "dark"
    advanced_settings_enabled = False
    debug_enabled = False
    HOTKEY_MODIFIERS, HOTKEY_VK = DEFAULT_HOTKEY_MOD, DEFAULT_HOTKEY_VK
    monitor_device_path = None
    monitor_manual = False
    window_positions.clear()
    try:
        set_autostart(False)
    except Exception as e:
        log(f"Сброс: не удалось отключить автозапуск: {e}")
    save_settings()
    if (HOTKEY_MODIFIERS, HOTKEY_VK) != prev_hotkey:
        request_hotkey_update(HOTKEY_MODIFIERS, HOTKEY_VK)
    update_tray_icon(current_mode_index)
    rebuild_tray_menu()
    if auto_switch_enabled != prev_auto_switch:
        threading.Thread(target=on_auto_switch_changed, args=(auto_switch_enabled,), daemon=True).start()

    def reapply_current_mode():
        if prev_manual:
            rebind_monitor_selection()   # ручной выбор сброшен: монитор определяется заново
        with game_state_lock:
            blocked, _ = is_hdr_blocked(force_refresh=True)
            if not blocked:
                apply_mode_settings(current_mode_index)
    threading.Thread(target=reapply_current_mode, daemon=True).start()
    show_notification(t("notif_settings_reset"))


def create_settings_window(start_page="general"):
    def create_window():
        # Окно настроек одно: повторный вызов (например, «О программе» из трея) показывает уже открытое.
        previous = _settings_ui.get("window")
        try:
            if previous is not None and previous.winfo_exists():
                previous.deiconify()
                previous.lift()
                previous.focus_force()
                _settings_ui["show_page"](start_page)
                return
        except tk.TclError:
            pass
        pal, dark = ui_palette()

        # ---------- действия ----------
        def save_all_settings():
            nonlocal new_hotkey_mod, new_hotkey_vk
            try:
                standard_brightness = int(standard_brightness_var.get())
                gaming_brightness = int(gaming_brightness_var.get())
                for value in (standard_brightness, gaming_brightness):
                    if not (0 <= value <= 100):
                        raise ValueError(t("err_brightness_range"))
                standard_dimming = standard_dimming_var.get()
                gaming_dimming = gaming_dimming_var.get()
                if standard_dimming == 0 or gaming_dimming == 0:
                    raise ValueError(t("err_select_dimming"))
                standard_halo = int(standard_halo_var.get())
                gaming_halo = int(gaming_halo_var.get())
                for value in (standard_halo, gaming_halo):
                    if not (0 <= value <= 100):
                        raise ValueError(t("err_halo_range"))
                auto_set_preset = auto_set_var.get()
                preset_number = parse_int_field(preset_entry.get())
                if not (0 <= preset_number <= 255):
                    raise ValueError(t("err_preset_range"))
                icon_color_on = icon_color_var.get()
                if icon_color_on:
                    # Скрытые поля не проверяем: ошибку в них пользователь не увидел бы.
                    standard_icon_color = normalize_icon_color(standard_icon_color_var.get())
                    gaming_icon_color = normalize_icon_color(gaming_icon_color_var.get())
                    if not standard_icon_color or not gaming_icon_color:
                        raise ValueError(t("err_icon_color"))
                try:
                    delay_val = parse_int_field(media_delay_var.get())
                    if delay_val < 1:
                        raise ValueError(t("err_delay_min"))
                    if delay_val > 60:
                        raise ValueError(t("err_delay_max"))
                except ValueError as e:
                    show_notification(t("notif_delay_field_error", error=e))
                    return

                global auto_switch_enabled, media_players_enabled, media_delay_seconds
                prev_auto_switch = auto_switch_enabled
                auto_switch_enabled = auto_switch_var.get()
                media_players_enabled = media_players_var.get()
                media_delay_seconds = delay_val
                if auto_switch_enabled != prev_auto_switch:
                    threading.Thread(target=on_auto_switch_changed, args=(auto_switch_enabled,), daemon=True).start()

                # Какие процессы добавлены в этом сохранении – считаем ДО перезаписи списка.
                # Пока «свои исключения» выключены, ни один из процессов не считается новым.
                global custom_exclusions_enabled
                was_enabled = custom_exclusions_enabled
                custom_exclusions_enabled = custom_excl_var.get()
                existing_exclusions = set(custom_excluded_processes) if was_enabled else set()
                newly_added_exclusions = ([p for p in custom_excluded_local if p not in existing_exclusions]
                                          if custom_exclusions_enabled else [])
                custom_excluded_processes[:] = custom_excluded_local

                global advanced_settings_enabled, debug_enabled
                advanced_settings_enabled = advanced_var.get()
                debug_enabled = debug_var.get()

                global monitor_manual, monitor_device_path
                previous_monitor = (monitor_manual, monitor_device_path)
                chosen_monitor = monitor_chosen["path"]
                if chosen_monitor:
                    monitor_manual, monitor_device_path = True, chosen_monitor
                elif monitor_manual:
                    monitor_manual, monitor_device_path = False, None   # вернулись к автоопределению: прежняя привязка не нужна
                monitor_changed = (monitor_manual, monitor_device_path) != previous_monitor

                modes[0]["brightness"] = standard_brightness
                modes[0]["local_dimming"] = standard_dimming
                modes[1]["brightness"] = gaming_brightness
                modes[1]["local_dimming"] = gaming_dimming
                # Halo Control: один общий переключатель для обоих режимов, значения хранятся в каждом режиме.
                global halo_enabled, halo_verified_value, ui_theme, auto_update_check
                halo_changed = ((halo_enabled, modes[0].get("halo"), modes[1].get("halo"))
                                != (halo_on_var.get(), standard_halo, gaming_halo))
                halo_enabled = halo_on_var.get()
                # Автопроверку только что включили (было выключено) – проверяем сразу, дальше по расписанию.
                update_check_now = auto_update_var.get() and not auto_update_check
                auto_update_check = auto_update_var.get()
                if halo_changed:
                    halo_verified_value = None   # Halo изменили в настройках – сверяем/записываем заново
                modes[0]["halo"] = standard_halo
                modes[1]["halo"] = gaming_halo
                hdr_settings["auto_set_preset"] = auto_set_preset
                hdr_settings["preset_number"] = preset_number
                global icon_color_enabled, notification_style
                icon_color_enabled = icon_color_on
                if icon_color_on:
                    icon_colors[0] = standard_icon_color
                    icon_colors[1] = gaming_icon_color
                update_tray_icon(current_mode_index)
                notification_style = notification_code_by_name.get(notification_var.get(), notification_style)
                ui_theme = theme_code_by_name.get(theme_var.get(), ui_theme)

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

                # Ярлык автозапуска трогаем, только если состояние переключателя изменилось: при уже включённом
                # автозапуске его не пересоздаём.
                desired_autostart = autostart_var.get()
                if desired_autostart == is_autostart_enabled():
                    autostart_ok, autostart_error = True, ""
                else:
                    autostart_ok, autostart_error = set_autostart(desired_autostart)

                if save_settings():
                    if autostart_ok:
                        show_notification(t("notif_settings_saved"))
                    else:
                        show_notification(t("notif_autostart_error", error=autostart_error), error=True)
                else:
                    # Значения в памяти уже новые и действуют до перезапуска – молча терять их при
                    # следующем запуске нельзя, поэтому сообщаем причину.
                    show_notification(t("notif_save_failed", error=last_save_error), error=True)
                # Переприменение настроек к текущему режиму – в отдельном потоке под game_state_lock.
                # Так не блокируем UI на время DDC-операций и не гоняем с monitor_loop, который мог бы
                # сменить current_mode_index прямо во время записи. Применяем и при ошибке записи файла:
                # значения в памяти от неё не зависят.
                def reapply_current_mode():
                    if monitor_changed:
                        rebind_monitor_selection()
                    with game_state_lock:
                        blocked, _ = is_hdr_blocked(force_refresh=True)
                        if not blocked:
                            apply_mode_settings(current_mode_index)
                threading.Thread(target=reapply_current_mode, daemon=True).start()

                if update_check_now:
                    threading.Thread(target=check_update_and_notify, daemon=True).start()

                if language_changed:
                    rebuild_tray_menu()
                    show_notification(t("notif_restart_required"))

                # Если в исключения добавили процесс, который прямо сейчас автоматически держит
                # игровой режим – вернуть стандартный.
                if newly_added_exclusions:
                    check_active_game_exclusion(newly_added_exclusions)

                if auto_switch_enabled:
                    def check_now():
                        hwnd = user32.GetForegroundWindow()
                        if not hwnd:
                            return
                        # is_game_window модифицирует глобальные last_excluded_process_logged /
                        # last_media_player_logged – держим game_state_lock, чтобы не гонять с monitor_loop.
                        with game_state_lock:
                            if is_game_window(hwnd):
                                log("Авто-переключение включено – игра/медиаплеер активна, переключаем")
                                apply_mode_by_index(1, force_hdr_check=True, hwnd=hwnd)
                    threading.Thread(target=check_now, daemon=True).start()

                remember_window_position("settings", window)
                window.destroy()
            except ValueError as e:
                show_notification(t("notif_error", error=str(e)))
            except Exception as e:
                show_notification(t("notif_save_error", error=e))

        def on_cancel():
            remember_window_position("settings", window)
            window.destroy()

        # ---------- окно ----------
        window = tk.Toplevel()
        window.withdraw()   # показываем окно, только когда оно собрано и стоит на своём месте (без «прыжка» из угла)
        apply_window_icon(window)
        window.title(t("settings_title"))
        window.resizable(False, False)
        ui_style_window(window, pal, dark)
        ui_setup_ttk(window, pal)
        win_width = 920
        win_height = min(720, window.winfo_screenheight() - 100)
        start_pos = get_window_start_position("settings", win_width, win_height)
        if start_pos is None:
            start_pos = ((window.winfo_screenwidth() - win_width) // 2,
                         (window.winfo_screenheight() - win_height) // 2)
        window.geometry(f"{win_width}x{win_height}+{start_pos[0]}+{start_pos[1]}")

        # Нижняя панель с кнопками создаётся первой, чтобы всегда оставаться на виду.
        footer = tk.Frame(window, bg=pal["bg"])
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, height=1, bg=pal["divider"]).pack(fill="x")
        buttons = tk.Frame(footer, bg=pal["bg"])
        buttons.pack(fill="x", padx=24, pady=12)
        W11Button(buttons, pal, t("btn_cancel"), on_cancel, bg=pal["bg"], min_width=110).pack(side="right")
        W11Button(buttons, pal, t("btn_save"), save_all_settings, kind="accent", bg=pal["bg"],
                  min_width=110).pack(side="right", padx=(0, 8))

        # Слева внизу: версия программы, значок проверки обновлений и результат проверки.
        version_box = tk.Frame(buttons, bg=pal["bg"])
        version_box.pack(side="left")
        tk.Label(version_box, text=t("settings_version", version=APP_VERSION), bg=pal["bg"], fg=pal["muted"],
                 font=(UI_FONT, 10)).pack(side="left")
        update_icon = W11Icon(version_box, pal, "refresh", command=lambda: start_update_check())
        update_icon.pack(side="left", padx=(8, 0))
        update_status = tk.Frame(version_box, bg=pal["bg"])
        update_status.pack(side="left", padx=(6, 0))

        def open_update_page(url):
            ok_url = isinstance(url, str) and url.startswith("https://github.com/")
            webbrowser.open(url if ok_url else f"https://github.com/{GITHUB_REPO}/releases")

        def render_update_status(state, url=None):
            for child in update_status.winfo_children():
                child.destroy()
            if state == "available":
                W11Icon(update_status, pal, "warn").pack(side="left")
                link = tk.Label(update_status, text=t("update_available"), bg=pal["bg"], fg=pal["warn"],
                                cursor="hand2", font=(UI_FONT, 10, "underline"))
                link.pack(side="left", padx=(4, 0))
                link.bind("<Button-1>", lambda e: open_update_page(url))
            elif state:
                text = {"checking": t("update_checking"), "latest": t("update_latest"),
                        "error": t("update_error")}[state]
                tk.Label(update_status, text=text, bg=pal["bg"], fg=pal["muted"],
                         font=(UI_FONT, 10)).pack(side="left")

        def finish_update_check(result):
            try:
                if not window.winfo_exists():
                    return
                update_icon.set_busy(False)
                if result[0] == "available":
                    render_update_status("available", result[2])
                else:
                    render_update_status("latest" if result[0] == "latest" else "error")
            except tk.TclError:
                pass

        def start_update_check():
            update_icon.set_busy(True)
            render_update_status("checking")

            def worker():
                result = check_for_update()
                tk_queue.put(("window", lambda: finish_update_check(result)))
            threading.Thread(target=worker, daemon=True).start()

        if update_info:   # новая версия уже найдена раньше (в том числе автоматической проверкой)
            render_update_status("available", update_info.get("url"))

        # Слева – меню категорий, справа – страница выбранной категории (каждая помещается без прокрутки).
        shell = tk.Frame(window, bg=pal["bg"])
        shell.pack(fill="both", expand=True)
        nav = tk.Frame(shell, bg=pal["bg"], width=230)
        nav.pack(side="left", fill="y", padx=(10, 0))
        nav.pack_propagate(False)
        tk.Label(nav, text=t("settings_title"), bg=pal["bg"], fg=pal["text"], font=(UI_FONT_SEMIBOLD, 15),
                 anchor="w").pack(fill="x", padx=14, pady=(20, 14))
        content = tk.Frame(shell, bg=pal["bg"])
        content.pack(side="left", fill="both", expand=True)

        pages, holders, nav_items, scrollers = {}, {}, {}, []

        def make_page(key, nav_text):
            page_, canvas_, update_, holder_ = ui_scrolled_page(content, pal, lambda parent: W11Page(parent, pal))
            holder_.pack_forget()
            page_.title(nav_text)
            pages[key], holders[key] = page_, holder_
            scrollers.append(update_)
            item = W11NavItem(nav, pal, nav_text, lambda k=key: show_page(k))
            item.pack(fill="x", padx=6, pady=1)
            nav_items[key] = item
            return page_, canvas_

        def update_scroll():
            for fn in scrollers:
                fn()

        def show_page(key):
            for k, holder in holders.items():
                holder.pack_forget()
                nav_items[k].set_selected(k == key)
            holders[key].pack(fill="both", expand=True)
            window.update_idletasks()
            update_scroll()

        page, _canvas1 = make_page("general", t("settings_nav_general"))
        pages_canvases = [_canvas1]
        for key, caption in (("auto", t("settings_nav_auto")), ("modes", t("settings_nav_modes")),
                             ("advanced", t("settings_nav_advanced")), ("about", t("settings_nav_about"))):
            pages_canvases.append(make_page(key, caption)[1])

        # Внизу бокового меню: значок и подпись, открывают окно отчёта о проблеме.
        report_box = tk.Frame(nav, bg=pal["bg"])
        report_box.pack(side="bottom", fill="x", padx=14, pady=(0, 16))
        report_icon = W11Icon(report_box, pal, "report", command=show_issue_report_dialog, size=24)
        report_icon.pack(side="left")
        report_label = tk.Label(report_box, text=t("settings_report_title"), bg=pal["bg"], fg=pal["muted"],
                                font=(UI_FONT, 9), cursor="hand2")
        report_label.pack(side="left", padx=(6, 0))

        def report_hover(value):
            report_label.configure(fg=pal["text"] if value else pal["muted"])
            report_icon._set_hover(value)
        report_label.bind("<Enter>", lambda e: report_hover(True))
        report_label.bind("<Leave>", lambda e: report_hover(False))
        report_label.bind("<Button-1>", lambda e: show_issue_report_dialog())
        report_icon.bind("<Enter>", lambda e: report_label.configure(fg=pal["text"]), add="+")
        report_icon.bind("<Leave>", lambda e: report_label.configure(fg=pal["muted"]), add="+")

        # ---------- Общие ----------
        page = pages["general"]
        card = page.card()

        row = card.add_row(t("settings_autostart"))
        autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        ui_toggle(row.right, pal, autostart_var).pack()

        row = card.add_row(t("settings_language_group"))
        language_names = [TRANSLATIONS[code]["lang_name"] for code in SUPPORTED_LANGUAGES]
        language_code_by_name = {TRANSLATIONS[code]["lang_name"]: code for code in SUPPORTED_LANGUAGES}
        language_var = tk.StringVar(value=TRANSLATIONS[current_language]["lang_name"])
        ui_combo(row.right, language_names, language_var, width=20).pack()

        row = card.add_row(t("settings_theme_title"), desc=t("settings_theme_desc"))
        theme_names = {"dark": t("theme_dark"), "light": t("theme_light"), "system": t("theme_system")}
        theme_code_by_name = {name: code for code, name in theme_names.items()}
        theme_var = tk.StringVar(value=theme_names.get(ui_theme, theme_names["dark"]))
        ui_combo(row.right, list(theme_names.values()), theme_var, width=20).pack()

        row = card.add_row(t("settings_notification_group"))
        notification_names = {
            "win10": t("settings_notification_win10"),
            "win11": t("settings_notification_win11"),
            "off": t("settings_notification_off"),
        }
        notification_code_by_name = {name: code for code, name in notification_names.items()}
        notification_var = tk.StringVar(value=notification_names.get(notification_style, notification_names["win10"]))
        ui_combo(row.right, list(notification_names.values()), notification_var, width=20).pack()

        # Горячая клавиша: подсказка под заголовком заменяется сообщениями во время записи комбинации.
        row = card.add_row(t("settings_hotkey_group"), desc=t("settings_hotkey_hint"))
        hotkey_hint_var = tk.StringVar(value=t("settings_hotkey_hint"))
        row.desc_label.configure(textvariable=hotkey_hint_var)
        hotkey_frame = tk.Frame(row.right, bg=pal["card"], takefocus=1)
        hotkey_frame.pack()
        hotkey_display_var = tk.StringVar(value=hotkey_to_string(new_hotkey_mod, new_hotkey_vk))
        tk.Label(hotkey_frame, textvariable=hotkey_display_var, bg=pal["field"], fg=pal["text"],
                 font=(UI_FONT_SEMIBOLD, 10), padx=12, pady=5, highlightthickness=1,
                 highlightbackground=pal["field_border"]).pack(side="left", padx=(0, 8))

        def finish_recording():
            hotkey_frame.unbind("<KeyPress>")
            hotkey_frame.unbind("<FocusOut>")
            record_button.set_text(t("settings_hotkey_record"))
            hotkey_hint_var.set(t("settings_hotkey_hint"))

        def on_hotkey_key_press(event):
            nonlocal new_hotkey_mod, new_hotkey_vk
            keysym = event.keysym

            if keysym in ("Super_L", "Super_R", "Win_L", "Win_R") or "Win" in keysym:
                hotkey_hint_var.set(t("settings_hotkey_win_forbidden"))
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
                    hotkey_hint_var.set(t("settings_hotkey_need_modifier"))
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
            hotkey_hint_var.set(t("settings_hotkey_press_combo"))
            record_button.set_text(t("settings_hotkey_cancel_record"))
            hotkey_frame.focus_set()
            hotkey_frame.bind("<KeyPress>", on_hotkey_key_press)
            hotkey_frame.bind("<FocusOut>", lambda e: (finish_recording(),
                              hotkey_display_var.set(hotkey_to_string(new_hotkey_mod, new_hotkey_vk))))

        def on_record_button():
            if record_button._text == t("settings_hotkey_cancel_record"):
                finish_recording()
                hotkey_display_var.set(hotkey_to_string(new_hotkey_mod, new_hotkey_vk))
            else:
                start_recording()

        record_button = W11Button(hotkey_frame, pal, t("settings_hotkey_record"), on_record_button)
        record_button.pack(side="left")

        # Цвет значка в трее: переключатель и по строке на каждый режим (строки видны, только когда включено).
        row = card.add_row(t("settings_icon_color_enabled"))
        icon_color_var = tk.BooleanVar(value=icon_color_enabled)
        ui_toggle(row.right, pal, icon_color_var).pack()
        icon_color_rows = []

        def toggle_icon_color_fields():
            for r in icon_color_rows:
                r.set_visible(icon_color_var.get())
            update_scroll()

        def build_icon_color_row(card, initial, default, title):
            """Цвет иконки трея: образец (клик открывает палитру), поле #RRGGBB, «Сбросить»."""
            var = tk.StringVar(value=initial)
            icon_row = card.add_row(title)
            swatch = tk.Label(icon_row.right, width=4, bg=initial, cursor="hand2", highlightthickness=1,
                              highlightbackground=pal["field_border"])
            swatch.pack(side="left", padx=(0, 8), ipady=3)
            entry = ui_entry(icon_row.right, pal, textvariable=var, width=9, justify="center")
            entry.pack(side="left", ipady=4, padx=(0, 8))
            W11Button(icon_row.right, pal, t("settings_icon_color_reset"), lambda: var.set(default)).pack(side="left")

            def refresh_swatch(*_):
                color = normalize_icon_color(var.get())
                if color:
                    swatch.config(bg=color, text="")
                else:
                    swatch.config(bg=pal["card"], text="?", fg=pal["muted"])

            def pick_color(event=None):
                current = normalize_icon_color(var.get()) or default
                chosen = colorchooser.askcolor(color=current, parent=window,
                                               title=t("settings_icon_color_dialog"))[1]
                if chosen:
                    var.set(normalize_icon_color(chosen) or current)

            def paste_color(event=None):
                """Ctrl+V: если в буфере цвет #RRGGBB – он заменяет содержимое поля целиком; иначе обычная вставка."""
                try:
                    clip = normalize_icon_color(entry.clipboard_get())
                except tk.TclError:
                    return None
                if not clip:
                    return None
                var.set(clip)
                entry.icursor(tk.END)
                return "break"

            def paste_any_layout(event):
                # В нелатинской раскладке Ctrl+V приходит с другим keysym, и <<Paste>> не срабатывает;
                # keycode 86 – физическая клавиша V.
                if event.keycode == 86 and event.keysym.lower() != "v":
                    entry.event_generate("<<Paste>>")
                    return "break"

            swatch.bind("<Button-1>", pick_color)
            entry.bind("<<Paste>>", paste_color)
            entry.bind("<Control-KeyPress>", paste_any_layout)
            var.trace_add("write", refresh_swatch)
            refresh_swatch()
            icon_color_rows.append(icon_row)
            return var

        icon_caption = t("settings_icon_color_label").rstrip(": ")
        standard_icon_color_var = build_icon_color_row(card, icon_colors[0], DEFAULT_ICON_COLORS[0],
                                                       f"{icon_caption}: {t('settings_standard_mode')}")
        gaming_icon_color_var = build_icon_color_row(card, icon_colors[1], DEFAULT_ICON_COLORS[1],
                                                     f"{icon_caption}: {t('settings_gaming_mode')}")
        toggle_icon_color_fields()
        icon_color_var.trace_add("write", lambda *a: toggle_icon_color_fields())

        # ---------- Автоматическое переключение ----------
        page = pages["auto"]
        card = page.card()

        row = card.add_row(t("settings_auto_switch"))
        auto_switch_var = tk.BooleanVar(value=auto_switch_enabled)
        ui_toggle(row.right, pal, auto_switch_var).pack()

        row_media = card.add_row(t("settings_media_players"))
        media_players_var = tk.BooleanVar(value=media_players_enabled)
        media_toggle = ui_toggle(row_media.right, pal, media_players_var)
        media_toggle.pack()

        row_delay = card.add_row(t("settings_media_delay_label").rstrip(": "))
        media_delay_var = tk.StringVar(value=str(media_delay_seconds))
        media_delay_entry = ui_entry(row_delay.right, pal, textvariable=media_delay_var, width=6, justify="center")
        media_delay_entry.pack(side="left", ipady=4)
        ui_label(row_delay.right, pal, t("settings_range_1_60"), muted=True, size=9).pack(side="left", padx=(8, 0))

        def refresh_auto_state(*_):
            auto = auto_switch_var.get()
            delay_on = auto and media_players_var.get()
            media_toggle.toggle.set_enabled(auto)
            row_media.set_dim(not auto, pal)
            media_delay_entry.config(state="normal" if delay_on else "disabled")
            row_delay.set_dim(not delay_on, pal)

        auto_switch_var.trace_add("write", refresh_auto_state)
        media_players_var.trace_add("write", refresh_auto_state)
        refresh_auto_state()

        # Свои исключения: по умолчанию выключены, пока выключены – блок настроек скрыт и список не применяется.
        page.gap(16)
        card = page.card()
        row = card.add_row(t("settings_exclusions_group"), desc=t("settings_exclusions_toggle_desc"))
        custom_excl_var = tk.BooleanVar(value=custom_exclusions_enabled)
        ui_toggle(row.right, pal, custom_excl_var).pack()

        custom_excluded_local = list(custom_excluded_processes)
        exclusion_entry_var = tk.StringVar()

        row_hint = card.add_row(None, desc=t("settings_exclusions_hint"))

        row_list = card.add_row()
        list_box = tk.Frame(row_list.left, bg=pal["field"], highlightthickness=1,
                            highlightbackground=pal["field_border"])
        list_box.pack(fill="x")
        exclusions_listbox = tk.Listbox(list_box, height=4, exportselection=False, bg=pal["field"],
                                        fg=pal["text"], selectbackground=pal["accent"],
                                        selectforeground=pal["on_accent"], relief="flat", bd=0,
                                        highlightthickness=0, activestyle="none", font=(UI_FONT, 10))
        exclusions_scroll = ttk.Scrollbar(list_box, orient="vertical", style="W11.Vertical.TScrollbar",
                                          command=exclusions_listbox.yview)
        exclusions_listbox.config(yscrollcommand=exclusions_scroll.set)
        exclusions_listbox.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=4)
        for excluded_name in custom_excluded_local:
            exclusions_listbox.insert(tk.END, excluded_name)

        def refresh_exclusions_scroll():
            # Полоса прокрутки нужна, только когда записи не помещаются.
            if exclusions_listbox.size() > 4:
                exclusions_scroll.pack(side="right", fill="y")
            else:
                exclusions_scroll.pack_forget()
        refresh_exclusions_scroll()

        def add_exclusion(name=None):
            normalized = normalize_process_name(exclusion_entry_var.get() if name is None else name)
            if not normalized:
                show_notification(t("err_exclusion_invalid"))
                return
            if normalized in custom_excluded_local or normalized in [p.lower() for p in EXCLUDED_PROCESSES]:
                show_notification(t("err_exclusion_duplicate", name=normalized))
                return
            custom_excluded_local.append(normalized)
            exclusions_listbox.insert(tk.END, normalized)
            exclusion_entry_var.set("")
            refresh_exclusions_scroll()

        def remove_exclusion():
            for index in reversed(exclusions_listbox.curselection()):
                del custom_excluded_local[index]
                exclusions_listbox.delete(index)
            refresh_exclusions_scroll()

        def pick_running_process():
            dialog = tk.Toplevel(window)
            dialog.withdraw()
            apply_window_icon(dialog)
            dialog.title(t("settings_exclusions_running_title"))
            dialog.transient(window)
            dialog.resizable(False, False)
            ui_style_window(dialog, pal, dark)
            wx, wy = get_window_origin(window)
            dialog.geometry(f"+{wx + 40}+{wy + 40}")
            body = tk.Frame(dialog, bg=pal["bg"])
            body.pack(fill="both", expand=True, padx=20, pady=16)
            ui_label(body, pal, t("settings_exclusions_running_hint"), muted=True, size=9, bg=pal["bg"],
                     wraplength=480, justify="left").pack(anchor="w", pady=(0, 8))
            list_frame = tk.Frame(body, bg=pal["field"], highlightthickness=1,
                                  highlightbackground=pal["field_border"])
            list_frame.pack(fill="both", expand=True)
            running_listbox = tk.Listbox(list_frame, width=70, height=14, exportselection=False,
                                         bg=pal["field"], fg=pal["text"], selectbackground=pal["accent"],
                                         selectforeground=pal["on_accent"], relief="flat", bd=0,
                                         highlightthickness=0, activestyle="none", font=(UI_FONT, 10))
            running_scroll = ttk.Scrollbar(list_frame, orient="vertical", style="W11.Vertical.TScrollbar",
                                           command=running_listbox.yview)
            running_listbox.config(yscrollcommand=running_scroll.set)
            running_listbox.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
            running_names = []

            def refresh_running():
                running_names.clear()
                running_listbox.delete(0, tk.END)
                already = {p.lower() for p in EXCLUDED_PROCESSES} | set(custom_excluded_local)
                for proc_name, title in list_windowed_processes():
                    if proc_name in already:
                        continue
                    running_names.append(proc_name)
                    running_listbox.insert(tk.END, f"{proc_name}  \u2014  {title[:50]}")
                if running_listbox.size() > 14:
                    running_scroll.pack(side="right", fill="y")
                else:
                    running_scroll.pack_forget()

            def choose_running(event=None):
                selection = running_listbox.curselection()
                if selection:
                    add_exclusion(running_names[selection[0]])
                    dialog.destroy()

            running_listbox.bind("<Double-Button-1>", choose_running)
            dialog_buttons = tk.Frame(body, bg=pal["bg"])
            dialog_buttons.pack(anchor="e", pady=(12, 0))
            W11Button(dialog_buttons, pal, t("settings_exclusions_add"), choose_running, kind="accent",
                      bg=pal["bg"]).pack(side="left", padx=(0, 8))
            W11Button(dialog_buttons, pal, t("settings_exclusions_refresh"), refresh_running,
                      bg=pal["bg"]).pack(side="left", padx=(0, 8))
            W11Button(dialog_buttons, pal, t("btn_cancel"), dialog.destroy, bg=pal["bg"]).pack(side="left")
            refresh_running()
            dialog.update_idletasks()
            dialog.deiconify()
            ui_style_window(dialog, pal, dark)
            dialog.focus_force()

        row_add = card.add_row()
        exclusion_entry = ui_entry(row_add.left, pal, textvariable=exclusion_entry_var, width=30)
        exclusion_entry.pack(side="left", ipady=5, padx=(0, 8))
        exclusion_entry.bind("<Return>", lambda e: add_exclusion())
        W11Button(row_add.left, pal, t("settings_exclusions_add"), add_exclusion).pack(side="left")
        ui_label(row_add.right, pal, "").pack()

        row_buttons = card.add_row()
        W11Button(row_buttons.left, pal, t("settings_exclusions_running"), pick_running_process).pack(
            side="left", padx=(0, 8))
        W11Button(row_buttons.left, pal, t("settings_exclusions_remove"), remove_exclusion).pack(side="left")

        exclusion_rows = (row_hint, row_list, row_add, row_buttons)

        def toggle_exclusions_block():
            for r in exclusion_rows:
                r.set_visible(custom_excl_var.get())
            update_scroll()

        toggle_exclusions_block()
        custom_excl_var.trace_add("write", lambda *a: toggle_exclusions_block())

        # ---------- Режимы монитора ----------
        page = pages["modes"]
        def build_mode_card(title, mode):
            page.section(title)
            mode_card = page.card()

            row = mode_card.add_row(t("settings_brightness_title"))
            brightness_var = tk.IntVar(value=int(mode["brightness"]))
            ui_label(row.right, pal, "", width=4, anchor="e", textvariable=brightness_var).pack(side="right")
            W11Slider(row.right, pal, brightness_var, 0, 100, width=210).pack(side="right")

            options = get_local_dimming_options()
            dimming_var = tk.IntVar(value=mode["local_dimming"])
            display_by_value = {o["value"]: o["name"] for o in options}
            value_by_display = {v: k for k, v in display_by_value.items()}
            dimming_row = mode_card.add_row(t("settings_dimming_title"), desc=" ")
            dimming_text_var = tk.StringVar(value=display_by_value.get(mode["local_dimming"], str(mode["local_dimming"])))

            def on_dimming_select(*_):
                value = value_by_display.get(dimming_text_var.get())
                if value is not None:
                    dimming_var.set(value)
                for o in options:
                    if o["value"] == dimming_var.get():
                        dimming_row.desc_label.config(text=o["description"])
                        break
            combo = ui_combo(dimming_row.right, list(display_by_value.values()), dimming_text_var, width=22)
            combo.pack()
            combo.bind("<<ComboboxSelected>>", on_dimming_select, add="+")
            on_dimming_select()

            # Уровень Halo этого режима; строка видна, только когда Halo Control включён (переключатель сверху страницы).
            level = mode.get("halo")
            halo_var = tk.IntVar(value=level if isinstance(level, int) else 50)
            halo_row = mode_card.add_row(t("settings_halo_title"))
            ui_label(halo_row.right, pal, "", width=4, anchor="e", textvariable=halo_var).pack(side="right")
            W11Slider(halo_row.right, pal, halo_var, 0, 100, width=210).pack(side="right")
            halo_rows.append(halo_row)
            halo_row.set_visible(halo_on_var.get())
            return brightness_var, dimming_var, halo_var

        # Выбор монитора: список собирается в фоне (опрос по DDC/CI занимает время). Ручной выбор запоминается
        # жёстко: если выбранный монитор не подключён, программа не подставляет другой.
        monitor_card = page.card()
        monitor_row = monitor_card.add_row(t("settings_monitor_title"), desc=t("settings_monitor_desc"))
        auto_label = t("monitor_auto")
        monitor_chosen = {"path": monitor_device_path if monitor_manual else None}
        monitor_labels = {auto_label: None}
        monitor_compat = {}
        monitor_current = {"name": None}   # имя монитора, которым программа управляет сейчас
        monitor_var = tk.StringVar(value=t("monitor_loading") if monitor_chosen["path"] else auto_label)
        monitor_combo = ui_combo(monitor_row.right, [auto_label], monitor_var, width=30)
        monitor_combo.pack(side="left")

        def show_monitor_note():
            if monitor_chosen["path"] and monitor_compat.get(monitor_chosen["path"]) is False:
                monitor_row.desc_label.configure(text=t("monitor_incompatible_warning"), fg=pal["warn"])
            elif monitor_current["name"]:
                monitor_row.desc_label.configure(text=t("monitor_current", name=monitor_current["name"]), fg=pal["muted"])
            else:
                monitor_row.desc_label.configure(text=t("settings_monitor_desc"), fg=pal["muted"])

        def on_monitor_select(*_):
            path = monitor_labels.get(monitor_var.get(), monitor_chosen["path"])
            monitor_chosen["path"] = path
            show_monitor_note()
            if path and monitor_compat.get(path) is None:
                # Признак Titan Army у этого монитора ещё не проверяли: проверяем один раз, только по выбору вручную.
                def worker():
                    result = probe_monitor_marker(path)

                    def apply():
                        try:
                            if window.winfo_exists():
                                monitor_compat[path] = result
                                show_monitor_note()
                        except tk.TclError:
                            pass
                    tk_queue.put(("window", apply))
                threading.Thread(target=worker, daemon=True).start()
        monitor_combo.bind("<<ComboboxSelected>>", on_monitor_select, add="+")

        def fill_monitor_choices(choices):
            try:
                if not window.winfo_exists():
                    return
                labels, compat = {auto_label: None}, {}
                for choice in choices:
                    label, n = choice["label"], 2
                    while label in labels:
                        label, n = f"{choice['label']} #{n}", n + 1
                    labels[label] = choice["path"]
                    compat[choice["path"]] = choice["compatible"]
                chosen = monitor_chosen["path"]
                if chosen and chosen not in labels.values():
                    labels[t("monitor_missing")] = chosen   # выбранный монитор сейчас не подключён: выбор не теряем
                monitor_labels.clear()
                monitor_labels.update(labels)
                monitor_compat.clear()
                monitor_compat.update(compat)
                monitor_current["name"] = next((c["name"] for c in choices if c["in_use"]), None)
                monitor_combo.configure(values=list(labels))
                monitor_var.set(next((l for l, p in labels.items() if p == chosen), auto_label))
                monitor_refresh.set_busy(False)
                show_monitor_note()
            except tk.TclError:
                pass

        def load_monitor_choices(probe=False):
            monitor_refresh.set_busy(True)

            def worker():
                choices = list_monitor_choices(probe)
                tk_queue.put(("window", lambda: fill_monitor_choices(choices)))
            threading.Thread(target=worker, daemon=True).start()

        monitor_refresh = W11Icon(monitor_row.right, pal, "refresh", command=lambda: load_monitor_choices(True))
        monitor_refresh.pack(side="left", padx=(8, 0))
        load_monitor_choices()
        page.gap(14)

        # Halo Control: один переключатель сразу для обоих режимов, у каждого режима свой уровень 0-100.
        # Одинаковые уровни сверяются с монитором один раз и дальше не переписываются, разные – пишутся при смене режима.
        halo_card = page.card()
        row = halo_card.add_row(t("settings_halo_title"), desc=t("settings_halo_desc"))
        halo_on_var = tk.BooleanVar(value=halo_enabled)
        ui_toggle(row.right, pal, halo_on_var).pack()
        halo_rows = []

        def refresh_halo(*_):
            for r in halo_rows:
                r.set_visible(halo_on_var.get())
            update_scroll()

        standard_brightness_var, standard_dimming_var, standard_halo_var = build_mode_card(
            t("settings_standard_mode"), modes[0])
        gaming_brightness_var, gaming_dimming_var, gaming_halo_var = build_mode_card(
            t("settings_gaming_mode"), modes[1])
        halo_on_var.trace_add("write", refresh_halo)

        # ---------- Дополнительно ----------
        page = pages["advanced"]
        card = page.card()
        row = card.add_row(t("settings_advanced_settings"))
        advanced_var = tk.BooleanVar(value=advanced_settings_enabled)
        ui_toggle(row.right, pal, advanced_var).pack()

        row_auto_set = card.add_row(t("settings_hdr_autoset"), desc=t("settings_hdr_autoset_warning"),
                                    desc_color=pal["warn"])
        auto_set_var = tk.BooleanVar(value=hdr_settings["auto_set_preset"])
        ui_toggle(row_auto_set.right, pal, auto_set_var).pack()

        row_preset = card.add_row(t("settings_hdr_preset_label").rstrip(": "))
        preset_entry = ui_entry(row_preset.right, pal, width=6, justify="center")
        preset_entry.insert(0, str(hdr_settings["preset_number"]))
        preset_entry.pack(ipady=4)

        row_debug = card.add_row(t("settings_debug_enable"), desc=t("settings_debug_file_label", file=DEBUG_LOG_FILE))
        debug_var = tk.BooleanVar(value=debug_enabled)
        def open_log_folder():
            # Файл лога есть – открываем папку с уже выделенным файлом, иначе просто папку.
            try:
                if os.path.exists(DEBUG_LOG_FILE):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(DEBUG_LOG_FILE)])
                else:
                    os.startfile(os.path.dirname(DEBUG_LOG_FILE))
            except Exception as e:
                log(f"Не удалось открыть папку с логом: {e}")

        W11Button(row_debug.right, pal, t("settings_open_folder"), open_log_folder).pack(side="left", padx=(0, 12))
        ui_toggle(row_debug.right, pal, debug_var).pack(side="left")

        advanced_rows = (row_auto_set, row_preset, row_debug)

        def toggle_advanced_container():
            for r in advanced_rows:
                r.set_visible(advanced_var.get())
            update_scroll()

        toggle_advanced_container()
        advanced_var.trace_add("write", lambda *a: toggle_advanced_container())

        # Сброс всех настроек: подтверждение в окне в стиле программы, затем сброс и закрытие настроек.
        def do_reset(dialog):
            dialog.destroy()
            remember_window_position("settings", window)
            window.destroy()
            reset_settings_to_defaults()

        def confirm_reset():
            dialog = tk.Toplevel(window)
            dialog.withdraw()
            apply_window_icon(dialog)
            dialog.title(t("settings_reset_title"))
            dialog.transient(window)
            dialog.resizable(False, False)
            ui_style_window(dialog, pal, dark)
            wx, wy = get_window_origin(window)
            dialog.geometry(f"+{wx + 220}+{wy + 220}")
            body = tk.Frame(dialog, bg=pal["bg"])
            body.pack(fill="both", expand=True, padx=24, pady=20)
            tk.Label(body, text=t("settings_reset_title"), bg=pal["bg"], fg=pal["text"],
                     font=(UI_FONT_SEMIBOLD, 14), anchor="w").pack(fill="x")
            tk.Label(body, text=t("settings_reset_confirm"), bg=pal["bg"], fg=pal["muted"], font=(UI_FONT, 10),
                     wraplength=400, justify="left", anchor="w").pack(fill="x", pady=(8, 18))
            dialog_buttons = tk.Frame(body, bg=pal["bg"])
            dialog_buttons.pack(anchor="e")
            W11Button(dialog_buttons, pal, t("settings_reset_button"), lambda: do_reset(dialog), kind="accent",
                      bg=pal["bg"], min_width=110).pack(side="left", padx=(0, 8))
            W11Button(dialog_buttons, pal, t("btn_cancel"), dialog.destroy, bg=pal["bg"],
                      min_width=110).pack(side="left")
            dialog.update_idletasks()
            dialog.deiconify()
            ui_style_window(dialog, pal, dark)
            try:
                dialog.grab_set()
            except tk.TclError:
                pass
            dialog.focus_force()

        page.gap(18)
        card = page.card()
        # «Журнал работы» не зависит от дополнительных настроек: он стоит перед сбросом, в той же карточке.
        row_journal = card.add_row(t("settings_journal_title"), desc=t("settings_journal_desc"))
        W11Button(row_journal.right, pal, t("settings_journal_open"),
                  lambda: show_log_preview(window, pal, dark, collect_recent_log()[0])).pack()
        row = card.add_row(t("settings_reset_title"), desc=t("settings_reset_desc"))
        W11Button(row.right, pal, t("settings_reset_button"), confirm_reset).pack()

        # ---------- О программе ----------
        page = pages["about"]
        head = tk.Frame(page, bg=pal["bg"])
        page._place(head, (0, 6))
        logo = tk.Canvas(head, width=56, height=56, bg=pal["bg"], highlightthickness=0, bd=0)
        logo.pack(side="left", padx=(0, 14))
        try:
            buf = io.BytesIO()
            _render_icon(DEFAULT_ICON_COLORS[0], 56).save(buf, format="PNG")
            window._logo = tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii"))
            logo.create_image(28, 28, image=window._logo)
        except Exception as e:
            log(f"Ошибка значка в разделе «О программе»: {e}")
        titles = tk.Frame(head, bg=pal["bg"])
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text=t("about_app_title"), bg=pal["bg"], fg=pal["text"], font=(UI_FONT_SEMIBOLD, 15),
                 anchor="w", justify="left").pack(anchor="w")
        version_line = tk.Frame(titles, bg=pal["bg"])
        version_line.pack(anchor="w", pady=(2, 0))
        tk.Label(version_line, text=t("about_version", version=APP_VERSION), bg=pal["bg"], fg=pal["muted"],
                 font=(UI_FONT, 10), anchor="w").pack(side="left")
        tk.Label(version_line, text="\u00b7", bg=pal["bg"], fg=pal["muted"], font=(UI_FONT, 10)).pack(
            side="left", padx=8)
        link = tk.Label(version_line, text="github.com/tawiss-cloud/TA-toggle", bg=pal["bg"], fg=pal["accent"],
                        cursor="hand2", font=(UI_FONT, 10, "underline"))
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(f"https://github.com/{GITHUB_REPO}"))

        page.section(t("about_current_settings").rstrip(":"))
        card = page.card()
        for mode, name_key in ((modes[0], "settings_standard_mode"), (modes[1], "settings_gaming_mode")):
            parts = [t("about_brightness_part", brightness=mode["brightness"]),
                     t("about_dimming_part", dimming=get_local_dimming_name(mode["local_dimming"]))]
            if halo_enabled and mode.get("halo") is not None:
                parts.append(t("about_halo_part", halo=mode["halo"]))
            card.add_row(t(name_key), desc=" \u00b7 ".join(parts))

        page.section(t("about_excluded_title").rstrip(":"))
        card = page.card()
        excluded_text = t("about_excluded_list")
        if custom_exclusions_enabled and custom_excluded_processes:
            excluded_text += " " + t("about_excluded_custom", count=len(custom_excluded_processes))
        card.add_row(None, desc=excluded_text)

        def open_settings_folder():
            try:
                os.startfile(os.path.dirname(SETTINGS_FILE))
            except Exception as e:
                log(f"Не удалось открыть папку настроек: {e}")

        page.gap(14)
        card = page.card()
        row = card.add_row(t("settings_auto_update"), desc=t("settings_auto_update_desc"))
        auto_update_var = tk.BooleanVar(value=auto_update_check)
        ui_toggle(row.right, pal, auto_update_var).pack()
        row = card.add_row(t("settings_file_title"), desc=SETTINGS_FILE)
        W11Button(row.right, pal, t("settings_open_folder"), open_settings_folder).pack()

        # ---------- завершение ----------
        for key, canvas_ in zip(("general", "auto", "modes", "advanced", "about"), pages_canvases):
            ui_bind_wheel(pages[key], canvas_)
        _settings_ui["window"] = window
        _settings_ui["show_page"] = show_page
        show_page(start_page if start_page in pages else "general")
        window.protocol("WM_DELETE_WINDOW", on_cancel)
        window.update_idletasks()
        window.deiconify()
        ui_style_window(window, pal, dark)   # заголовок красим уже у существующего окна
        window.lift()
        window.focus_force()

    new_hotkey_mod = HOTKEY_MODIFIERS
    new_hotkey_vk = HOTKEY_VK
    recording_modifiers = set()
    tk_queue.put(('window', create_window))

def set_hdr_color_preset():
    global confirmed_hdr_active, hdr_confirmed_for_hwnd
    global standard_return_attempt_logged, standard_return_blocked_logged, standard_return_last_attempt_time
    global standard_restore_pending
    try:
        log("Проверка HDR для пресета...")
        # Другой поток (хоткей) – тот же game_state_lock, что и monitor_loop().
        with game_state_lock:
            hdr_check_result = is_hdr_enabled(force_refresh=True)
            # Ручное действие, не привязанное к окну (см. toggle_mode).
            confirmed_hdr_active = (hdr_check_result == "hdr")
            hdr_confirmed_for_hwnd = None
            standard_return_attempt_logged = False
            standard_return_blocked_logged = False
            standard_return_last_attempt_time = 0.0
            standard_restore_pending = False
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
            # Сохраняем последний процесс в подсказке (если игровой режим был
            # установлен автоматически), чтобы смена языка не теряла суффикс.
            update_tray_title(current_mode_index, last_tray_process_name)
        except Exception as e:
            log(f"Ошибка обновления меню трея: {e}")

def on_settings(icon, item):
    create_settings_window()

def on_about(icon, item):
    # Отдельного окна «О программе» нет: открываем настройки на странице «О программе».
    create_settings_window(start_page="about")

def on_quit(icon, item):
    global stop_hotkey_thread, media_timer, app_exiting
    stop_hotkey_thread = True
    app_exiting = True
    with media_timer_lock:
        if media_timer is not None:
            media_timer.cancel()
            media_timer = None
    try:
        if hotkey_thread_id:
            user32.PostThreadMessageW(hotkey_thread_id, 0x0012, 0, 0)   # WM_QUIT: GetMessageW вернёт 0, цикл закончится
    except Exception:
        pass
    icon.stop()

def hotkey_listener(icon):
    global hotkey_thread_id, stop_hotkey_thread, HOTKEY_MODIFIERS, HOTKEY_VK
    msg = ctypes.wintypes.MSG()
    # Очередь сообщений потока создаём сразу: иначе PostThreadMessageW, пришедший до первого GetMessageW, не дойдёт.
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
    my_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
    hotkey_thread_id = my_thread_id
    registered = None   # сочетание, которое сейчас действительно зарегистрировано этим потоком
    if user32.RegisterHotKey(None, HOTKEY_ID, HOTKEY_MODIFIERS | MOD_NOREPEAT, HOTKEY_VK):
        registered = (HOTKEY_MODIFIERS, HOTKEY_VK)
    else:
        # Поток не завершаем: сочетание могла занять другая программа, и пользователь должен суметь выбрать другое.
        log("Не удалось зарегистрировать горячую клавишу (возможно, она занята другой программой): её можно сменить в настройках")
        # Сочетание уже записано в настройках, поэтому при каждом запуске будет та же неудача: пользователь должен узнать о ней.
        show_notification(t("notif_hotkey_busy", hotkey=hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)))
    try:
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
                try:
                    user32.UnregisterHotKey(None, HOTKEY_ID)
                except Exception:
                    pass
                if user32.RegisterHotKey(None, HOTKEY_ID, pending_hotkey_mod | MOD_NOREPEAT, pending_hotkey_vk):
                    registered = (pending_hotkey_mod, pending_hotkey_vk)
                    HOTKEY_MODIFIERS, HOTKEY_VK = registered
                    log(f"Горячая клавиша обновлена: {hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)}")
                    show_notification(t("notif_hotkey", hotkey=hotkey_to_string(HOTKEY_MODIFIERS, HOTKEY_VK)))
                else:
                    show_notification(t("notif_hotkey_fail"))
                    # Окно настроек уже записало новое сочетание в HOTKEY_*, поэтому «прежнее» берём из того, что
                    # реально было зарегистрировано, а не из HOTKEY_*.
                    if registered and user32.RegisterHotKey(None, HOTKEY_ID, registered[0] | MOD_NOREPEAT, registered[1]):
                        HOTKEY_MODIFIERS, HOTKEY_VK = registered
                        log("Не удалось зарегистрировать новую горячую клавишу, возвращаем прежнюю")
                    else:
                        registered = None
                        log("Не удалось зарегистрировать новую горячую клавишу")
                    try:
                        save_settings()   # в файле должно остаться то сочетание, которое действует
                    except Exception as e:
                        log(f"Не удалось сохранить настройки: {e}")
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        if hotkey_thread_id == my_thread_id:
            hotkey_thread_id = None   # request_hotkey_update по этому признаку поймёт, что поток не работает

def start_tkinter():
    root = tk.Tk()
    root.withdraw()
    def process_queue():
        if app_exiting:
            root.quit()
            return
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
    try:
        root.destroy()
    except Exception:
        pass

SINGLE_INSTANCE_MUTEX_NAME = r"Local\TA-toggle.SingleInstance"
_instance_mutex_handle = None

def acquire_single_instance():
    """True – это первый экземпляр. Второй показывает сообщение и должен завершиться.
    Если сам mutex создать не удалось, запуск не блокируем."""
    global _instance_mutex_handle
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
    k32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    k32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    handle = k32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
    err = ctypes.get_last_error()
    if not handle:
        log(f"Не удалось создать mutex единственного экземпляра: {err}")
        return True
    if err == 183:  # ERROR_ALREADY_EXISTS
        k32.CloseHandle(handle)
        try:
            ctypes.windll.user32.MessageBoxW(None, t("err_already_running"), "TA-toggle", 0x40)
        except Exception:
            pass
        return False
    _instance_mutex_handle = handle
    return True

if __name__ == "__main__":
    load_settings()
    if not acquire_single_instance():
        sys.exit(0)
    migrate_legacy_autostart()
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
        log("Монитор при запуске не найден: поиск будет повторяться")
    sync_current_mode()

    tk_thread = threading.Thread(target=start_tkinter, daemon=True)
    tk_thread.start()

    tray_icon = pystray.Icon("monitor_toggle")
    tray_icon.icon = create_image(current_mode_index)
    rebuild_tray_menu()

    threading.Thread(target=lambda: hotkey_listener(tray_icon), daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()

    print(t("console_started", mode=get_mode_name(current_mode_index)))
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
    threading.Thread(target=lambda: (time.sleep(8), maybe_auto_check_update()), daemon=True).start()
    tray_icon.run()
    # Выход: даём потоку Tk корректно закрыться и завершаем процесс сразу. Иначе интерпретатор при остановке
    # может зависнуть на потоках (Tk-цикл, DDC-вызов), и консоль, из которой запущена программа, не вернёт приглашение.
    app_exiting = True
    tk_thread.join(timeout=1.5)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)
