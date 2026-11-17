# Phone Display

Android-телефон как второй монитор для ноутбука на Windows — **по USB-кабелю**, без Wi-Fi и без приложений на телефоне.

Подключили кабель → на телефоне сам открывается второй рабочий стол. Касания по экрану телефона управляют мышью.

*English version below.*

## Установка

1. Скачайте `PhoneDisplay-Setup-x.y.z.exe` со страницы [Releases](../../releases/latest) и запустите.
2. Оставьте галочки:
   - **Установить виртуальный экран** — телефон получит отдельный рабочий стол, а не копию экрана ноутбука;
   - **Запускать вместе с Windows**.
3. Если Windows спросит, доверять ли издателю драйвера — нажмите «Установить».
4. Откройте **Параметры → Система → Дисплей**, выберите «Расширить эти экраны», нажмите на экран **2** и задайте разрешение (например 1920×1080).

### Подготовка телефона (один раз)
1. Настройки → О телефоне → 7 раз нажмите «Номер сборки» (включатся «Параметры разработчика»).
2. Настройки → Для разработчиков → включите **Отладку по USB**.
3. Подключите телефон кабелем и нажмите «Разрешить» (с галочкой «Всегда разрешать с этого компьютера»).

## Как пользоваться

Программа живёт в трее (синий значок телефона возле часов).

- Подключите **разблокированный** телефон — браузер с вторым экраном откроется сам.
- Нажмите на экран телефона, чтобы включить полноэкранный режим.
- Перетащите окно за правый край экрана ноутбука — оно появится на телефоне.

| Жест на телефоне | Действие |
|---|---|
| Касание | клик |
| Касание и протянуть | перетаскивание |
| Долгое нажатие | правый клик |
| Два пальца вверх/вниз | прокрутка |

Меню значка в трее: «Открыть на телефоне», «Запускать вместе с Windows», «Журнал», «Выход».

## Частые проблемы

- **Страница не открылась на телефоне** — телефон был заблокирован. Разблокируйте его и нажмите «Открыть на телефоне» в трее.
- **Телефон дублирует экран ноутбука** — не установлен виртуальный экран или в настройках дисплея выбрано «Дублировать». Выберите «Расширить эти экраны».
- **После обновления видеодрайвера экран ноутбука чёрный** — нажмите Win+P → «Только экран компьютера».
- **Антивирус ругается на exe** — так бывает с программами, собранными PyInstaller. Исходный код открыт, установщик собирается GitHub Actions из этого репозитория.
- Журналы: `%LOCALAPPDATA%\PhoneDisplay\phone_display.log`, установка драйвера — `%ProgramData%\PhoneDisplay\vdd_install.log`.

## Как это работает

- `adb reverse` пробрасывает порт через USB: телефон открывает `http://127.0.0.1:8765` и получает картинку через кабель.
- Экран захватывается ([mss](https://github.com/BoboTiG/python-mss)) и отдаётся как MJPEG-поток в браузер телефона.
- Касания отправляются обратно и превращаются в события мыши Windows.
- Отдельный рабочий стол даёт [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver) (MIT), его ставит установщик через winget.
- `adb` при первом запуске скачивается с официального сайта Google в `%LOCALAPPDATA%\PhoneDisplay`.
- Сервер слушает только `127.0.0.1` — из локальной сети он недоступен.

## Параметры запуска

```
PhoneDisplay.exe --list             список мониторов
PhoneDisplay.exe --monitor 2        выбрать монитор вручную
PhoneDisplay.exe --fps 20           меньше нагрузка
PhoneDisplay.exe --quality 50       быстрее, но картинка мыльнее
PhoneDisplay.exe --max-width 1280   меньше задержка
PhoneDisplay.exe --no-touch         только показ, без управления
```

## Сборка из исходников

```
git clone https://github.com/ShakalIST/phone-display
cd phone-display
scripts\run_from_source.bat        запуск с консолью
scripts\build.bat 1.0.0            сборка установщика (нужен Inno Setup 6)
```

Релиз: создайте тег `vX.Y.Z` и запушьте его — GitHub Actions соберёт установщик и прикрепит к релизу.

---

## English

Use an Android phone as a second monitor for a Windows laptop **over a USB cable** — no Wi-Fi, no app on the phone.

1. Download `PhoneDisplay-Setup-x.y.z.exe` from [Releases](../../releases/latest) and run it (keep "Install a virtual display" and "Start with Windows" checked).
2. In Windows *Settings → Display* choose "Extend these displays".
3. On the phone enable *USB debugging*, connect the cable, allow debugging.
4. The phone's browser opens the second screen automatically. Tap = click, drag = drag, long press = right click, two fingers = scroll.

How it works: `adb reverse` over USB + MJPEG stream of the captured monitor + touch → mouse events. The separate desktop comes from [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver).

## License

MIT
