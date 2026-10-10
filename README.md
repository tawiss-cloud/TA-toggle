# TA toggle (Titan Army Monitor Switcher)


Python-утилита для автоматического переключения настроек мониторов Titan Army.

Программа позволяет вручную или автоматически переключаться между "стандартным" и "игровым" пресетами яркости и локального затеменения монитора в зависимости от того, запущена ли игра или поддерживаемый медиаплеер.


## Возможности

- Автоматическое обнаружение игр
- Автоматическое обнаружение медиаплееров (MPC-HC, MPC-BE, VLC, PotPlayer)
- Обнаружение HDR
- Автоматическое переключение режима локального затемнения и яркости
- Ручное переключение режимов (Ctrl + Alt + Z)
- Пользовательские исключения: ручное добавление приложений и процессов

## Управление

### Ctrl + Alt + Z 

- Ручное Переключение режима монитора

## Автоматическое переключение

В программе настраиваются два режима локального затемнения и яркости. При работе в SDR программа сама переведет монитор в "игровой" режим при запуске игры или просмотре видео в VLC MPC и т.д. и вернет в "стандартный", когда игра закроется.

## Ручное исключение процессов

Если для какой-то программы автоматическое переключение не нужно, её процесс можно добавить в исключения. Для этого в настройках нажмите «Выбрать из запущенных», выберите нужный процесс и добавьте его в список исключений. После этого программа не будет учитывать его при автоматической смене режимов.

Чтобы узнать, какой именно процесс переключил режим, после срабатывания автоматического переключения наведите курсор на иконку программы — во всплывающей подсказке будет указано имя этого процесса. Это удобно, если нужно быстро найти и исключить приложение, из-за которого сменился режим.

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
- Custom exclusions: manually add applications and processes

## Controls
### Ctrl + Alt + Z
- Manually switch between monitor modes

## Automatic Switching

The program lets you configure separate brightness and local dimming settings for two modes.
When running in SDR, the program automatically switches the monitor to Gaming mode when a game is launched or when video playback starts in VLC, MPC-HC, MPC-BE, PotPlayer, etc. It switches the monitor back to Standard mode when the game or media player is closed.

## Manual process exclusion

If you don’t need automatic switching for a certain application, you can add its process to the exclusions. To do this, in the settings click “Select from running”, select the desired process, and add it to the exclusion list. After that, the program will ignore it during automatic mode switching.

To find out which process switched the mode, after automatic switching is triggered, hover the cursor over the program icon — the name of that process will be shown in the tooltip. This is convenient if you need to quickly find and exclude the application that caused the mode change.

## License

MIT
