#!/usr/bin/env python3
"""
phone_display.py — Android-телефон как второй монитор ноутбука по USB.

Как работает:
  1. Находит adb (или сам скачивает platform-tools от Google).
  2. Ждёт телефон по USB, делает `adb reverse` — телефон ходит на ПК через кабель,
     Wi-Fi и сеть не нужны.
  3. Захватывает выбранный монитор и отдаёт его как MJPEG-поток.
  4. Сам открывает страницу в браузере телефона. Касания = мышь на ПК.
  5. Если кабель выдернуть и вставить обратно — переподключится сам.

Запуск:  PhoneDisplay.exe / python phone_display.py
         --list            список мониторов
         --monitor 2 --fps 30 --quality 70

https://github.com/ShakalIST/Phone-Dispaly   (MIT)
"""
__version__ = "1.0.0"
import argparse
import ctypes
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import mss
    from PIL import Image, ImageDraw
except ImportError:
    print("Не хватает пакетов. Выполните:  python -m pip install mss pillow")
    sys.exit(1)

FROZEN = getattr(sys, "frozen", False)  # собран в PhoneDisplay.exe
APP_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
# журнал и скачанный adb — в профиле пользователя (Program Files только для чтения)
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "PhoneDisplay")
os.makedirs(DATA_DIR, exist_ok=True)
LOG_PATH = os.path.join(DATA_DIR, "phone_display.log")
BACKGROUND = sys.stdout is None or "pythonw" in os.path.basename(sys.executable).lower()
if BACKGROUND:  # без консоли (pythonw) всё пишем в журнал
    _log = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = _log
IS_WIN = os.name == "nt"
ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
NO_WINDOW = 0x08000000 if IS_WIN else 0  # не мигать окнами консоли при вызове adb

# Чтобы координаты совпадали при масштабе 125%/150% в Windows
if IS_WIN:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ───────────────────────────── ADB ─────────────────────────────

def find_adb() -> str:
    exe = "adb.exe" if IS_WIN else "adb"
    for base in (APP_DIR, DATA_DIR):
        cand = os.path.join(base, "platform-tools", exe)
        if os.path.isfile(cand):
            return cand
    found = shutil.which("adb")
    if found:
        return found
    if not IS_WIN:
        sys.exit("adb не найден. Установите пакет android-tools / adb.")
    local = os.path.join(DATA_DIR, "platform-tools", exe)
    print("adb не найден — скачиваю platform-tools с сайта Google (~7 МБ)...")
    zpath = os.path.join(DATA_DIR, "platform-tools.zip")
    urllib.request.urlretrieve(ADB_URL, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(DATA_DIR)
    os.remove(zpath)
    print("adb скачан.")
    return local


def adb(adb_path, *args, timeout=15):
    try:
        r = subprocess.run([adb_path, *args], capture_output=True, text=True,
                           timeout=timeout, creationflags=NO_WINDOW)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, "timeout"


def device_state(adb_path):
    """Возвращает (serial, state) первого телефона или (None, None)."""
    _, out = adb(adb_path, "devices")
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            return parts[0], parts[1]
    return None, None


HINTS = {
    None: "Телефон не виден. Подключите кабель и включите «Отладку по USB»\n"
          "  (Настройки → О телефоне → 7 раз нажать «Номер сборки», затем\n"
          "  Настройки → Для разработчиков → Отладка по USB).",
    "unauthorized": "На экране телефона подтвердите «Разрешить отладку по USB»\n"
                    "  (поставьте галочку «Всегда разрешать с этого компьютера»).",
    "offline": "Телефон в состоянии offline — переподключите кабель.",
}


def device_watcher(adb_path, port, on_connect):
    """Следит за телефоном и при каждом подключении настраивает проброс."""
    last_ok, last_hint = None, object()
    while True:
        serial, state = device_state(adb_path)
        ok = state == "device"
        if ok and serial != last_ok:
            code, out = adb(adb_path, "-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}")
            if code == 0:
                print(f"[+] Телефон {serial} подключён, порт {port} проброшен по USB.")
                on_connect(serial)
                last_ok = serial
            else:
                print("[!] Не удалось сделать adb reverse:", out)
        elif not ok:
            if last_ok:
                print("[-] Телефон отключён. Жду переподключения...")
            last_ok = None
            if state != last_hint:
                print("[?]", HINTS.get(state, f"Состояние телефона: {state}"))
                last_hint = state
        time.sleep(2)


# ──────────────────────── Захват экрана ────────────────────────

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def cursor_pos():
    if not IS_WIN:
        return None
    p = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def new_mss():
    """mss >= 10 переименовал mss.mss в mss.MSS."""
    return (getattr(mss, "MSS", None) or mss.mss)()


class Grabber:
    def __init__(self, mon, fps, quality, max_width, show_cursor=True, auto=True):
        self.mon, self.fps, self.quality = mon, fps, quality
        self.auto = auto  # сам переключаться, если мониторы добавились/пропали
        self.max_width, self.show_cursor = max_width, show_cursor
        self.frame, self.seq, self.clients = None, 0, 0
        self.cond = threading.Condition()

    def add_client(self, delta):
        with self.cond:
            self.clients += delta
            self.cond.notify_all()

    def run(self):
        period = 1.0 / self.fps
        sct, last_check, fails = None, 0.0, 0
        while True:
            with self.cond:  # не грузим CPU, пока никто не смотрит
                self.cond.wait_for(lambda: self.clients > 0)
            t0 = time.perf_counter()
            try:
                if sct is None or (self.auto and t0 - last_check > 3):
                    last_check = t0  # раз в 3 с перечитываем список мониторов
                    if sct is not None:
                        try:
                            sct.close()
                        except Exception:
                            pass
                    sct = new_mss()
                    if self.auto:
                        idx, mon = pick_monitor(sct.monitors, None)
                        if mon != self.mon:
                            self.mon = mon
                            print(f"[*] Мониторы изменились — показываю монитор {idx}: "
                                  f"{mon['width']}x{mon['height']}")
                self._frame(sct)
                fails = 0
            except Exception as e:
                # блокировка экрана, выход из сна, смена разрешения — переподключаемся
                fails += 1
                if fails in (1, 10) or fails % 100 == 0:
                    print(f"[!] Ошибка захвата экрана ({e}), пробую снова...")
                sct = None
                time.sleep(min(2.0, 0.2 * fails))
                continue
            time.sleep(max(0.0, period - (time.perf_counter() - t0)))

    def _frame(self, sct):
        mon = self.mon
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        if self.show_cursor:
            cp = cursor_pos()
            if cp:
                cx, cy = cp[0] - mon["left"], cp[1] - mon["top"]
                if 0 <= cx < img.width and 0 <= cy < img.height:
                    r = max(6, img.width // 250)
                    d = ImageDraw.Draw(img)
                    d.ellipse((cx - r, cy - r, cx + r, cy + r),
                              fill=(255, 255, 255), outline=(0, 0, 0), width=2)

        if img.width > self.max_width:
            h = round(img.height * self.max_width / img.width)
            img = img.resize((self.max_width, h), Image.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=self.quality)
        with self.cond:
            self.frame = buf.getvalue()
            self.seq += 1
            self.cond.notify_all()


# ──────────────────────── Ввод (мышь) ─────────────────────────

class Mouse:
    LDOWN, LUP, RDOWN, RUP, WHEEL = 0x0002, 0x0004, 0x0008, 0x0010, 0x0800

    def __init__(self, grabber):
        self.g = grabber
        self.u32 = ctypes.windll.user32 if IS_WIN else None

    def _xy(self, nx, ny):
        nx, ny = min(max(nx, 0.0), 1.0), min(max(ny, 0.0), 1.0)
        m = self.g.mon
        return (m["left"] + round(nx * (m["width"] - 1)),
                m["top"] + round(ny * (m["height"] - 1)))

    def handle(self, ev):
        if not self.u32:
            return
        t = ev.get("t")
        if t in ("down", "move", "up", "rclick"):
            self.u32.SetCursorPos(*self._xy(ev["x"], ev["y"]))
        if t == "down":
            self.u32.mouse_event(self.LDOWN, 0, 0, 0, 0)
        elif t == "up":
            self.u32.mouse_event(self.LUP, 0, 0, 0, 0)
        elif t == "rclick":
            self.u32.mouse_event(self.RDOWN, 0, 0, 0, 0)
            self.u32.mouse_event(self.RUP, 0, 0, 0, 0)
        elif t == "wheel":
            self.u32.mouse_event(self.WHEEL, 0, 0, int(ev.get("d", 0)), 0)


# ─────────────────────── Страница на телефоне ───────────────────────

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Второй монитор</title>
<style>
 html,body{margin:0;height:100%;background:#000;overflow:hidden;touch-action:none;user-select:none}
 #s{position:fixed;inset:0;width:100vw;height:100vh;object-fit:contain}
 #h{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
    color:#fff;font:20px sans-serif;text-align:center;background:rgba(0,0,0,.6)}
</style></head><body>
<img id="s" src="/stream">
<div id="h">Нажмите, чтобы развернуть на весь экран</div>
<script>
const TOUCH = __TOUCH__;
const img = document.getElementById('s'), hint = document.getElementById('h');
let wake = null;

async function goFull(){
  try { await document.documentElement.requestFullscreen(); } catch(e){}
  try { await screen.orientation.lock('landscape'); } catch(e){}
  try { wake = await navigator.wakeLock.request('screen'); } catch(e){}
  hint.style.display = 'none';
}
hint.addEventListener('click', goFull);
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement) hint.style.display = 'flex';
});
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible') {
    try { wake = await navigator.wakeLock.request('screen'); } catch(e){}
  }
});

// переподключение потока, если связь пропала
img.onerror = () => setTimeout(() => img.src = '/stream?' + Date.now(), 1000);

function send(o){
  fetch('/input', {method:'POST', body: JSON.stringify(o), keepalive:true}).catch(()=>{});
}
// касание -> координаты 0..1 внутри картинки (учитываем чёрные поля)
function norm(e){
  const r = img.getBoundingClientRect(), nw = img.naturalWidth, nh = img.naturalHeight;
  if (!nw) return null;
  const k = Math.min(r.width / nw, r.height / nh), w = nw * k, h = nh * k;
  return { x: (e.clientX - r.left - (r.width - w) / 2) / w,
           y: (e.clientY - r.top - (r.height - h) / 2) / h };
}

if (TOUCH) {
  const pts = new Map();
  let longT = null, down = false, startP = null, lastMove = 0, scrollY = null;

  img.addEventListener('pointerdown', e => {
    pts.set(e.pointerId, e);
    if (pts.size === 2) {                 // два пальца = прокрутка
      clearTimeout(longT);
      if (down) { send({t:'up', ...norm(e)}); down = false; }
      scrollY = e.clientY; return;
    }
    const p = norm(e); if (!p) return;
    startP = {x: e.clientX, y: e.clientY};
    send({t:'move', ...p});
    longT = setTimeout(() => {            // долгое нажатие = правый клик
      longT = null; startP = null; send({t:'rclick', ...p});
    }, 600);
  });

  img.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, e);
    if (pts.size >= 2) {
      const dy = e.clientY - scrollY;
      if (Math.abs(dy) > 15) { send({t:'wheel', d: dy > 0 ? 120 : -120}); scrollY = e.clientY; }
      return;
    }
    if (!startP) return;
    const moved = Math.hypot(e.clientX - startP.x, e.clientY - startP.y) > 10;
    if (moved && longT) {                 // начали тянуть = зажатая ЛКМ
      clearTimeout(longT); longT = null; send({t:'down', ...norm(e)}); down = true;
    }
    const now = performance.now();
    if (down && now - lastMove > 25) { lastMove = now; send({t:'move', ...norm(e)}); }
  });

  function end(e){
    if (!pts.has(e.pointerId)) return;
    pts.delete(e.pointerId);
    if (pts.size > 0) return;
    scrollY = null;
    const p = norm(e);
    if (longT) { clearTimeout(longT); longT = null; send({t:'down', ...p}); send({t:'up', ...p}); }
    else if (down) { send({t:'up', ...p}); }
    down = false; startP = null;
  }
  img.addEventListener('pointerup', end);
  img.addEventListener('pointercancel', end);
}
</script></body></html>"""


def make_handler(grabber, mouse, touch):
    page = PAGE.replace("__TOUCH__", "true" if touch else "false").encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/stream"):
                return self.stream()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            grabber.add_client(+1)
            last = -1
            try:
                while True:
                    with grabber.cond:
                        grabber.cond.wait_for(lambda: grabber.seq != last, timeout=2)
                        frame, last = grabber.frame, grabber.seq
                    if frame is None:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                     b"Content-Length: %d\r\n\r\n" % len(frame))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                grabber.add_client(-1)

        def do_POST(self):
            if self.path == "/input" and touch:
                n = int(self.headers.get("Content-Length", 0))
                try:
                    mouse.handle(json.loads(self.rfile.read(n) or b"{}"))
                except Exception:
                    pass
            self.send_response(204)
            self.end_headers()

    return Handler


# ─────────────────────────── main ───────────────────────────

def pick_monitor(monitors, wanted):
    real = monitors[1:]  # [0] в mss — все экраны вместе
    if wanted:
        if not 1 <= wanted <= len(real):
            sys.exit(f"Нет монитора {wanted}. Посмотрите список: --list")
        return wanted, real[wanted - 1]
    # по умолчанию — первый НЕ основной монитор (основной начинается в 0,0)
    for i, m in enumerate(real, 1):
        if (m["left"], m["top"]) != (0, 0):
            return i, m
    return 1, real[0]


def main():
    ap = argparse.ArgumentParser(description="Телефон как второй монитор по USB")
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--list", action="store_true", help="показать мониторы и выйти")
    ap.add_argument("--monitor", type=int, help="номер монитора (по умолчанию — второй, если есть)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--quality", type=int, default=70, help="качество JPEG 30..95")
    ap.add_argument("--max-width", type=int, default=1920, help="уменьшать картинку до этой ширины")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-touch", action="store_true", help="телефон только показывает, без управления")
    ap.add_argument("--no-cursor", action="store_true", help="не рисовать курсор")
    ap.add_argument("--no-tray", action="store_true", help="без значка в трее")
    args = ap.parse_args()

    with new_mss() as sct:
        monitors = sct.monitors
    if args.list:
        for i, m in enumerate(monitors[1:], 1):
            main_mark = " (основной)" if (m["left"], m["top"]) == (0, 0) else ""
            print(f"  {i}: {m['width']}x{m['height']} в точке ({m['left']},{m['top']}){main_mark}")
        return

    idx, mon = pick_monitor(monitors, args.monitor)
    print(f"Показываю монитор {idx}: {mon['width']}x{mon['height']}")
    if len(monitors) == 2 and not args.monitor:
        print("  Второго монитора в системе нет — телефон будет ДУБЛИРОВАТЬ экран.\n"
              "  Чтобы был отдельный рабочий стол, поставьте виртуальный дисплей (см. README на GitHub).")

    grabber = Grabber(mon, args.fps, args.quality, args.max_width,
                      not args.no_cursor, auto=not args.monitor)
    threading.Thread(target=grabber.run, daemon=True).start()

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                     make_handler(grabber, Mouse(grabber), not args.no_touch))
    except OSError:
        print(f"Порт {args.port} занят — программа уже запущена (значок в трее).")
        if not BACKGROUND:
            time.sleep(4)
        return
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()

    adb_path = find_adb()
    url = f"http://127.0.0.1:{args.port}/"

    state = {"serial": None}

    def open_on_phone(serial):
        state["serial"] = serial
        adb(adb_path, "-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
        # 1) сразу в Chrome (на realme/ColorOS общий VIEW иногда молча игнорируется)
        code, out = adb(adb_path, "-s", serial, "shell", "am", "start", "-n",
                        "com.android.chrome/com.google.android.apps.chrome.Main",
                        "-a", "android.intent.action.VIEW", "-d", url)
        if code != 0 or "Error" in out:
            # 2) Chrome нет — браузер по умолчанию
            code, out = adb(adb_path, "-s", serial, "shell", "am", "start",
                            "-a", "android.intent.action.VIEW", "-d", url)
        if "Error" in out:
            print("[!] Телефон не дал открыть браузер:", out)
        print(f"    [{datetime.now():%H:%M:%S}] Открываю {url} на телефоне. Если страница "
              f"не появилась — разблокируйте телефон и нажмите значок в трее.")

        def check():  # если за 8 с поток никто не смотрит — пробуем ещё раз
            time.sleep(8)
            if grabber.clients == 0 and state["serial"] == serial:
                print("[?] Страница на телефоне не открылась, пробую ещё раз "
                      "(разблокируйте экран телефона).")
                adb(adb_path, "-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
                adb(adb_path, "-s", serial, "shell", "am", "start",
                    "-a", "android.intent.action.VIEW", "-d", url)
        threading.Thread(target=check, daemon=True).start()

    def reopen():
        if state["serial"]:
            open_on_phone(state["serial"])
        else:
            print("Телефон ещё не подключён.")

    def quit_app():
        print("Выход.")
        adb(adb_path, "reverse", "--remove-all")
        os._exit(0)

    def enter_to_reopen():
        while True:
            try:
                input()
            except Exception:  # нет консоли / EOF
                return
            reopen()

    if not BACKGROUND:
        threading.Thread(target=enter_to_reopen, daemon=True).start()
        print("Enter — открыть страницу на телефоне заново, Ctrl+C — выход.\n")

    watcher = threading.Thread(target=device_watcher,
                               args=(adb_path, args.port, open_on_phone), daemon=True)
    watcher.start()

    if not args.no_tray and run_tray(reopen, quit_app):
        return  # трей работает до «Выход»
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        quit_app()


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "PhoneDisplay"


def autostart_command():
    if FROZEN:
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw if os.path.isfile(pyw) else sys.executable}" "{os.path.abspath(__file__)}"'


def autostart_enabled():
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except OSError:
                pass
    print("Автозапуск", "включён" if on else "выключен")


def run_tray(on_open, on_quit):
    """Значок в трее. Возвращает False, если pystray не установлен."""
    try:
        import pystray
    except ImportError:
        print("pystray не установлен — работаю без значка в трее.")
        return False
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((18, 4, 46, 60), radius=6, fill=(40, 120, 220), outline=(255, 255, 255), width=3)
    d.rectangle((23, 11, 41, 50), fill=(220, 235, 255))
    menu = pystray.Menu(
        pystray.MenuItem("Открыть на телефоне", lambda icon, item: on_open(), default=True),
        pystray.MenuItem("Запускать вместе с Windows",
                         lambda icon, item: set_autostart(not autostart_enabled()),
                         checked=lambda item: autostart_enabled(), visible=IS_WIN),
        pystray.MenuItem("Журнал", lambda icon, item: os.startfile(LOG_PATH) if IS_WIN else None,
                         visible=BACKGROUND),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Выход", lambda icon, item: (icon.stop(), on_quit())),
    )
    pystray.Icon("phone_display", img, f"Phone Display {__version__} — телефон как второй монитор", menu).run()
    return True

if __name__ == "__main__":
    main()
