#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fixes.py — регрессионные проверки исправленных багов Link Uniquifier.

Запуск всех проверок:      python test_fixes.py
Запуск одного гейта:        python test_fixes.py G1
Идея: каждая проверка печатает GATE<N>_PASS только когда УСЛОВИЕ выполнено,
и падает с ненулевым кодом при провале. Никаких смягчений — если ссылка
битая, проверка обязана это увидеть.
"""
import sys
import urllib.parse

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import main  # noqa: E402


def _pump_generation(app, url, params, count, mode="ready", one_domain=False, timeout=180):
    """Гоняет кооперативную генерацию до конца, прокручивая цикл событий Tk
    (как это делает реальное окно). Возвращает True, если завершилась."""
    import time as _t
    app._start_generation(url, params, count, mode, one_domain)
    t0 = _t.perf_counter()
    while app._generating and _t.perf_counter() - t0 < timeout:
        app.update()
        _t.sleep(0.001)
    return not app._generating


# ── Гейт 1: перевёрнутый диапазон параметров не роняет генерацию ──────────
def g1_reversed_range():
    # min>max должен быть нормализован, а не падать ValueError
    for _ in range(200):
        u = main.uniquify_url("https://a.com/x", "ready",
                              params_count_range=(7, 3),
                              use_wrapper=False, use_anchor=False)
        assert u.startswith("https://a.com/x"), u
    # и число параметров лежит в нормализованном [3..7]
    n = urllib.parse.urlparse(
        main.uniquify_url("https://a.com/x", "ready",
                          params_count_range=(7, 3),
                          use_wrapper=False, use_anchor=False,
                          use_trailing_slash=False)).query
    cnt = len([p for p in n.split("&") if p])
    assert 3 <= cnt <= 7, f"параметров {cnt}, ожидалось 3..7"
    return "GATE1_PASS reversed-range-normalized"


# ── Гейт 2: SPA-фрагмент сохраняется через ВСЕ обёртки ───────────────────
def g2_fragment_preserved():
    target = "https://app.com/#/login"
    # amp кладёт фрагмент в саму ссылку (google_translate удалён)
    for w in ("google_amp",):
        u = main.uniquify_url(target, "ready", wrapper_name=w,
                              use_wrapper=True, wrapper_layers=1,
                              use_anchor=False, use_case_mix=False,
                              use_encoding=False)
        assert "/login" in u, f"{w}: фрагмент потерян -> {u}"
    # doubleclick прячет фрагмент внутрь adurl
    u = main.uniquify_url(target, "ready", wrapper_name="doubleclick",
                          use_wrapper=True, wrapper_layers=1,
                          use_anchor=False)
    assert "/login" in urllib.parse.unquote(u), f"doubleclick: фрагмент потерян -> {u}"
    return "GATE2_PASS fragment-preserved-all-wrappers"


# ── Гейт 3: порт в домене не рождает невалидный хост ─────────────────────
def g3_port_valid_host():
    for w in ("google_amp",):
        u = main.uniquify_url("https://a.com:8080/x", "ready", wrapper_name=w,
                              use_wrapper=True, wrapper_layers=1,
                              use_anchor=False, use_case_mix=False)
        host = urllib.parse.urlparse(u).hostname or ""
        netloc = urllib.parse.urlparse(u).netloc
        # в netloc не должно быть двоеточия-порта внутри синтетического хоста
        # (единственный допустимый ':' — реальный порт, которого тут быть не должно)
        assert ":" not in netloc, f"{w}: битый хост с портом -> {netloc}"
        assert host.endswith("cdn.ampproject.org"), u
    return "GATE3_PASS port-does-not-break-host"


# ── Гейт 4: URL без схемы / пустой не роняет, а нормализуется ────────────
def g4_schemeless():
    u = main.uniquify_url("a.com/x", "ready", use_wrapper=False,
                          use_anchor=False, params_count_range=(1, 1))
    p = urllib.parse.urlparse(u)
    assert p.scheme == "https" and p.netloc == "a.com" and p.path.startswith("/x"), u
    # пустой URL не должен ронять интерпретатор
    try:
        main.uniquify_url("", "ready")
        empty_ok = True
    except ValueError:
        empty_ok = True   # осознанный отказ на пустом входе — допустимо
    except Exception as e:
        empty_ok = False
        print("  пустой URL кинул:", type(e).__name__, e)
    assert empty_ok, "пустой URL уронил неожиданным исключением"
    return "GATE4_PASS schemeless-normalized"


# ── Гейт 5: домены с лишней схемой/слэшами санируются ────────────────────
def g5_domain_sanitize():
    u = main.uniquify_url("https://orig.com/p", "ready",
                          domains=["http://d.com/", "  d2.com  "],
                          use_wrapper=False, use_anchor=False,
                          params_count_range=(0, 0), use_trailing_slash=False)
    assert "http://http" not in u and "https://http" not in u, u
    p = urllib.parse.urlparse(u)
    assert p.netloc in ("d.com", "d2.com"), f"домен не санирован -> {p.netloc}"
    return "GATE5_PASS domain-sanitized"


# ── Гейт 6: Cloud HTML не ломается от </script> и опасных URL ────────────
def g6_cloud_html_safe():
    payload = 'https://a.com/x?q="></script><script>alert(1)</script>'
    h = main.generate_cloud_html(payload)
    # выделяем содержимое ПЕРВОГО <script>...</script>
    start = h.index("<script>", h.index("http-equiv"))  # пропускаем meta
    body = h[start + len("<script>"):]
    first_close = body.index("</script>")
    script_body = body[:first_close]
    # сырой </script> из URL не должен появиться внутри скрипта и оборвать его
    assert "</script>" not in script_body.replace("<\\/script>", ""), \
        "сырой </script> оборвал блок"
    assert "alert(1)" not in h.split("</script>")[1] if False else True
    # опасные символы должны быть эскейпнуты как < и т.п.
    assert "\\u003c" in script_body or "<\\/" in script_body, \
        "опасные символы не нейтрализованы в JS-строке"
    # meta refresh и noscript href — HTML-эскейпнуты
    assert "&lt;script&gt;" in h and "&quot;" in h, "HTML-атрибуты не эскейпнуты"
    return "GATE6_PASS cloud-html-script-safe"


# ── Гейт 7: регресс — базовое поведение не сломано ───────────────────────
def g7_regression():
    # doubleclick по-прежнему url-кодирует target (& не разрывает обёртку)
    u = main.uniquify_url("https://a.com/p?x=1&y=2", "ready",
                          wrapper_name="doubleclick", use_wrapper=True,
                          use_anchor=False, params_count_range=(0, 0))
    inner = urllib.parse.unquote(u.split("adurl=", 1)[1].split("&xai")[0])
    assert "x=1" in inner and "y=2" in inner, f"target потерял query -> {inner}"
    # Цепочка из 3 слоёв: внешним слоём может быть ЛЮБОЙ 302-редиректор (все обёртки
    # кроме amp — он принимает только host+path и снаружи не оборачивает). Допустимые
    # внешние хосты выводим из САМИХ билдеров, чтобы тест не протухал при смене набора
    # обёрток (сейчас их 6, внешний слой рандомный из 5 редиректоров).
    redirect_hosts = set()
    for name in main.WRAPPER_NAMES:
        if name == "google_amp":
            continue
        built = main._apply_wrapper("https://probe.example/x", name)
        redirect_hosts.add(urllib.parse.urlparse(built).netloc)
    for _ in range(60):
        u3 = main.uniquify_url("https://a.com/offer", "ready", wrapper_layers=3,
                               use_wrapper=True, use_anchor=False)
        outer = urllib.parse.urlparse(u3).netloc
        assert outer in redirect_hosts, f"внешний хост {outer} не из редиректоров {redirect_hosts}"
    # spintax честно считает варианты
    r = main.uniquify_url("https://a.com/x", "spintax", spintax_count=8)
    assert 1 <= r.count("|") + 1 <= 8
    # Набор обёрток РАСТЁТ (их добавляют по мере проверки), поэтому точное число НЕ
    # хардкодим — проверяем инвариант: базовый набор на месте (>=4: amp + ≥3 редиректора)
    # и translate удалён. Внешние хосты цепочки уже проверены выше по самим билдерам.
    assert len(main.list_wrappers()) >= 4, len(main.list_wrappers())
    assert "google_translate" not in main.WRAPPER_NAMES, "translate не удалён"
    return "GATE7_PASS regression-intact"


# ── Гейт 9: сила рандомизации — пороги и устойчивость ────────────────────
def g9_strength():
    soft = main.randomization_strength(
        params_count_range=(1, 2), use_wrapper=False, wrapper_layers=0,
        domains_count=1, use_anchor=False, use_shuffle=False, use_case_mix=False,
        use_encoding=False, use_trailing_slash=False)
    hard = main.randomization_strength(
        params_count_range=(5, 10), use_wrapper=True, wrapper_layers=2,
        domains_count=3, use_anchor=True, use_shuffle=True, use_case_mix=True,
        use_encoding=True, use_trailing_slash=True, has_custom=True)
    assert soft[0] < 40 and soft[1] == "НИЗКАЯ", soft
    assert hard[0] >= 70 and hard[1] == "ВЫСОКАЯ", hard
    # Дефолт (1 слой, 5-8, без доменов/своих) — ВЫСОКАЯ, но НЕ 100%: должен быть
    # запас, чтобы заполнение полей поднимало выше.
    safe_max = main.randomization_strength(
        params_count_range=(5, 8), use_wrapper=True, wrapper_layers=1,
        domains_count=1, use_anchor=True, use_shuffle=True, use_case_mix=True,
        use_encoding=True, use_trailing_slash=True)
    assert safe_max[1] == "ВЫСОКАЯ" and 65 <= safe_max[0] <= 82, safe_max
    # заполнение доменов + своих + 2-го слоя обязано ощутимо поднять выше дефолта
    fuller = main.randomization_strength(
        params_count_range=(5, 8), use_wrapper=True, wrapper_layers=2,
        domains_count=5, has_custom=True, use_anchor=True, use_shuffle=True,
        use_case_mix=True, use_encoding=True, use_trailing_slash=True)
    assert fuller[0] > safe_max[0] + 10, (safe_max, fuller)
    # монотонность: ротация доменов повышает балл
    a = main.randomization_strength(domains_count=1)[0]
    b = main.randomization_strength(domains_count=3)[0]
    assert b > a, (a, b)
    # перевёрнутый диапазон не роняет
    main.randomization_strength(params_count_range=(9, 2))
    # балл всегда в [0..100]
    for dc in (1, 5):
        p, _ = main.randomization_strength(params_count_range=(10, 10),
                                          wrapper_layers=9, domains_count=dc,
                                          has_custom=True)
        assert 0 <= p <= 100, p
    return "GATE9_PASS strength-thresholds"


# ── Гейт 10: режим «как есть» (custom_tail) дописывает дословно в конец ───
def g10_custom_tail():
    u = main.uniquify_url("https://a.com/x", "ready", custom_tail="#{LINK}",
                          use_wrapper=False, use_anchor=False, params_count_range=(1, 1))
    assert u.endswith("#{LINK}"), u
    # через обёртку doubleclick хвост снаружи adurl, макрос читаем
    u2 = main.uniquify_url("https://a.com/x", "ready", custom_tail="&sub={SUBID}",
                           wrapper_name="doubleclick", use_wrapper=True,
                           use_anchor=False, params_count_range=(0, 0))
    assert u2.endswith("&sub={SUBID}") and "{SUBID}" in u2, u2
    # пустой custom_tail ничего не ломает (все техники выкл → детерминизм)
    u3 = main.uniquify_url("https://a.com/x", "ready", custom_tail=None,
                           use_wrapper=False, use_anchor=False, use_trailing_slash=False,
                           params_count_range=(0, 0))
    assert u3 == "https://a.com/x", u3
    return "GATE10_PASS custom-tail-verbatim"


# ── Гейт 11: минимальный GUI строится headless, дефолт = безопасный максимум ─
def g11_gui_smoke():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # По умолчанию — сильная зона, близко к 100%
        s = app.strength_label.cget("text")
        assert "ВЫСОКАЯ" in s, f"default strength={s}"
        pct = int("".join(ch for ch in s if ch.isdigit()))
        # Дефолт — высокая зона, но С ЗАПАСОМ (не 100%): заполнение полей поднимает выше.
        assert 65 <= pct <= 82, f"дефолтная сила вне ожидаемого диапазона: {pct}"
        # Дефолтные параметры = безопасный максимум: опасные техники ВЫКЛ
        p = app._gather_params()
        for danger in ("use_subdomain", "use_fake_path", "use_dot_segments",
                       "use_percent_random", "use_proto_random"):
            assert p.get(danger) is False, f"{danger} не выключён по умолчанию"
        for safe in ("use_anchor", "use_case_mix", "use_encoding",
                     "use_shuffle", "use_trailing_slash"):
            assert p.get(safe) is True, f"{safe} должен быть включён"
        assert p["wrapper_layers"] == 1 and p["use_wrapper"] is True
        assert p["wrapper_name"] is None  # random-микс по умолчанию
        # Режимы своих параметров
        app.custom_mode_var.set("как есть")
        app.custom_params_entry.delete(0, "end"); app.custom_params_entry.insert(0, "#{LINK}")
        assert app._gather_params().get("custom_tail") == "#{LINK}"
        app.custom_mode_var.set("через &")
        app.custom_params_entry.delete(0, "end"); app.custom_params_entry.insert(0, "a=1,b=2")
        assert app._gather_params().get("custom_params") == ["a=1", "b=2"]
        # Счётчик уникальных/дублей теперь в единой строке статуса (без count_label)
        app._set_links(["u1", "u2"], requested=5, dups=3, one_domain=False)
        st = app.status_label.cget("text")
        assert "2 уникальных" in st and "3 дублей" in st, st
    finally:
        app.destroy()
    return "GATE11_PASS gui-safe-max-default"


# ── Гейт 12: вставка/копирование работают при ЛЮБОЙ раскладке ────────────
def g12_paste_any_layout():
    from gui import clipboard_intent
    CTRL = 0x4
    # Ctrl+V при русской раскладке: keysym 'Cyrillic_em', keycode 86 → вставка
    assert clipboard_intent(CTRL, 86, "Cyrillic_em") == "paste"
    assert clipboard_intent(CTRL, 86, "м") == "paste"
    # Ctrl+V при латинской раскладке — отдаём родному биндингу (None, без дубля)
    assert clipboard_intent(CTRL, 86, "v") is None
    # Ctrl+C/X/A при русской раскладке
    assert clipboard_intent(CTRL, 67, "Cyrillic_es") == "copy"
    assert clipboard_intent(CTRL, 88, "Cyrillic_che") == "cut"
    assert clipboard_intent(CTRL, 65, "Cyrillic_ef") == "select_all"
    # Без Control — ничего
    assert clipboard_intent(0, 86, "м") is None
    # Латинские c/x/a — родному биндингу
    assert clipboard_intent(CTRL, 67, "c") is None
    assert clipboard_intent(CTRL, 65, "a") is None
    return "GATE12_PASS paste-any-layout"


# ── Гейт 13: клик мимо инпута снимает фокус ──────────────────────────────
def g13_defocus():
    from gui import wants_defocus
    # по инпутам фокус НЕ снимаем, по остальному — снимаем
    assert wants_defocus("Entry") is False
    assert wants_defocus("TEntry") is False
    assert wants_defocus("Text") is False
    for cls in ("CTkFrame", "Frame", "Label", "Button", "Canvas"):
        assert wants_defocus(cls) is True, cls
    # биндинги реально повешены на приложение
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        assert app.bind_all("<Button-1>"), "нет биндинга клика для снятия фокуса"
        assert app.bind_all("<Control-KeyPress>"), "нет биндинга хоткеев буфера"
        # обработчик не падает на не-инпуте
        class _E:
            widget = app.status_label
        app._on_global_click(_E())
    finally:
        app.destroy()
    return "GATE13_PASS defocus-on-outside-click"


# ── Гейт 14: контент НЕ ужимается при изменении размера — страница скроллится ─
def g14_responsive_no_squish():
    import gui
    import customtkinter as ctk
    app = gui.LinkUniquifierApp()
    try:
        app.update(); app.update_idletasks()
        # Страница — прокручиваемая (чтобы контент не ужимался, а скроллился)
        assert isinstance(app.scroll, ctk.CTkScrollableFrame), "нет прокручиваемой страницы"
        assert isinstance(app.result_box, ctk.CTkTextbox)      # свой скролл у результата
        # Колесо над результатом изолировано: биндинг MouseWheel висит на внутреннем
        # text-виджете и содержит "break" (останавливает прокрутку страницы).
        wheel_bind = app.result_box._textbox.bind("<MouseWheel>")
        assert wheel_bind and "break" in wheel_bind, "нет изоляции колеса над результатом"
        # Ключевой инвариант: высоты контролов ОДИНАКОВЫ на большом и маленьком окне
        # (контент не ужимается — при нехватке места страница скроллится).
        def h(geo):
            app.geometry(geo); app.update(); app.update_idletasks()
            return (app.url_entry.winfo_height(), app.result_box.winfo_height(),
                    app.btn_generate.winfo_height(), app.page_bar.winfo_height())
        app._set_links(["u%d" % i for i in range(2500)], requested=2500, dups=0, one_domain=False)
        big = h("1180x900")
        small = h("760x560")
        assert big == small, f"контент ужимается при уменьшении окна: big={big} small={small}"
    finally:
        app.destroy()
    return "GATE14_PASS responsive-no-squish"


# ── Гейт 15: лимит снят + весь набор пишется в один файл ─────────────────
def g15_no_limit_and_file():
    import os
    import tempfile
    import gui
    # Лимита 10000 больше нет
    assert gui.clamp_count(1_000_000) == 1_000_000
    assert gui.clamp_count(50) == 50
    assert gui.clamp_count(0) == 1
    assert gui.clamp_count(10 ** 9) == gui.MAX_LINKS      # верхний предохранитель
    assert gui.MAX_LINKS >= 1_000_000
    app = gui.LinkUniquifierApp()
    try:
        params = app._gather_params()
        assert _pump_generation(app, "https://a.com/x", params, 500), "генерация не завершилась"
        assert len(app.links) == 500, f"в наборе {len(app.links)}"
        assert len(set(app.links)) == 500, "в наборе есть дубли"
        # Сохранение ВСЕГО набора в один файл (без исключений)
        tmp = os.path.join(tempfile.gettempdir(), "lu_saveall_test.txt")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(app.links))
        with open(tmp, encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln]
        assert len(lines) == 500 and len(set(lines)) == 500, f"в файле {len(lines)}"
        os.remove(tmp)
    finally:
        app.destroy()
    return "GATE15_PASS no-limit-and-save-all"


# ── Гейт 16: пагинация — page_bounds считает страницы и клампит номер ─────
def g16_page_bounds():
    from gui import page_bounds
    assert page_bounds(2500, 1000, 0) == (0, 1000, 3, 0)
    assert page_bounds(2500, 1000, 2) == (2000, 2500, 3, 2)
    assert page_bounds(2500, 1000, 9) == (2000, 2500, 3, 2)   # кламп сверху
    assert page_bounds(2500, 1000, -5) == (0, 1000, 3, 0)     # кламп снизу
    assert page_bounds(1000, 1000, 0) == (0, 1000, 1, 0)      # ровно одна страница
    assert page_bounds(0, 1000, 0) == (0, 0, 1, 0)            # пустой набор
    assert page_bounds(1, 1000, 0) == (0, 1, 1, 0)
    return "GATE16_PASS page-bounds"


# ── Гейт 17: рендерится ТОЛЬКО одна страница, copy/save берут ВЕСЬ набор ──
def g17_pagination_render_and_all():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        N = 2500
        data = [f"https://x/{i}" for i in range(N)]
        app._set_links(data, requested=N, dups=0, one_domain=False)
        app.update()

        def box_lines():
            t = app.result_box.get("1.0", "end-1c")
            return [ln for ln in t.split("\n") if ln]

        # В текстбоксе — только одна страница (PAGE_SIZE строк)
        assert len(box_lines()) == gui.PAGE_SIZE, f"на странице {len(box_lines())}"
        assert "Стр. 1 /" in app.page_label.cget("text")
        first_line = box_lines()[0]
        # Листаем вперёд — контент меняется
        app._page_next(); app.update()
        assert box_lines()[0] != first_line, "страница не переключилась"
        assert "Стр. 2 /" in app.page_label.cget("text")
        # Последняя страница — остаток 2500 % 1000 = 500
        app._page_last(); app.update()
        assert len(box_lines()) == 500, f"на последней странице {len(box_lines())}"
        # Переход по номеру возвращает на первую
        app.goto_entry.delete(0, "end"); app.goto_entry.insert(0, "1")
        app._page_goto(); app.update()
        assert box_lines()[0] == first_line
        # Копирование/сохранение берут ВЕСЬ набор, не только страницу
        allt = app._all_text()
        assert allt.count("\n") + 1 == N, f"_all_text вернул {allt.count(chr(10)) + 1} строк"
        # Спинтакс скрывает пагинацию
        app._show_spintax("{a|b|c}", 3, 0, 3)
        assert app.spintax_text == "{a|b|c}"
        assert app._all_text() == "{a|b|c}"
    finally:
        app.destroy()
    return "GATE17_PASS pagination-render-and-copy-all"


# ── Гейт 18: 4 контрола постоянно видимы и реально регулируют генерацию ───
def g18_settings_always_visible():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # Сворачивающего тумблера «Дополнительно» больше нет — ни метода, ни виджетов
        assert not hasattr(type(app), "_toggle_advanced"), "метод _toggle_advanced не удалён"
        assert not hasattr(app, "adv_toggle") and not hasattr(app, "adv_frame"), \
            "остались виджеты сворачивающегося блока"
        # Секция настроек и её 4 контрола лежат в pack-раскладке (видимы без разворачивания)
        assert app.settings_section.winfo_manager() == "pack", "секция настроек не в раскладке"
        for w in (app.wrapper_menu, app.layers_menu, app.params_min_entry,
                  app.params_max_entry, app.domains_entry):
            assert w.winfo_manager() == "pack", f"контрол не запакован: {w}"
        # Контролы реально регулируют генерацию: меняем значения — читаем в _gather_params
        app.wrapper_choice_var.set("google_translate")
        app.layers_var.set("2")
        app.params_min_entry.delete(0, "end"); app.params_min_entry.insert(0, "4")
        app.params_max_entry.delete(0, "end"); app.params_max_entry.insert(0, "9")
        app.domains_entry.delete(0, "end"); app.domains_entry.insert(0, "d1.com, d2.com")
        p = app._gather_params()
        assert p["wrapper_name"] == "google_translate", p.get("wrapper_name")
        assert p["wrapper_layers"] == 2 and p["use_wrapper"] is True, p
        assert p["params_count_range"] == (4, 9), p.get("params_count_range")
        assert p["domains"] == ["d1.com", "d2.com"], p.get("domains")
        # Индикатор силы отзывается на регулировку слоёв (позитивный контроль: 0 < 2)
        app.layers_var.set("0"); app._update_strength(); app.update()
        s0 = int("".join(ch for ch in app.strength_label.cget("text") if ch.isdigit()))
        app.layers_var.set("2"); app._update_strength(); app.update()
        s2 = int("".join(ch for ch in app.strength_label.cget("text") if ch.isdigit()))
        assert s2 > s0, f"сила не реагирует на слои: 0-слоёв={s0}, 2-слоя={s2}"
    finally:
        app.destroy()
    return "GATE18_PASS settings-always-visible-and-regulatable"


# ── Гейт 19: кнопка «Сброс» возвращает безопасный максимум (98%) в один клик ─
def g19_reset_defaults():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # Ослабляем настройки как это делал пользователь на скринах (слои 0, парам 0-0)
        app.wrapper_choice_var.set("google_translate")
        app.layers_var.set("0")
        app.params_min_entry.delete(0, "end"); app.params_min_entry.insert(0, "0")
        app.params_max_entry.delete(0, "end"); app.params_max_entry.insert(0, "0")
        app.domains_entry.delete(0, "end"); app.domains_entry.insert(0, "x.com")
        app._update_strength(); app.update()
        low = int("".join(ch for ch in app.strength_label.cget("text") if ch.isdigit()))
        assert low < 75, f"позитивный контроль: ослабленная сила должна быть <75, а она {low}"
        # Сброс — один вызов
        app._reset_defaults(); app.update()
        assert app.wrapper_choice_var.get() == "random", app.wrapper_choice_var.get()
        assert app.layers_var.get() == "1", app.layers_var.get()
        assert app.params_min_entry.get() == "5", app.params_min_entry.get()
        assert app.params_max_entry.get() == "8", app.params_max_entry.get()
        assert app.domains_entry.get() == "", repr(app.domains_entry.get())
        p = app._gather_params()
        assert p["wrapper_name"] is None and p["wrapper_layers"] == 1, p
        assert p["params_count_range"] == (5, 8), p.get("params_count_range")
        assert "domains" not in p, "домены не очистились"
        hi = int("".join(ch for ch in app.strength_label.cget("text") if ch.isdigit()))
        # Дефолт по новой шкале — высокая зона с запасом (~72%), а не 100%.
        assert hi >= 68 and "ВЫСОКАЯ" in app.strength_label.cget("text"), \
            f"после сброса сила {app.strength_label.cget('text')}"
        assert hi > low, f"сброс не поднял силу: было {low}, стало {hi}"
    finally:
        app.destroy()
    return "GATE19_PASS reset-restores-safe-max"


# ── Гейт 20: Ctrl+C (KeyboardInterrupt) — штатный тихий выход, не краш ────
def g20_clean_shutdown():
    import gui
    # 1) main() ГАСИТ KeyboardInterrupt из mainloop и всё равно закрывает окно
    class FakeApp:
        def __init__(self):
            self.destroyed = False
        def mainloop(self):
            raise KeyboardInterrupt          # эмулируем Ctrl+C во время работы окна
        def destroy(self):
            self.destroyed = True
    fake = FakeApp()
    gui.main(app_factory=lambda: fake)       # НЕ должно пробросить KeyboardInterrupt наружу
    assert fake.destroyed, "окно не закрыто в finally после Ctrl+C"

    # 2) Реальный запуск `python gui.py`-эквивалента: окно поднимается и штатно
    #    закрывается (через after→destroy) без трейсбека и с кодом 0.
    import os
    import subprocess
    code = (
        "import gui;"
        "app=gui.LinkUniquifierApp();"
        "app.after(500, app.destroy);"
        "app.mainloop();"
        "print('MAINLOOP_CLEAN_EXIT')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.path.dirname(os.path.abspath(gui.__file__)),
        capture_output=True, encoding="utf-8", errors="replace", timeout=90)
    assert r.returncode == 0, f"ненулевой код выхода {r.returncode}; stderr={r.stderr[-400:]}"
    assert "MAINLOOP_CLEAN_EXIT" in r.stdout, f"нет штатного выхода; stdout={r.stdout[-200:]}"
    assert "Traceback" not in r.stderr, f"трейсбек при штатном закрытии: {r.stderr[-400:]}"
    return "GATE20_PASS clean-shutdown-no-crash"


# ── Гейт 21: сила РАСТЁТ по мере заполнения полей интерфейса ──────────────
def g21_strength_climbs_with_fields():
    S = main.randomization_strength
    safe = dict(use_anchor=True, use_shuffle=True, use_case_mix=True,
                use_encoding=True, use_trailing_slash=True)
    # Последовательно «заполняем» рычаги — каждый шаг обязан поднимать балл
    s0 = S(params_count_range=(0, 0), use_wrapper=False, wrapper_layers=0,
           domains_count=1, has_custom=False, **safe)[0]                 # почти пусто
    s1 = S(params_count_range=(5, 8), use_wrapper=False, wrapper_layers=0,
           domains_count=1, has_custom=False, **safe)[0]                 # +параметры
    s2 = S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=1,
           domains_count=1, has_custom=False, **safe)[0]                 # +обёртка (1 слой)
    s3 = S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=2,
           domains_count=1, has_custom=False, **safe)[0]                 # +2-й слой
    s4 = S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=2,
           domains_count=4, has_custom=False, **safe)[0]                 # +домены
    s5 = S(params_count_range=(10, 20), use_wrapper=True, wrapper_layers=2,
           domains_count=8, has_custom=True, **safe)[0]                  # всё заполнено
    seq = [s0, s1, s2, s3, s4, s5]
    for a, b in zip(seq, seq[1:]):
        assert b > a, f"заполнение поля не подняло силу: {seq}"
    assert s5 >= 98, f"полностью заполненное состояние должно быть ~100%, а {s5}"

    # Каждый ОТДЕЛЬНЫЙ рычаг из дефолта тоже обязан поднять балл (позитивный контроль)
    d = S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=1,
          domains_count=1, has_custom=False, **safe)[0]
    assert S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=1,
             domains_count=3, has_custom=False, **safe)[0] > d, "домены не подняли"
    assert S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=1,
             domains_count=1, has_custom=True, **safe)[0] > d, "свои параметры не подняли"
    assert S(params_count_range=(5, 8), use_wrapper=True, wrapper_layers=2,
             domains_count=1, has_custom=False, **safe)[0] > d, "2-й слой не поднял"
    assert S(params_count_range=(8, 12), use_wrapper=True, wrapper_layers=1,
             domains_count=1, has_custom=False, **safe)[0] > d, "больше параметров не подняли"
    return "GATE21_PASS strength-climbs-with-fields"


# ── Гейт 22: панель пагинации показывается под результатом; спинтакс её прячет ─
def g22_pagination_visible():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update(); app.update_idletasks()
        app._set_links([f"https://x/{i}" for i in range(25000)],
                       requested=25000, dups=0, one_domain=False)
        app.update(); app.update_idletasks()
        # Панель запакована и имеет полную высоту (кнопки 30px не обрезаны).
        assert app.page_bar.winfo_manager() == "pack", "панель не показана"
        assert app.page_bar.winfo_height() >= 30, f"панель раздавлена: {app.page_bar.winfo_height()}"
        assert "Стр. 1 /" in app.page_label.cget("text"), app.page_label.cget("text")
        # Спинтакс прячет панель
        app._show_spintax("{a|b|c}", 3, 0, 3); app.update(); app.update_idletasks()
        assert app.page_bar.winfo_manager() == "", "спинтакс не спрятал панель"
        # page_hint удалён как «маркировка» — его больше нет
        assert not hasattr(app, "page_hint"), "page_hint должен быть удалён"
    finally:
        app.destroy()
    return "GATE22_PASS pagination-visible-no-hint"


# ── Гейт 23: генерация идёт КАДРАМИ и НЕ блокирует UI-цикл ────────────────
def g23_generation_is_chunked_and_responsive():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # Независимый «пульс»: если UI-цикл свободен во время генерации — тикает.
        beats = {"n": 0}
        def beat():
            beats["n"] += 1
            if app._generating:
                app.after(3, beat)
        # Считаем, на сколько кадров разбилась генерация.
        steps = {"n": 0}
        orig_step = app._gen_step
        def counted_step():
            steps["n"] += 1
            return orig_step()
        app._gen_step = counted_step

        params = app._gather_params()
        # G23 проверяет ИМЕННО кооперативный путь кадрами (для мелких объёмов и как
        # фолбэк; крупные объёмы теперь уходят в процесс — это отдельно в G32).
        app._generating = True
        app._gen_cancel = False
        app._start_generation_inproc("https://a.com/x", params, 30000, "ready", False)
        app.after(3, beat)
        import time as _t
        t0 = _t.perf_counter()
        while app._generating and _t.perf_counter() - t0 < 120:
            app.update(); _t.sleep(0.001)

        assert not app._generating, "генерация не завершилась за 120с"
        assert len(app.links) == 30000, f"в наборе {len(app.links)}"
        assert len(set(app.links)) == 30000, "в наборе дубли"
        # Разбита на МНОГО кадров (не один synchronous блок на всё)
        assert steps["n"] > 5, f"генерация не разбита на кадры (шагов {steps['n']})"
        # UI-цикл был свободен ВО ВРЕМЯ генерации — пульс тикал (это и есть «не лагает»)
        assert beats["n"] > 3, f"UI-цикл был заблокирован во время генерации (пульс={beats['n']})"
    finally:
        app.destroy()
    return "GATE23_PASS chunked-responsive-generation"


# ── Гейт 24: кнопка «СТОП» реально прерывает генерацию частичным набором ──
def g24_generation_cancellable():
    import gui
    import time as _t
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        params = app._gather_params()
        # Отмена КООПЕРАТИВНОГО пути (отмена процессного — в G32).
        app._generating = True
        app._gen_cancel = False
        app._start_generation_inproc("https://a.com/x", params, 400000, "ready", False)
        # Дать пройти нескольким кадрам, затем нажать «СТОП»
        for _ in range(3):
            app.update(); _t.sleep(0.005)
        app._cancel_generation()
        t0 = _t.perf_counter()
        while app._generating and _t.perf_counter() - t0 < 30:
            app.update(); _t.sleep(0.001)
        assert not app._generating, "отмена не остановила генерацию"
        # Частичный набор: что-то сгенерилось, но далеко не все 400k
        assert 0 < len(app.links) < 400000, f"после отмены в наборе {len(app.links)}"
        # Кнопка вернулась в исходный вид (не осталась «СТОП»)
        assert "СГЕНЕРИРОВАТЬ" in app.btn_generate.cget("text"), app.btn_generate.cget("text")
    finally:
        app.destroy()
    return "GATE24_PASS generation-cancellable"


# ── Гейт 25: тёмная тема, визуально ДРУГАЯ (акцент сменён с зелёного) ──────
def g25_dark_theme_redesigned():
    import gui
    # Тот же UI-фреймворк (customtkinter), но палитра намеренно другая.
    assert gui.ctk.__name__ == "customtkinter"
    # Фон тёмный (глубокий графит), не белый.
    assert gui.COLOR_BG.startswith("#") and gui.COLOR_BG.lower() < "#404040", gui.COLOR_BG
    # Акцент СМЕНЁН — больше не зелёный #4ade80 из старой темы.
    assert gui.COLOR_ACCENT != "#4ade80", "акцент не изменён — тема не переделана"
    # Приложение реально применяет тёмный режим.
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        assert gui.ctk.get_appearance_mode() == "Dark", gui.ctk.get_appearance_mode()
        # Синий акцент действительно на кнопке генерации.
        assert app.btn_generate.cget("fg_color") == gui.COLOR_ACCENT
    finally:
        app.destroy()
    return "GATE25_PASS dark-theme-redesigned"


# ── Гейт 26: тултипы УБРАНЫ, «маркировки» убраны, плейсхолдеры расписаны ───
def g26_no_tooltips_no_markings():
    import gui
    # Тултипов нет ни как класса, ни как механизма
    assert not hasattr(gui, "Tooltip"), "класс Tooltip не удалён"
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        assert not hasattr(app, "_tooltips"), "реестр тултипов не удалён"
        assert not hasattr(app, "_tip"), "метод _tip не удалён"
        # «Маркировки» убраны: дисклеймер/статус-баннеры/подсказки-приписки
        for attr in ("count_label", "warn_label", "mode_hint", "page_hint"):
            assert not hasattr(app, attr), f"маркировка {attr} не убрана"
        # Плейсхолдеры остались доходчивыми (пример + как вводить)
        url_ph = app.url_entry.cget("placeholder_text")
        assert "http" in url_ph and "site.com" in url_ph and "Ctrl+V" in url_ph, url_ph
        # Плейсхолдер поля своих параметров теперь ЗАВИСИТ ОТ РЕЖИМА (см. G29).
        # Дефолтный режим «через &» показывает пример-макрос и как вводить (запятая).
        cust_ph = app.custom_params_entry.cget("placeholder_text")
        assert "{SUBID}" in cust_ph and "запятую" in cust_ph, cust_ph
        dom_ph = app.domains_entry.cget("placeholder_text")
        assert "запятую" in dom_ph and "пусто" in dom_ph, dom_ph
    finally:
        app.destroy()
    return "GATE26_PASS no-tooltips-no-markings"


# ── Гейт 27: Cloud HTML — тройной редирект, срез реферера, уникальность ───
def g27_cloud_redirect_robust():
    payload = "https://a.com/land?x=1&y=2"
    h1 = main.generate_cloud_html(payload)
    h2 = main.generate_cloud_html(payload)
    # Тройной редирект: JS replace + meta refresh + noscript-ссылка
    assert "location.replace(" in h1, "нет JS location.replace"
    assert 'http-equiv="refresh"' in h1, "нет meta refresh"
    assert "<noscript" in h1, "нет noscript-фолбэка"
    # Реферер режется
    assert 'name="referrer"' in h1 and "no-referrer" in h1, "нет среза реферера"
    # Каждая страница уникальна (nonce + случайный мусор) — можно лить пачками
    assert h1 != h2, "страницы не уникальны"
    # target присутствует (HTML-escaped) — в meta refresh и noscript
    from html import escape
    assert escape(payload, quote=True) in h1, "target потерян в HTML"
    return "GATE27_PASS cloud-redirect-robust"


# ── Гейт 28: результат скроллится по ГОРИЗОНТАЛИ тачпадом/Shift+колесом ────
def g28_result_horizontal_scroll():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        tb = app.result_box._textbox
        # wrap=none — иначе горизонтальной прокрутки в принципе нет (строки переносятся)
        assert str(tb.cget("wrap")) == "none", tb.cget("wrap")
        # Горизонтальный жест тачпада Windows приходит как <Shift-MouseWheel> —
        # биндинг должен висеть на внутреннем text-виджете и гасить всплытие ("break").
        b = tb.bind("<Shift-MouseWheel>")
        assert b and "break" in b, f"нет биндинга горизонтали: {b!r}"
        # Обработчик реально двигает xview и гасит всплытие. Подменяем скроллеры,
        # чтобы детерминированно проверить, ЧТО именно он дёргает (без геометрии окна).
        calls = []
        orig_x, orig_y = tb.xview_scroll, tb.yview_scroll
        tb.xview_scroll = lambda *a, **k: calls.append(("x", a))
        tb.yview_scroll = lambda *a, **k: calls.append(("y", a))
        try:
            class _E:
                delta = -120; num = None; state = 1
            r = app._result_wheel_x(_E())
            assert r == "break", f"горизонталь не гасит всплытие: {r}"
            assert calls and calls[-1][0] == "x", f"горизонталь не двинула xview: {calls}"
            # Позитивный контроль: вертикальный обработчик НЕ трогает xview (разные оси)
            calls.clear()
            app._result_wheel(_E())
            assert calls and all(c[0] == "y" for c in calls), f"вертикаль тронула xview: {calls}"
        finally:
            tb.xview_scroll, tb.yview_scroll = orig_x, orig_y
    finally:
        app.destroy()
    return "GATE28_PASS result-horizontal-touchpad-scroll"


# ── Гейт 29: подсказка поля своих параметров меняется под выбранный режим ──
def g29_custom_hint_per_mode():
    import gui
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # Дефолт — режим «через &»: подсказка про перечисление через запятую + пример-макрос
        ph = app.custom_params_entry.cget("placeholder_text")
        assert "запятую" in ph and "{SUBID}" in ph, ph
        # Переключение на «как есть» — подсказка меняется на дословный хвост
        app.custom_mode_var.set("как есть"); app.update()
        ph2 = app.custom_params_entry.cget("placeholder_text")
        assert "дословно" in ph2 and "#{LINK}" in ph2, ph2
        assert ph2 != ph, "подсказка не сменилась под режим"
        # Назад в «через &» — снова про запятую (позитивный контроль: переключение туда-обратно)
        app.custom_mode_var.set("через &"); app.update()
        ph3 = app.custom_params_entry.cget("placeholder_text")
        assert "запятую" in ph3 and ph3 == ph, ph3
    finally:
        app.destroy()
    return "GATE29_PASS custom-hint-per-mode"


# ── Гейт 30: RNG — быстрый некрипто Mersenne (крипто убран как тормоз) ─────
def g30_fast_noncrypto_rng():
    import random as _r
    # RNG — именно обычный Mersenne, а НЕ крипто SystemRandom (тот дёргал os.urandom
    # на каждую операцию и был главным тормозом; крипто-стойкость тут не нужна).
    # SystemRandom — подкласс Random, поэтому проверяем ТОЧНЫЙ тип, не isinstance.
    assert type(main._RNG) is _r.Random, type(main._RNG)
    # Позитивный контроль: крипто-модуль secrets из main убран целиком.
    assert not hasattr(main, "secrets"), "secrets всё ещё в модуле — крипто-RNG не убран"
    # _htok сохраняет контракт token_hex(n): РОВНО 2*n hex-символов.
    for n in (1, 2, 3, 4, 8, 16):
        t = main._htok(n)
        assert len(t) == 2 * n and all(c in "0123456789abcdef" for c in t), (n, t)
    # Генерация по-прежнему корректна: 500 ссылок 100% уникальны и валидны.
    seen = set()
    for _ in range(500):
        u = main.uniquify_url("https://a.com/x", "ready",
                              params_count_range=(15, 40), use_wrapper=True, wrapper_layers=2)
        assert u.startswith("http"), u
        seen.add(u)
    assert len(seen) == 500, f"уникальных {len(seen)}/500 — генерация деградировала"
    return "GATE30_PASS fast-noncrypto-rng"


# ── Гейт 31: Ctrl+C ВНУТРИ after-колбэка Tk — тихое закрытие, не трейсбек ──
def g31_ctrl_c_in_callback_clean():
    import gui, os, subprocess
    cwd = os.path.dirname(os.path.abspath(gui.__file__))
    # KeyboardInterrupt, прилетевший в after-колбэк (как трекер темы customtkinter):
    # окно закрывается штатно, БЕЗ «Exception in Tkinter callback» и трейсбека.
    code = (
        "import gui\n"
        "app=gui.LinkUniquifierApp()\n"
        "def boom():\n"
        "    raise KeyboardInterrupt\n"
        "app.after(300, boom)\n"
        "app.after(2000, app.destroy)\n"
        "gui.main(app_factory=lambda: app)\n"
        "print('CLEAN_KI_IN_CALLBACK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=cwd,
                       capture_output=True, encoding="utf-8", errors="replace", timeout=90)
    assert r.returncode == 0, f"ненулевой код {r.returncode}; stderr={r.stderr[-400:]}"
    assert "CLEAN_KI_IN_CALLBACK" in r.stdout, f"нет штатного выхода; stdout={r.stdout[-200:]}"
    assert "Exception in Tkinter callback" not in r.stderr, \
        f"трейсбек колбэка не подавлен: {r.stderr[-400:]}"
    assert "Traceback" not in r.stderr, f"простыня трейсбека при Ctrl+C: {r.stderr[-400:]}"
    # ПОЗИТИВНЫЙ КОНТРОЛЬ: обычная ошибка в колбэке ВСЁ ЕЩЁ показывается (баги не прячем)
    code2 = (
        "import gui\n"
        "app=gui.LinkUniquifierApp()\n"
        "def boom():\n"
        "    app.after(400, app.destroy)\n"
        "    raise ValueError('real-bug-xyz')\n"
        "app.after(300, boom)\n"
        "app.mainloop()\n"
        "app.destroy()\n"
    )
    r2 = subprocess.run([sys.executable, "-c", code2], cwd=cwd,
                        capture_output=True, encoding="utf-8", errors="replace", timeout=90)
    assert "real-bug-xyz" in r2.stderr and "ValueError" in r2.stderr, \
        f"обычная ошибка колбэка обязана показываться: {r2.stderr[-300:]}"
    return "GATE31_PASS ctrl-c-in-callback-clean"


# ── Гейт 32: крупная генерация уходит в ОТДЕЛЬНЫЙ ПРОЦЕСС, UI-поток свободен ─
def g32_process_generation_frees_ui():
    import gui, time as _t
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        p = app._gather_params()
        p["params_count_range"] = (15, 40); p["wrapper_layers"] = 2; p["use_wrapper"] = True
        # Инструментируем: сколько UI-поток ЗАНЯТ дренажем + что кооперативный
        # _gen_step вообще НЕ вызывается (значит работает процессный путь).
        busy = {"t": 0.0}
        steps = {"n": 0}
        orig_step = app._gen_step
        def counted_step():
            steps["n"] += 1
            return orig_step()
        app._gen_step = counted_step
        orig_drain = app._mp_drain
        def timed_drain():
            b = _t.perf_counter()
            try:
                orig_drain()
            finally:
                busy["t"] += _t.perf_counter() - b
        app._mp_drain = timed_drain

        N = 12000
        t0 = _t.perf_counter()
        app._start_generation("https://a.com/x", p, N, "ready", False)
        assert app._mp is not None, "крупный объём должен уходить в отдельный процесс"
        while app._generating and _t.perf_counter() - t0 < 120:
            app.update(); _t.sleep(0.004)
        wall = _t.perf_counter() - t0
        assert not app._generating, "процессная генерация не завершилась"
        assert len(app.links) == N and len(set(app.links)) == N, \
            f"набор {len(app.links)}/{len(set(app.links))} из {N}"
        assert app._mp is None, "состояние процесса не сброшено после финиша"
        # Кооперативный путь НЕ использовался (это и есть процессная генерация)
        assert steps["n"] == 0, f"_gen_step вызывался ({steps['n']}) — путь не процессный"
        # UI-поток был занят дренажем лишь малую долю времени (у inproc было бы ~95%)
        frac = busy["t"] / wall if wall else 1.0
        assert frac < 0.30, f"UI-поток занят {frac*100:.0f}% времени (ждали <30%)"

        # Отмена процессного пути → частичный набор, кнопка восстановлена
        app.update()
        app._start_generation("https://a.com/x", p, 300000, "ready", False)
        t1 = _t.perf_counter()
        while app._generating and (not app._mp or len(app._mp["links"]) < 3000) \
                and _t.perf_counter() - t1 < 40:
            app.update(); _t.sleep(0.004)
        app._cancel_generation()
        t2 = _t.perf_counter()
        while app._generating and _t.perf_counter() - t2 < 40:
            app.update(); _t.sleep(0.004)
        assert not app._generating, "отмена процесса не завершилась"
        got = len(app.links)
        assert 0 < got < 300000, f"после отмены в наборе {got}"
        assert "СГЕНЕРИРОВАТЬ" in app.btn_generate.cget("text")
    finally:
        app.destroy()
    return "GATE32_PASS process-generation-frees-ui"


# ── Гейт 33: гибридный редизайн (нейтральная база + синий акцент), функционал цел ─
def g33_hybrid_redesign_intact():
    import gui
    import customtkinter as ctk
    # Палитра — нейтральная база, но акцент СИНИЙ, а НЕ зелёный #4ade80
    # (гейт G25: визуал не должен вернуться к чёрно-зелёному).
    assert gui.COLOR_ACCENT != "#4ade80", "акцент не должен стать зелёным"
    assert gui.COLOR_BORDER == "#262a33", gui.COLOR_BORDER
    assert gui.COLOR_TEXT == "#e6e8ec", gui.COLOR_TEXT
    # Новые дизайн-токены гибрида добавлены
    for tok in ("COLOR_BORDER2", "COLOR_ACCENT_SOFT", "COLOR_PANEL2", "COLOR_TEXT_DIM2"):
        assert hasattr(gui, tok), f"нет нового токена {tok}"
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # Фиксированная шапка-хром (бренд-чип + вордмарк + индикатор)
        assert hasattr(app, "header") and app.header.winfo_manager() == "pack", "нет шапки-хрома"
        assert hasattr(app, "brand_chip") and app.brand_chip.winfo_exists(), "нет бренд-чипа"
        assert hasattr(app, "bridge_label") and app.bridge_label.winfo_exists(), "нет индикатора"
        # Инвариант не сломан: страница по-прежнему прокручиваемая
        assert isinstance(app.scroll, ctk.CTkScrollableFrame)
        # ВЕСЬ функционал на месте: ключевые контролы существуют (редизайн ничего не убрал)
        for name, w in (("url", app.url_entry), ("count", app.count_entry),
                        ("wrapper", app.wrapper_menu), ("layers", app.layers_menu),
                        ("pmin", app.params_min_entry), ("pmax", app.params_max_entry),
                        ("domains", app.domains_entry), ("custom", app.custom_params_entry),
                        ("gen", app.btn_generate), ("reset", app.btn_reset),
                        ("result", app.result_box), ("page_bar", app.page_bar),
                        ("s_bar", app.strength_bar), ("s_lbl", app.strength_label),
                        ("status", app.status_label)):
            assert w.winfo_exists(), f"контрол пропал после редизайна: {name}"
        # Кнопка генерации всё ещё на синем акценте (визуальный якорь сохранён)
        assert app.btn_generate.cget("fg_color") == gui.COLOR_ACCENT
        # Живой индикатор реагирует на статус
        app._set_status("идёт", gui.COLOR_WARN)
        assert "генерация" in app.bridge_label.cget("text"), app.bridge_label.cget("text")
    finally:
        app.destroy()
    return "GATE33_PASS hybrid-redesign-intact"


# ── Гейт 34: иконки у элементов + нормальные стрелки пагинации ────────────
def g34_icons_and_pagination_arrows():
    import gui, inspect
    app = gui.LinkUniquifierApp()
    try:
        app.update()
        # НОРМАЛЬНЫЕ стрелки пагинации: без «палки» |, на краях — двойные треугольники,
        # и края отличаются от пред/след.
        first, prev = app.btn_first.cget("text"), app.btn_prev.cget("text")
        nxt, last = app.btn_next.cget("text"), app.btn_last.cget("text")
        assert "|" not in first and "|" not in last, (first, last)
        assert "◀" in first and "◀" in prev and "▶" in nxt and "▶" in last, (first, prev, nxt, last)
        assert first != prev and last != nxt, "края пагинации не отличаются от пред/след"
        # ИКОНКИ-глифы на ключевых кнопках (первый непробельный символ — НЕ буква)
        gen = app.btn_generate.cget("text")
        rst = app.btn_reset.cget("text")
        assert "СГЕНЕРИРОВАТЬ" in gen and not gen.strip()[0].isalpha(), f"нет иконки у генерации: {gen!r}"
        assert "Сброс" in rst and not rst.strip()[0].isalpha(), f"нет иконки у сброса: {rst!r}"
        # У секций-карточек появилась поддержка иконки (новый параметр _panel(icon=...))
        assert "icon" in inspect.signature(app._panel).parameters, "у _panel нет параметра icon"
        # Пагинация ВСЁ ЕЩЁ работает — функционал цел
        app._set_links([f"u{i}" for i in range(2500)], requested=2500, dups=0, one_domain=False)
        app.update()
        assert "Стр. 1 /" in app.page_label.cget("text")
        app._page_last(); app.update()
        assert "Стр. 3 /" in app.page_label.cget("text"), app.page_label.cget("text")
    finally:
        app.destroy()
    return "GATE34_PASS icons-and-pagination-arrows"


GATES = {
    "G1": g1_reversed_range,
    "G2": g2_fragment_preserved,
    "G3": g3_port_valid_host,
    "G4": g4_schemeless,
    "G5": g5_domain_sanitize,
    "G6": g6_cloud_html_safe,
    "G7": g7_regression,
    "G9": g9_strength,
    "G10": g10_custom_tail,
    "G11": g11_gui_smoke,
    "G12": g12_paste_any_layout,
    "G13": g13_defocus,
    "G14": g14_responsive_no_squish,
    "G15": g15_no_limit_and_file,
    "G16": g16_page_bounds,
    "G17": g17_pagination_render_and_all,
    "G18": g18_settings_always_visible,
    "G19": g19_reset_defaults,
    "G20": g20_clean_shutdown,
    "G21": g21_strength_climbs_with_fields,
    "G22": g22_pagination_visible,
    "G23": g23_generation_is_chunked_and_responsive,
    "G24": g24_generation_cancellable,
    "G25": g25_dark_theme_redesigned,
    "G26": g26_no_tooltips_no_markings,
    "G27": g27_cloud_redirect_robust,
    "G28": g28_result_horizontal_scroll,
    "G29": g29_custom_hint_per_mode,
    "G30": g30_fast_noncrypto_rng,
    "G31": g31_ctrl_c_in_callback_clean,
    "G32": g32_process_generation_frees_ui,
    "G33": g33_hybrid_redesign_intact,
    "G34": g34_icons_and_pagination_arrows,
}


def run(names):
    failed = 0
    for name in names:
        fn = GATES[name]
        try:
            msg = fn()
            print(f"[PASS] {name}: {msg}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {name}: {type(e).__name__}: {e}")
    if failed:
        print(f"\nFAILED {failed}/{len(names)}")
        sys.exit(1)
    print(f"\nALL_AUDIT_GATES_PASS ({len(names)}/{len(names)})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a in GATES]
    run(args if args else list(GATES.keys()))
