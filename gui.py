#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINK UNIQUIFIER — GUI (тёмная тема «slate», прокручиваемая страница).

Дизайн:
  • тёмный визуал — сине-графитовая палитра и синий акцент (вместо
    чёрно-зелёной), плоские панели с акцентной точкой вместо эмодзи-заголовков;
  • тултипы убраны полностью;
  • убраны «маркировки» — жёлтый дисклеймер, статус-баннеры «✅ готово», мелкие
    подписи-подсказки под контролами;
  • страница ПРОКРУЧИВАЕТСЯ (CTkScrollableFrame). Поэтому контент больше НЕ
    «ужимается» при уменьшении высоты окна — он просто скроллится и одинаково
    нормально выглядит на любом размере экрана/окна;
  • блок результата — фиксированной высоты со своим скроллом; колесо над ним
    крутит ТОЛЬКО его (изоляция), а не всю страницу.

Запуск:  python gui.py
"""

import time
import queue
import multiprocessing as mp
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from main import (
    uniquify_url,
    generate_cloud_redirect_page,
    randomization_strength,
    generate_worker,
    PARAM_POOL,
    WRAPPER_NAMES,
)


# ═══════════════════════════════════════════════════════════
#  ТЕМА  (тёмная «slate» — намеренно ДРУГАЯ, синий акцент)
# ═══════════════════════════════════════════════════════════

# Палитра: глубокий нейтральный фон, карточки-фреймы, тонкие границы, mono-подписи
# + СИНИЙ акцент. Зелёный #4ade80 запрещён намеренно (гейт G25): визуал не должен
# скатиться обратно в чёрно-зелёный.
COLOR_BG          = "#0b0d12"  # фон окна — глубокий графит с уходом в синий
COLOR_BG2         = "#0f1116"  # шапка-хром / вторичный фон
COLOR_PANEL       = "#15171d"  # карточки-секции
COLOR_PANEL2      = "#1a1d24"  # приподнятые поверхности
COLOR_FIELD       = "#0e1015"  # поля ввода / результат (глубже карточек)
COLOR_ACCENT      = "#4f8cff"  # СИНИЙ акцент (НЕ зелёный — гейт G25)
COLOR_ACCENT_HVR  = "#3b74e6"
COLOR_ACCENT_SOFT = "#16233c"  # синяя «accent-bg» поверхность (бренд-чип, ghost-акцент)
COLOR_ERROR       = "#f87171"
COLOR_WARN        = "#fbbf24"
COLOR_INFO        = "#38bdf8"
COLOR_TEXT        = "#e6e8ec"
COLOR_TEXT_DIM    = "#8b90a0"
COLOR_TEXT_DIM2   = "#5b606e"  # mono-подписи, совсем тускло
COLOR_BORDER      = "#262a33"
COLOR_BORDER2     = "#323744"  # границы полей/кнопок (на ступень светлее)
COLOR_BTN         = "#1a1d24"  # вторичные кнопки
COLOR_BTN_HVR     = "#232733"

FONT_FAMILY = "Segoe UI"
FONT_MONO   = "Consolas"

WRAPPER_OPTIONS = ["random"] + WRAPPER_NAMES

# Безопасный максимум: неломающие техники всегда ВКЛ, опасные ВЫКЛ и скрыты.
SAFE_TECHNIQUES = dict(
    use_anchor=True, use_case_mix=True, use_encoding=True,
    use_shuffle=True, use_trailing_slash=True,
    use_subdomain=False, use_fake_path=False, use_dot_segments=False,
    use_percent_random=False, use_proto_random=False,
)
DEFAULT_PARAMS_MIN = 5
DEFAULT_PARAMS_MAX = 8
DEFAULT_LAYERS = 1

# Подсказки поля «свои параметры» — по одной на режим сегмента. Показываем ПРЯМО
# в поле, что и как вписывать, чтобы формат не приходилось угадывать: в «через &»
# — список через запятую (каждый пункт станет отдельным ?параметром), в «как есть»
# — строка дословно дописывается в самый конец (для #-фрагментов, не для меток).
CUSTOM_PH_THROUGH = ("перечисли через запятую:  utm_source=newsletter, "
                     "sub={SUBID}, click_id={CLICKID}")
CUSTOM_PH_ASIS = ("дословно в самый конец:  #{LINK}  или  #promo   ·   "
                  "для фрагментов, не для трек-параметров")

# Объёмы генерации
MAX_LINKS   = 2_000_000     # весь набор держим в памяти для листания/копирования
MAX_SPINTAX = 100_000       # спинтакс — одна строка, держим разумно
PAGE_SIZE   = 1_000         # ссылок на страницу: в текстбокс рендерим ТОЛЬКО одну

# Бюджет работы на один кадр кооперативной генерации (~18 мс → ~55 кадров/сек).
# Это ФОЛБЭК-путь (в одном потоке): окно остаётся живым, но при скролле во время
# генерации всё равно подлагивает — UI-поток занят чанками ~18мс, а таймер Windows
# квантует after по ~15.6мс, так что мельче дробить бесполезно (замерено).
_GEN_FRAME_BUDGET = 0.018

# Порог, с которого генерация уходит в ОТДЕЛЬНЫЙ ПРОЦЕСС (см. _start_generation):
# тогда UI-поток свободен и окно плавно скроллится во время генерации. Мелкие
# объёмы делаем в этом же потоке — они завершаются мгновенно, лагать нечему, а
# ~0.5с на старт процесса того не стоят.
_MP_THRESHOLD = 5_000
_MP_POLL_MS = 30            # как часто UI переливает готовые батчи из очереди процесса

# Высота блока результата фиксированная — страница скроллится, а результат имеет
# свой скролл. Так ничто не «ужимается» при изменении размера окна.
RESULT_HEIGHT = 380


# ═══════════════════════════════════════════════════════════
#  ЧИСТЫЕ ФУНКЦИИ (тестируемы без окна)
# ═══════════════════════════════════════════════════════════

def _validate_positive_int(new_value: str) -> bool:
    """Разрешает пустую строку или неотрицательное целое (без верхней границы)."""
    if new_value == "":
        return True
    try:
        return int(new_value) >= 0
    except ValueError:
        return False


def clipboard_intent(state, keycode, keysym):
    """
    Что сделать по Ctrl+<клавиша>. Решаем по KEYCODE (физическая клавиша), а не
    по символу: при русской раскладке Ctrl+V шлёт 'м', но keycode тот же 86.
    Латинскую букву отдаём родному биндингу Tk (не дублируем).
    """
    if not (state & 0x4):
        return None
    ks = (keysym or "").lower()
    if keycode == 86 and ks != "v":
        return "paste"
    if keycode == 67 and ks != "c":
        return "copy"
    if keycode == 88 and ks != "x":
        return "cut"
    if keycode == 65 and ks != "a":
        return "select_all"
    return None


def wants_defocus(widget_class: str) -> bool:
    """True, если по клику на этот виджет нужно СНЯТЬ фокус с инпута."""
    return widget_class not in ("Entry", "TEntry", "Text", "TText", "Listbox")


def clamp_count(n, cap: int = MAX_LINKS) -> int:
    """Ограничивает количество ссылок диапазоном [1..cap] (лимита 10к больше нет)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return 1
    return max(1, min(n, cap))


def page_bounds(total: int, page_size: int, page: int):
    """
    Границы страницы для пагинации. Возвращает (start, end, total_pages, page),
    где page уже приведён к [0..total_pages-1]. Пустой набор — 1 пустая страница.
    """
    if page_size < 1:
        page_size = 1
    total = max(0, int(total))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(int(page), total_pages - 1))
    start = page * page_size
    end = min(start + page_size, total)
    return start, end, total_pages, page


# ═══════════════════════════════════════════════════════════
#  ПРИЛОЖЕНИЕ
# ═══════════════════════════════════════════════════════════

class LinkUniquifierApp(ctk.CTk):
    """Главное окно."""

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("LINK UNIQUIFIER")
        # Дефолт комфортный, minsize маленький — на меньших окнах страница
        # ПРОКРУЧИВАЕТСЯ, а не ужимается.
        self.geometry("1180x860")
        self.minsize(760, 560)
        self.configure(fg_color=COLOR_BG)

        self._vcmd_int = (self.register(_validate_positive_int), '%P')

        # Весь сгенерированный набор + состояние пагинации.
        self.links = []
        self.page = 0
        self.spintax_text = None

        # Состояние кооперативной генерации (кадрами через after)
        self._generating = False
        self._gen = None
        self._gen_cancel = False
        # Состояние генерации в отдельном процессе (None = процесс не запущен)
        self._mp = None
        # Ctrl+C, пойманный внутри after-колбэка Tk (см. report_callback_exception)
        self._interrupted = False

        self._build_ui()

        self.bind_all("<Control-KeyPress>", self._on_ctrl_key, add="+")
        self.bind_all("<Button-1>", self._on_global_click, add="+")
        self._update_strength()

    def report_callback_exception(self, exc, val, tb):
        """Ctrl+C (KeyboardInterrupt) может прилететь ВНУТРЬ after-колбэка Tk — напр.
        в периодический цикл трекера темы customtkinter. Тогда его перехватывает
        диспетчер колбэков Tkinter (ЭТОТ метод корня), а не main(), и по умолчанию
        печатает простыню трейсбека «Exception in Tkinter callback». Это НЕ краш:
        тихо гасим mainloop и помечаем штатное закрытие. Прочие исключения показываем
        как обычно — реальные баги прятать нельзя."""
        if issubclass(exc, (KeyboardInterrupt, SystemExit)):
            self._interrupted = True
            try:
                self.quit()
            except Exception:
                pass
            return
        import traceback
        traceback.print_exception(exc, val, tb)

    def destroy(self):
        """При закрытии окна гасим воркер-процесс генерации, чтобы не оставлять
        «зомби» после закрытия приложения."""
        self._kill_worker()
        super().destroy()

    def _kill_worker(self):
        m = getattr(self, "_mp", None)
        if not m:
            return
        try:
            m["stop"].set()
            proc = m.get("proc")
            if proc is not None and proc.is_alive():
                proc.terminate()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #  UI BUILDER — прокручиваемая страница
    # ══════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # ── Шапка-хром (фиксирована сверху) — не скроллится:
        #    бренд-чип + двухцветный вордмарк + правый статус-индикатор + разделитель.
        self.header = ctk.CTkFrame(self, fg_color=COLOR_BG2, corner_radius=0, height=66)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)
        hbar = ctk.CTkFrame(self.header, fg_color="transparent")
        hbar.pack(fill="both", expand=True, padx=22, pady=11)
        self.brand_chip = ctk.CTkLabel(
            hbar, text="⬡", width=42, height=42, corner_radius=12,
            fg_color=COLOR_ACCENT_SOFT, text_color=COLOR_ACCENT,
            font=(FONT_FAMILY, 21, "bold"))
        self.brand_chip.pack(side="left")
        wm = ctk.CTkFrame(hbar, fg_color="transparent")
        wm.pack(side="left", padx=(13, 0))
        wmrow = ctk.CTkFrame(wm, fg_color="transparent")
        wmrow.pack(anchor="w")
        ctk.CTkLabel(wmrow, text="LINK", font=(FONT_FAMILY, 17, "bold"),
                     text_color=COLOR_ACCENT).pack(side="left")
        ctk.CTkLabel(wmrow, text=" UNIQUIFIER", font=(FONT_FAMILY, 17, "bold"),
                     text_color=COLOR_TEXT).pack(side="left")
        ctk.CTkLabel(wm, text="уникализатор ссылок для рассылок",
                     font=(FONT_MONO, 10), text_color=COLOR_TEXT_DIM2,
                     anchor="w").pack(anchor="w", pady=(1, 0))
        self.bridge_label = ctk.CTkLabel(
            hbar, text="● готов к работе", font=(FONT_MONO, 11),
            text_color=COLOR_TEXT_DIM, anchor="e")
        self.bridge_label.pack(side="right")
        ctk.CTkFrame(self, fg_color=COLOR_BORDER, height=1,
                     corner_radius=0).pack(fill="x", side="top")

        # Вся страница внутри прокручиваемого фрейма: контент не ужимается —
        # при нехватке высоты появляется вертикальный скролл.
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_BG, corner_radius=0,
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_BTN_HVR)
        self.scroll.pack(fill="both", expand=True, padx=14, pady=(12, 6))
        page = self.scroll

        # ── Секция: ссылка ──
        s1 = self._panel(page, "ССЫЛКА", "оффер · количество ссылок · режим генерации",
                         icon="🔗")
        self.url_entry = self._entry(
            s1, "Вставь ссылку оффера — напр. https://site.com/promo?utm=fb    "
                "(Ctrl+V, любая раскладка)", big=True)
        self.url_entry.pack(fill="x")

        row = ctk.CTkFrame(s1, fg_color="transparent")
        row.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(row, text="Сколько ссылок", font=(FONT_FAMILY, 13),
                     text_color=COLOR_TEXT).pack(side="left")
        self.count_entry = self._num_entry(row, "50", 100)
        self.count_entry.pack(side="left", padx=(10, 24))
        ctk.CTkLabel(row, text="Режим", font=(FONT_FAMILY, 13),
                     text_color=COLOR_TEXT).pack(side="left")
        self.mode_var = ctk.StringVar(value="ready")
        self._seg(row, ["ready", "spintax"], self.mode_var, height=34).pack(
            side="left", padx=(10, 0))

        # ── Секция: свои параметры/макросы ──
        s2 = self._panel(page, "СВОИ ПАРАМЕТРЫ И МАКРОСЫ  ·  по желанию",
                         "метки и макросы мейлера, которые лягут в каждую ссылку",
                         icon="🏷")
        crow = ctk.CTkFrame(s2, fg_color="transparent")
        crow.pack(fill="x")
        self.custom_mode_var = ctk.StringVar(value="через &")
        self._seg(crow, ["через &", "как есть"], self.custom_mode_var,
                  height=32, width=170).pack(side="left", padx=(0, 10))
        # Плейсхолдер меняется под выбранный режим — чтобы прямо в поле было видно,
        # ЧТО и КАК вписывать, а не гадать. Дефолт — текст режима «через &».
        self.custom_params_entry = self._entry(crow, CUSTOM_PH_THROUGH, mono=True)
        self.custom_params_entry.pack(side="left", fill="x", expand=True)
        self.custom_params_entry.bind("<KeyRelease>", self._update_strength)
        # Клик по сегменту пишет в переменную → трейс обновит подсказку и при клике
        # пользователя, и при программной установке значения.
        self.custom_mode_var.trace_add("write", self._on_custom_mode_changed)

        # ── Секция: настройки уникализации ──
        s3 = self._panel(page, "НАСТРОЙКИ УНИКАЛИЗАЦИИ",
                         "обёртка · слои редиректов · диапазон параметров · ротация доменов",
                         icon="⚙")
        self.settings_section = s3

        r1 = ctk.CTkFrame(s3, fg_color="transparent")
        r1.pack(fill="x")
        ctk.CTkLabel(r1, text="Обёртка", font=(FONT_FAMILY, 12),
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self.wrapper_choice_var = ctk.StringVar(value="random")
        self.wrapper_menu = self._option(r1, WRAPPER_OPTIONS, self.wrapper_choice_var, 210)
        self.wrapper_menu.pack(side="left", padx=(8, 18))
        ctk.CTkLabel(r1, text="Слоёв", font=(FONT_FAMILY, 12),
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self.layers_var = ctk.StringVar(value=str(DEFAULT_LAYERS))
        self.layers_menu = self._option(r1, ["0", "1", "2"], self.layers_var, 68)
        self.layers_menu.pack(side="left", padx=(8, 18))
        ctk.CTkLabel(r1, text="Параметров от", font=(FONT_FAMILY, 12),
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self.params_min_entry = self._num_entry(r1, str(DEFAULT_PARAMS_MIN), 52)
        self.params_min_entry.pack(side="left", padx=(8, 6))
        self.params_min_entry.bind("<KeyRelease>", self._update_strength)
        ctk.CTkLabel(r1, text="до", font=(FONT_FAMILY, 12),
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self.params_max_entry = self._num_entry(r1, str(DEFAULT_PARAMS_MAX), 52)
        self.params_max_entry.pack(side="left", padx=(8, 0))
        self.params_max_entry.bind("<KeyRelease>", self._update_strength)

        self.btn_reset = ctk.CTkButton(
            r1, text="↺  Сброс", width=110, height=30, font=(FONT_FAMILY, 12, "bold"),
            fg_color=COLOR_ACCENT_SOFT, hover_color=COLOR_BTN_HVR, text_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT, border_width=1, corner_radius=8,
            command=self._reset_defaults)
        self.btn_reset.pack(side="right")

        r2 = ctk.CTkFrame(s3, fg_color="transparent")
        r2.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(r2, text="Домены", font=(FONT_FAMILY, 12),
                     text_color=COLOR_TEXT_DIM, width=64, anchor="w").pack(side="left")
        self.domains_entry = self._entry(
            r2, "Несколько доменов через запятую → письма пойдут с разных, "
                "напр. go.site.com, r.site.net    ·    пусто = домен из ссылки оффера",
            mono=True)
        self.domains_entry.pack(side="left", fill="x", expand=True)
        self.domains_entry.bind("<KeyRelease>", self._update_strength)

        # ── Кнопки действий ──
        act = ctk.CTkFrame(page, fg_color="transparent")
        act.pack(fill="x", padx=6, pady=(2, 2))
        self.btn_generate = ctk.CTkButton(
            act, text="⚡  СГЕНЕРИРОВАТЬ", height=46, width=250,
            font=(FONT_FAMILY, 15, "bold"), fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HVR, text_color="#0b1220", corner_radius=10,
            command=self._on_generate)
        self.btn_generate.pack(side="left", padx=(0, 10))
        for text, cmd in (("⧉  Копировать", self._on_copy),
                          ("⭳  Сохранить", self._on_save),
                          ("☁  Cloud HTML", self._on_cloud_html)):
            ctk.CTkButton(
                act, text=text, height=42, width=142, font=(FONT_FAMILY, 13),
                fg_color=COLOR_BTN, hover_color=COLOR_BTN_HVR, text_color=COLOR_TEXT,
                border_color=COLOR_BORDER2, border_width=1, corner_radius=8,
                command=cmd).pack(side="left", padx=(0, 10))

        # ── Секция: результат ──
        s4 = self._panel(page, "РЕЗУЛЬТАТ",
                         "сила рандомизации · готовые ссылки · листание и экспорт",
                         icon="📋")

        srow = ctk.CTkFrame(s4, fg_color="transparent")
        srow.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(srow, text="СИЛА РАНДОМИЗАЦИИ", font=(FONT_FAMILY, 11, "bold"),
                     text_color=COLOR_TEXT_DIM, width=170, anchor="w").pack(side="left")
        self.strength_bar = ctk.CTkProgressBar(
            srow, height=7, corner_radius=20, fg_color=COLOR_FIELD,
            border_color=COLOR_BORDER, border_width=1, progress_color=COLOR_ACCENT)
        self.strength_bar.pack(side="left", fill="x", expand=True, padx=(4, 12))
        self.strength_bar.set(0)
        self.strength_label = ctk.CTkLabel(
            srow, text="—", font=(FONT_MONO, 12, "bold"),
            text_color=COLOR_ACCENT, width=140, anchor="e")
        self.strength_label.pack(side="left")

        # Единственная строка статуса — компактная, без баннеров-«маркировок».
        self.status_label = ctk.CTkLabel(
            s4, text="", font=(FONT_MONO, 12), text_color=COLOR_TEXT_DIM, anchor="w")
        self.status_label.pack(fill="x", pady=(2, 8))

        # Текстбокс фикс-высоты со своим скроллом. Колесо над ним крутит ТОЛЬКО его.
        self.result_box = ctk.CTkTextbox(
            s4, height=RESULT_HEIGHT, font=(FONT_MONO, 12), fg_color=COLOR_FIELD,
            text_color=COLOR_TEXT, border_color=COLOR_BORDER2, border_width=1,
            corner_radius=8, wrap="none",
            scrollbar_button_color=COLOR_BORDER, scrollbar_button_hover_color=COLOR_BTN_HVR)
        self.result_box.pack(fill="x")
        self.result_box.bind("<MouseWheel>", self._result_wheel)
        self.result_box.bind("<Button-4>", self._result_wheel)
        self.result_box.bind("<Button-5>", self._result_wheel)
        # Горизонталь тачпадом: Windows отдаёт двухпальцевый горизонтальный жест как
        # <Shift-MouseWheel> — этот биндинг и есть рабочий путь на нашей платформе.
        self.result_box.bind("<Shift-MouseWheel>", self._result_wheel_x)
        # X11 шлёт горизонталь как Button-6/7 — на Windows Tk такого события нет и
        # bind падает TclError, поэтому вешаем опционально, не роняя окно.
        for seq in ("<Button-6>", "<Button-7>"):
            try:
                self.result_box.bind(seq, self._result_wheel_x)
            except Exception:
                pass

        # Панель пагинации — прямо под результатом (страница фикс-высоты, места хватает).
        self.page_bar = ctk.CTkFrame(s4, fg_color="transparent")

        def _pbtn(txt, cmd, w=44):
            return ctk.CTkButton(
                self.page_bar, text=txt, width=w, height=30, font=(FONT_FAMILY, 13),
                fg_color=COLOR_BTN, hover_color=COLOR_BTN_HVR, text_color=COLOR_TEXT,
                border_color=COLOR_BORDER2, border_width=1, corner_radius=6, command=cmd)

        self.btn_first = _pbtn("◀◀", self._page_first, w=48)
        self.btn_first.pack(side="left", padx=(0, 4))
        self.btn_prev = _pbtn("◀", self._page_prev)
        self.btn_prev.pack(side="left", padx=(0, 8))
        self.page_label = ctk.CTkLabel(
            self.page_bar, text="Стр. 1 / 1", font=(FONT_FAMILY, 12, "bold"),
            text_color=COLOR_TEXT, width=120)
        self.page_label.pack(side="left")
        self.btn_next = _pbtn("▶", self._page_next)
        self.btn_next.pack(side="left", padx=(8, 4))
        self.btn_last = _pbtn("▶▶", self._page_last, w=48)
        self.btn_last.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self.page_bar, text="перейти", font=(FONT_FAMILY, 12),
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self.goto_entry = self._num_entry(self.page_bar, "1", 60)
        self.goto_entry.pack(side="left", padx=(8, 4))
        self.goto_entry.bind("<Return>", self._page_goto)
        _pbtn("→", self._page_goto, w=36).pack(side="left")
        self.range_label = ctk.CTkLabel(
            self.page_bar, text="", font=(FONT_MONO, 11), text_color=COLOR_TEXT_DIM,
            anchor="e")
        self.range_label.pack(side="right")

    # ══════════════════════════════════════════════════════
    #  ХЕЛПЕРЫ UI
    # ══════════════════════════════════════════════════════

    def _panel(self, parent, title: str, sub: str = None, icon: str = None) -> ctk.CTkFrame:
        """Карточка-секция: вертикальный акцентный «таб» слева,
        (опц.) иконка-глиф, заголовок капсом и (опц.) mono-подпись. Возвращает
        внутренний фрейм."""
        outer = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=14,
                             border_color=COLOR_BORDER, border_width=1)
        outer.pack(fill="x", padx=6, pady=7)
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(15, 2))
        ctk.CTkFrame(head, width=4, height=16, fg_color=COLOR_ACCENT,
                     corner_radius=2).pack(side="left", pady=1)
        if icon:
            ctk.CTkLabel(head, text=icon, font=(FONT_FAMILY, 15),
                         text_color=COLOR_ACCENT, width=22).pack(side="left", padx=(9, 0))
        ctk.CTkLabel(head, text=title, font=(FONT_FAMILY, 12, "bold"),
                     text_color=COLOR_TEXT, anchor="w").pack(
            side="left", padx=(6 if icon else 11, 0))
        if sub:
            ctk.CTkLabel(outer, text=sub, font=(FONT_MONO, 10),
                         text_color=COLOR_TEXT_DIM2, anchor="w").pack(
                fill="x", padx=20, pady=(3, 0))
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(12, 17))
        return inner

    def _entry(self, parent, placeholder: str, big: bool = False,
               mono: bool = False) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent, height=46 if big else 34, placeholder_text=placeholder,
            font=((FONT_MONO if mono else FONT_FAMILY), 14 if big else 12),
            fg_color=COLOR_FIELD, text_color=COLOR_TEXT,
            placeholder_text_color=COLOR_TEXT_DIM2,
            border_color=COLOR_BORDER2, border_width=1, corner_radius=8)

    def _num_entry(self, parent, default: str, width: int) -> ctk.CTkEntry:
        e = ctk.CTkEntry(parent, height=32, width=width, font=(FONT_MONO, 12),
                         fg_color=COLOR_FIELD, text_color=COLOR_TEXT,
                         border_color=COLOR_BORDER2, border_width=1, corner_radius=8,
                         justify="center", validate="key", validatecommand=self._vcmd_int)
        e.insert(0, default)
        return e

    def _seg(self, parent, values, variable, height=32, width=None):
        kw = dict(values=values, variable=variable, font=(FONT_FAMILY, 12, "bold"),
                  height=height, fg_color=COLOR_FIELD, selected_color=COLOR_ACCENT,
                  selected_hover_color=COLOR_ACCENT_HVR, unselected_color=COLOR_PANEL2,
                  unselected_hover_color=COLOR_BTN_HVR, text_color=COLOR_TEXT,
                  corner_radius=8)
        if width:
            kw["width"] = width
        return ctk.CTkSegmentedButton(parent, **kw)

    def _option(self, parent, values, variable, width):
        return ctk.CTkOptionMenu(
            parent, values=values, variable=variable, width=width, height=32,
            font=(FONT_FAMILY, 12), fg_color=COLOR_FIELD, button_color=COLOR_PANEL2,
            button_hover_color=COLOR_BTN_HVR, text_color=COLOR_TEXT, corner_radius=8,
            dropdown_fg_color=COLOR_PANEL2, dropdown_hover_color=COLOR_ACCENT_SOFT,
            dropdown_text_color=COLOR_TEXT, command=self._update_strength)

    def _int(self, entry, default: int) -> int:
        try:
            return max(0, int(entry.get().strip()))
        except (ValueError, AttributeError):
            return default

    def _set_status(self, text: str, color: str = COLOR_TEXT_DIM) -> None:
        self.status_label.configure(text=text, text_color=color)
        # Живой индикатор в шапке — состояние по цвету статуса.
        state = {COLOR_WARN: "● генерация…", COLOR_ERROR: "● ошибка",
                 COLOR_ACCENT: "● готово"}.get(color, "● готов к работе")
        try:
            self.bridge_label.configure(text=state, text_color=color)
        except Exception:
            pass

    def _on_custom_mode_changed(self, *_):
        """Подсказка в поле своих параметров зависит от выбранного режима: «через &»
        — перечисление через запятую, «как есть» — дословный хвост в конец. Иначе
        формат приходилось бы угадывать."""
        ph = CUSTOM_PH_ASIS if self.custom_mode_var.get() == "как есть" else CUSTOM_PH_THROUGH
        try:
            self.custom_params_entry.configure(placeholder_text=ph)
        except Exception:
            pass

    def _result_wheel(self, event):
        """Колесо над результатом крутит ТОЛЬКО его, не всю страницу (return break
        останавливает bind_all прокрутки CTkScrollableFrame)."""
        try:
            if getattr(event, "num", None) == 4:
                delta = 1
            elif getattr(event, "num", None) == 5:
                delta = -1
            else:
                delta = int(event.delta / 120) or (1 if event.delta > 0 else -1)
            self.result_box._textbox.yview_scroll(-delta, "units")
        except Exception:
            pass
        return "break"

    def _result_wheel_x(self, event):
        """Горизонтальная прокрутка результата (тачпад/Shift+колесо). Как и вертикаль,
        крутит ТОЛЬКО результат и гасит всплытие к прокрутке страницы (return break)."""
        try:
            if getattr(event, "num", None) in (4, 6):
                delta = 1
            elif getattr(event, "num", None) in (5, 7):
                delta = -1
            else:
                delta = int(event.delta / 120) or (1 if event.delta > 0 else -1)
            self.result_box._textbox.xview_scroll(-delta, "units")
        except Exception:
            pass
        return "break"

    # ══════════════════════════════════════════════════════
    #  ФОКУС / ХОТКЕИ
    # ══════════════════════════════════════════════════════

    def _on_global_click(self, event):
        """Клик мимо инпута снимает с него фокус (как переход на другой инпут)."""
        try:
            cls = event.widget.winfo_class()
        except Exception:
            return
        if wants_defocus(cls):
            try:
                self.focus_set()
            except Exception:
                pass

    def _on_ctrl_key(self, event):
        intent = clipboard_intent(event.state, event.keycode, event.keysym)
        if intent is None:
            return
        w = event.widget
        try:
            if intent == "paste":
                w.event_generate("<<Paste>>")
            elif intent == "copy":
                w.event_generate("<<Copy>>")
            elif intent == "cut":
                w.event_generate("<<Cut>>")
            elif intent == "select_all":
                if w.winfo_class() in ("Text", "TText"):
                    w.tag_add("sel", "1.0", "end")
                else:
                    w.select_range(0, "end")
                    w.icursor("end")
        except Exception:
            pass
        return "break"

    # ══════════════════════════════════════════════════════
    #  СИЛА / СБРОС
    # ══════════════════════════════════════════════════════

    def _domains_count(self) -> int:
        dom = self.domains_entry.get().strip()
        if not dom:
            return 1
        return len([x for x in dom.split(",") if x.strip()]) or 1

    def _update_strength(self, *_) -> None:
        try:
            layers = int(self.layers_var.get())
            pct, label = randomization_strength(
                params_count_range=(self._int(self.params_min_entry, DEFAULT_PARAMS_MIN),
                                    self._int(self.params_max_entry, DEFAULT_PARAMS_MAX)),
                use_wrapper=layers > 0, wrapper_layers=layers,
                domains_count=self._domains_count(),
                has_custom=bool(self.custom_params_entry.get().strip()),
                **SAFE_TECHNIQUES,
            )
            self.strength_bar.set(pct / 100)
            color = COLOR_ACCENT if pct >= 70 else (COLOR_WARN if pct >= 40 else COLOR_ERROR)
            self.strength_bar.configure(progress_color=color)
            self.strength_label.configure(text=f"{label} · {pct}%", text_color=color)
        except Exception:
            pass

    def _reset_defaults(self) -> None:
        """Вернуть 4 контрола к безопасному дефолту (random / 1 слой / 5–8 /
        домены пусто). Свои макросы НЕ трогаем."""
        self.wrapper_choice_var.set("random")
        self.layers_var.set(str(DEFAULT_LAYERS))
        self.params_min_entry.delete(0, "end"); self.params_min_entry.insert(0, str(DEFAULT_PARAMS_MIN))
        self.params_max_entry.delete(0, "end"); self.params_max_entry.insert(0, str(DEFAULT_PARAMS_MAX))
        self.domains_entry.delete(0, "end")
        self._update_strength()
        self._set_status("Сброшено к дефолту: random · 1 слой · 5–8 параметров", COLOR_ACCENT)

    # ══════════════════════════════════════════════════════
    #  ГЕНЕРАЦИЯ (кооперативно кадрами — окно не лагает)
    # ══════════════════════════════════════════════════════

    def _gather_params(self) -> dict:
        layers = int(self.layers_var.get())
        params = dict(SAFE_TECHNIQUES)
        params["params_count_range"] = (
            self._int(self.params_min_entry, DEFAULT_PARAMS_MIN),
            self._int(self.params_max_entry, DEFAULT_PARAMS_MAX),
        )
        params["use_wrapper"] = layers > 0
        params["wrapper_layers"] = layers
        wc = self.wrapper_choice_var.get()
        params["wrapper_name"] = None if wc == "random" else wc

        cp = self.custom_params_entry.get().strip()
        if cp:
            if self.custom_mode_var.get() == "как есть":
                params["custom_tail"] = cp
            else:
                params["custom_params"] = [x.strip() for x in cp.split(",") if x.strip()]

        dom = self.domains_entry.get().strip()
        if dom:
            params["domains"] = [x.strip() for x in dom.split(",") if x.strip()]
        return params

    def _url_from_entry(self) -> str:
        url = self.url_entry.get().strip()
        if url and not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def _on_generate(self) -> None:
        if self._generating:
            return
        url = self._url_from_entry()
        if not url:
            self._set_status("Введи ссылку оффера!", COLOR_ERROR)
            self.url_entry.focus_set()
            return

        mode = self.mode_var.get()
        params = self._gather_params()
        one_domain = self._domains_count() < 2 and int(self.layers_var.get()) == 0

        count = clamp_count(self._int(self.count_entry, 50))
        if mode == "spintax":
            count = min(count, MAX_SPINTAX)
        self._start_generation(url, params, count, mode, one_domain)

    def _start_generation(self, url, params, count, mode, one_domain) -> None:
        self._generating = True
        self._gen_cancel = False
        self.btn_generate.configure(text="■  СТОП", fg_color=COLOR_ERROR,
                                    hover_color="#d13b40", text_color="#0b1220",
                                    command=self._cancel_generation)
        self._set_status(f"Генерация 0 / {count:,}", COLOR_WARN)
        # Крупный объём → в ОТДЕЛЬНЫЙ ПРОЦЕСС (UI-поток свободен, окно не лагает при
        # скролле). Если процесс не поднялся — откат на кооперативную генерацию в
        # этом же потоке. Мелкий объём и так мгновенный — делаем на месте.
        if count >= _MP_THRESHOLD:
            try:
                self._start_generation_mp(url, params, count, mode, one_domain)
                return
            except Exception:
                self._mp = None   # процесс не стартовал — идём фолбэком
        self._start_generation_inproc(url, params, count, mode, one_domain)

    # ── путь 1: генерация в отдельном процессе (без лагов UI) ──

    def _start_generation_mp(self, url, params, count, mode, one_domain) -> None:
        q = mp.Queue()
        stop = mp.Event()
        proc = mp.Process(target=generate_worker,
                          args=(url, params, count, q, stop), daemon=True)
        proc.start()   # бросит исключение при неудаче старта → фолбэк в _start_generation
        self._mp = dict(q=q, stop=stop, proc=proc, target=count, mode=mode,
                        one_domain=one_domain, links=[], attempts=0)
        self.after(_MP_POLL_MS, self._mp_drain)

    def _mp_drain(self) -> None:
        """UI-сторона: дёшево переливает готовые батчи из очереди процесса. Вся
        тяжёлая работа — в процессе, поэтому этот метод почти мгновенный и окно
        остаётся отзывчивым/плавным при скролле."""
        if not self._generating or not self._mp:
            return
        m = self._mp
        done = False
        try:
            while True:
                item = m["q"].get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__done__":
                    m["attempts"] = item[1]
                    done = True
                    break
                m["links"].extend(item)
        except queue.Empty:
            pass
        if done:
            self._finish_generation_mp(cancelled=self._gen_cancel)
            return
        got = len(m["links"])
        self._set_status(
            f"Генерация {got * 100 // max(1, m['target'])}%  ·  {got:,} / {m['target']:,}  "
            "(окно отзывчиво, можно «СТОП»)", COLOR_WARN)
        self.after(_MP_POLL_MS, self._mp_drain)

    def _finish_generation_mp(self, cancelled: bool) -> None:
        m = self._mp
        self._mp = None
        self._generating = False
        proc = m.get("proc")
        try:
            if proc is not None:
                proc.join(timeout=1.0)
                if proc.is_alive():
                    proc.terminate()
        except Exception:
            pass
        links = m["links"]
        dups = max(0, m["attempts"] - len(links))
        self._restore_generate_button()
        if m["mode"] == "spintax":
            result = "{" + "|".join(links) + "}"
            self._show_spintax(result, len(links), dups, m["target"])
        else:
            self._set_links(links, m["target"], dups, m["one_domain"])
        if cancelled:
            self._set_status(f"Прервано — готово {len(links):,} ссылок (весь набор доступен)",
                             COLOR_WARN)

    # ── путь 2 (фолбэк / мелкий объём): кооперативная генерация кадрами ──

    def _start_generation_inproc(self, url, params, count, mode, one_domain) -> None:
        self._gen = dict(url=url, params=params, target=count, mode=mode,
                         one_domain=one_domain, seen=set(), links=[],
                         attempts=0, max_attempts=count * 6 + 100)
        self.after(1, self._gen_step)

    def _cancel_generation(self) -> None:
        self._gen_cancel = True
        # Процессу шлём событие остановки; он до-флашит батч и пришлёт "__done__".
        if self._mp:
            try:
                self._mp["stop"].set()
            except Exception:
                pass

    def _gen_step(self) -> None:
        if not self._generating:
            return
        g = self._gen
        try:
            if self._gen_cancel:
                self._finish_generation(cancelled=True)
                return
            url, params, target = g["url"], g["params"], g["target"]
            seen, links = g["seen"], g["links"]
            max_attempts = g["max_attempts"]
            deadline = time.perf_counter() + _GEN_FRAME_BUDGET
            n = 0
            while len(links) < target and g["attempts"] < max_attempts:
                link = uniquify_url(url, "ready", **params)
                g["attempts"] += 1
                h = hash(link)
                if h not in seen:
                    seen.add(h)
                    links.append(link)
                n += 1
                # Проверяем дедлайн каждые 64 итерации (perf_counter дешёвый).
                if (n & 0x3F) == 0 and time.perf_counter() >= deadline:
                    break
            if len(links) < target and g["attempts"] < max_attempts:
                done = len(links)
                self._set_status(
                    f"Генерация {done * 100 // target}%  ·  {done:,} / {target:,}  "
                    "(окно отзывчиво, можно «СТОП»)", COLOR_WARN)
                self.after(1, self._gen_step)
            else:
                self._finish_generation(cancelled=False)
        except Exception as e:
            self._generating = False
            self._restore_generate_button()
            self._show_error(str(e))

    def _restore_generate_button(self) -> None:
        self.btn_generate.configure(text="⚡  СГЕНЕРИРОВАТЬ", fg_color=COLOR_ACCENT,
                                    hover_color=COLOR_ACCENT_HVR, text_color="#0b1220",
                                    command=self._on_generate)

    def _finish_generation(self, cancelled: bool) -> None:
        g = self._gen
        self._generating = False
        links = g["links"]
        dups = g["attempts"] - len(links)
        self._restore_generate_button()
        if g["mode"] == "spintax":
            result = "{" + "|".join(links) + "}"
            self._show_spintax(result, len(links), dups, g["target"])
        else:
            self._set_links(links, g["target"], dups, g["one_domain"])
        if cancelled:
            self._set_status(f"Прервано — готово {len(links):,} ссылок (весь набор доступен)",
                             COLOR_WARN)

    # ── отображение / пагинация ──

    def _set_links(self, links, requested, dups, one_domain) -> None:
        self.links = links
        self.spintax_text = None
        self.page = 0
        self._set_pagination_visible(True)
        self._render_page()
        self._restore_generate_button()
        n = len(links)
        self._set_status(f"{n:,} уникальных · {dups:,} дублей", COLOR_ACCENT)

    def _render_page(self) -> None:
        """Показывает ТОЛЬКО текущую страницу набора в текстбоксе."""
        start, end, total_pages, self.page = page_bounds(len(self.links), PAGE_SIZE, self.page)
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", "\n".join(self.links[start:end]))
        self.result_box.yview_moveto(0)
        self.page_label.configure(text=f"Стр. {self.page + 1} / {total_pages}")
        shown = f"{start + 1:,}–{end:,}" if self.links else "0"
        self.range_label.configure(text=f"показано {shown} из {len(self.links):,}  ")
        first = self.page > 0
        last = self.page < total_pages - 1
        self.btn_first.configure(state="normal" if first else "disabled")
        self.btn_prev.configure(state="normal" if first else "disabled")
        self.btn_next.configure(state="normal" if last else "disabled")
        self.btn_last.configure(state="normal" if last else "disabled")

    def _set_pagination_visible(self, visible: bool) -> None:
        # Результат — фикс-высоты (не expand), поэтому панель просто пакуется под ним
        # и всегда видна; страница при нехватке места скроллится целиком.
        if visible:
            if not self.page_bar.winfo_manager():
                self.page_bar.pack(fill="x", pady=(10, 0))
        else:
            self.page_bar.pack_forget()

    def _goto_page(self, page: int) -> None:
        if not self.links:
            return
        self.page = page
        self._render_page()

    def _page_first(self):
        self._goto_page(0)

    def _page_prev(self):
        self._goto_page(self.page - 1)

    def _page_next(self):
        self._goto_page(self.page + 1)

    def _page_last(self):
        _, _, total_pages, _ = page_bounds(len(self.links), PAGE_SIZE, 0)
        self._goto_page(total_pages - 1)

    def _page_goto(self, *_):
        try:
            n = int(self.goto_entry.get().strip())
        except (ValueError, AttributeError):
            return
        self._goto_page(n - 1)

    def _show_spintax(self, result, count, dups, requested) -> None:
        self.links = []
        self.spintax_text = result
        self._set_pagination_visible(False)
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", result)
        self._restore_generate_button()
        self._set_status(f"спинтакс · {count:,} вариантов · {dups:,} дублей", COLOR_ACCENT)

    def _all_text(self) -> str:
        """Полный результат для копирования/сохранения — ВЕСЬ набор, не только страница."""
        if self.spintax_text is not None:
            return self.spintax_text
        if self.links:
            return "\n".join(self.links)
        return self.result_box.get("1.0", "end-1c").strip()

    def _show_error(self, err):
        self._set_pagination_visible(False)
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", f"ОШИБКА: {err}")
        self._restore_generate_button()
        self._set_status(f"Ошибка: {err}", COLOR_ERROR)

    # ══════════════════════════════════════════════════════
    #  КОПИРОВАТЬ / СОХРАНИТЬ / CLOUD
    # ══════════════════════════════════════════════════════

    def _on_copy(self):
        text = self._all_text()
        if not text:
            self._set_status("Нечего копировать — сначала сгенерируй", COLOR_WARN)
            return
        self._set_status("Копирование...", COLOR_WARN)
        self.update_idletasks()
        self.clipboard_clear()
        self.clipboard_append(text)
        n = len(self.links) if self.links else (text.count("\n") + 1)
        self._set_status(f"Скопировано в буфер: {n:,} строк (весь набор)", COLOR_ACCENT)

    def _on_save(self):
        text = self._all_text()
        if not text:
            self._set_status("Нечего сохранять — сначала сгенерируй", COLOR_WARN)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="unique_links.txt")
        if path:
            try:
                if self.links:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("\n".join(self.links))
                    n = len(self.links)
                else:
                    Path(path).write_text(text, encoding="utf-8")
                    n = text.count("\n") + 1
                self._set_status(f"Сохранено {n:,} строк: {Path(path).name}", COLOR_ACCENT)
            except Exception as e:
                self._set_status(f"Ошибка сохранения: {e}", COLOR_ERROR)

    def _on_cloud_html(self):
        url = self._url_from_entry()
        if not url:
            self._set_status("Введи ссылку оффера для Cloud HTML", COLOR_ERROR)
            return
        try:
            html = generate_cloud_redirect_page(url)
            self.links = []
            self.spintax_text = None
            self._set_pagination_visible(False)
            self.result_box.delete("1.0", "end")
            self.result_box.insert("1.0", html)
            self._set_status("Cloud HTML готов — залей на облако и шли ссылку на него", COLOR_ACCENT)
        except Exception as e:
            self._set_status(f"Ошибка Cloud HTML: {e}", COLOR_ERROR)


# ═══════════════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════════════

def main(app_factory=LinkUniquifierApp) -> None:
    """Запуск окна. Ctrl+C (KeyboardInterrupt) гасим — это НЕ краш, а штатная
    остановка mainloop; окно корректно закрывается."""
    app = app_factory()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        # Ctrl+C, прилетевший ПРЯМО в mainloop (не в колбэк).
        print("\nЗакрыто (Ctrl+C).")
    else:
        # Ctrl+C, пойманный внутри after-колбэка → mainloop вышел штатно через quit().
        if getattr(app, "_interrupted", False):
            print("\nЗакрыто (Ctrl+C).")
    finally:
        try:
            app.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    # freeze_support — чтобы дочерний процесс генерации корректно поднимался при
    # spawn на Windows (и в замороженном .exe), а не пытался заново открыть окно.
    mp.freeze_support()
    main()
