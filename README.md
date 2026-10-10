# TA toggle (Titan Army Monitor Switcher)


Python-утилита для автоматического переключения настроек мониторов Titan Army.

Программа позволяет вручную или автоматически переключаться между "стандартным" и "игровым" пресетами яркости и локального затеменения монитора в зависимости от того, запущена ли игра или поддерживаемый медиаплеер.


## Возможности

- Автоматическое обнаружение игр
- Автоматическое обнаружение медиаплееров (MPC-HC, MPC-BE, VLC, PotPlayer)
- Обнаружение HDR
- Автоматическое переключение режима локального затемнения и яркости
- Ручное переключение режимов (Ctrl + Alt + Z)
- Исключение программ из автоматического переключения режимов

## Управление

### Ctrl + Alt + Z 

- Ручное Переключение режима монитора

## Автоматическое переключение

В программе настраиваются два режима локального затемнения и яркости. При работе в SDR программа сама переведет монитор в "игровой" режим при запуске игры или просмотре видео в VLC MPC и т.д. и вернет в "стандартный", когда игра закроется.

## Исключение программ

Если не нужно, чтобы программа влияла на автоматическое переключение режимов, можно добавить её в исключения. В настройках нажмите «Выбрать из запущенных», найдите нужную программу и добавьте её в список.

Если не знаете, какая программа вызвала переключение, наведите курсор на иконку программы в трее после автоматичской смены режима. Во всплывающей подсказке будет указано имя процесса, который её вызвал.

## License

MIT

# TA toggle (Titan Army Monitor Switcher)


Python utility for automatically switching settings on Titan Army monitors.

The program allows you to manually or automatically switch between Standard and Gaming presets for monitor brightness and local dimming, depending on whether a game or supported media player is running.

## Features
- Automatic game detection
- Automatic media player detection (MPC-HC, MPC-BE, VLC, PotPlayer)
- HDR detection
- Automatic switching of local dimming and brightness settings
- Manual mode switching (Ctrl + Alt + Z)
- Excluding Applications from Automatic Mode Switching

## Controls
### Ctrl + Alt + Z
- Manually switch between monitor modes

## Automatic Switching

The program lets you configure separate brightness and local dimming settings for two modes.
When running in SDR, the program automatically switches the monitor to Gaming mode when a game is launched or when video playback starts in VLC, MPC-HC, MPC-BE, PotPlayer, etc. It switches the monitor back to Standard mode when the game or media player is closed.

## Excluding Applications

If you don't want an application to trigger automatic mode switching, you can add it to the exclusion list. In the settings, click "Choose Running Process", find the application you want, and add it to the list.

If you're not sure which application triggered a mode switch, hover over the program's system tray icon after the mode switches automatically. A tooltip will show the name of the process that triggered it. 

## License

MIT
