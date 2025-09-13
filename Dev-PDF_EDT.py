import time, socket, yaml
from contextlib import closing
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# =========================
# Chargement configuration
# =========================
def load_cfg(path="conf.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# =========================
# Utilitaires réseau & logs
# =========================
def can_resolve(host: str) -> bool:
    try:
        socket.gethostbyname(host); return True
    except Exception:
        return False

def can_tcp_connect(host: str, port: int, timeout=3.0) -> bool:
    try:
        with closing(socket.create_connection((host, port), timeout=timeout)):
            return True
    except Exception:
        return False

def goto_with_retry(page, url, attempts=3, wait_between=2.0, timeout_ms=30000):
    last_err = None
    for i in range(1, attempts+1):
        print(f"[INFO] Navigation tentative {i}/{attempts} -> {url}")
        try:
            page.goto(url, wait_until="load", timeout=timeout_ms)
            print(f"[INFO] Page chargée: {page.url}")
            return
        except Exception as e:
            last_err = e
            print(f"[WARN] Échec goto (tentative {i}): {e}")
            time.sleep(wait_between)
    raise last_err

def list_frames(page, label="[INFO] Frames"):
    print(label)
    for fr in page.frames:
        print(f"  - name={fr.name!r}  url={fr.url}")

def wait_for_content_loaded(page, name="content", timeout_ms=25000, settle_ms=1500):
    """Attend que la frame 'content' charge une page ≠ blank, puis laisse settle_ms ms."""
    t0 = time.time()
    while (time.time() - t0) * 1000 < timeout_ms:
        fr = page.frame(name=name)
        if fr and fr.url and fr.url not in ("about:blank", "/blank.html") and not fr.url.endswith("/blank.html"):
            page.wait_for_timeout(settle_ms)
            return fr
        page.wait_for_timeout(200)
    list_frames(page, "[ERROR] Frames au moment du timeout")
    raise RuntimeError(f"La frame '{name}' n'a pas chargé de contenu (timeout).")

# ======================================
# Lancement navigateur (Chrome / proxy)
# ======================================
def launch_browser(pw, cfg):
    channel = "chrome" if cfg.get("use_chrome_channel", False) else None
    proxy_cfg = cfg.get("proxy") or {}
    proxy = None
    if proxy_cfg.get("server"):
        proxy = {
            "server": proxy_cfg["server"],
            "username": proxy_cfg.get("username") or None,
            "password": proxy_cfg.get("password") or None,
        }
    args = []
    if cfg.get("proxy_pac_url"):
        args.append(f'--proxy-pac-url={cfg["proxy_pac_url"]}')
    if cfg.get("proxy_auto_detect"):
        args.append("--proxy-auto-detect")

    headless = bool(cfg.get("headless", True))
    ignore_https = bool(cfg.get("ignore_https_errors", False))

    print(f"[INFO] Lancement navigateur | channel={channel} proxy={proxy} args={args} headless={headless}")
    browser = pw.chromium.launch(headless=headless, proxy=proxy, channel=channel, args=args)
    context = browser.new_context(ignore_https_errors=ignore_https)
    page = context.new_page()
    try:
        print("[INFO] navigator.onLine =", page.evaluate("navigator.onLine"))
    except Exception:
        pass
    return browser, context, page

def try_webkit_fallback(pw, cfg):
    print("[WARN] Tentative de secours avec WebKit…")
    headless = bool(cfg.get("headless", True))
    ignore_https = bool(cfg.get("ignore_https_errors", False))
    browser = pw.webkit.launch(headless=headless)
    context = browser.new_context(ignore_https_errors=ignore_https)
    page = context.new_page()
    print("[INFO] (WebKit) navigator.onLine =", page.evaluate("navigator.onLine"))
    return browser, context, page

# =========================
# SSO → CAS → Consentement
# =========================
def click_sso_button(page):
    print("[INFO] Attente bouton SSO…")
    page.wait_for_selector('#remoteAuth .provider', timeout=15000)
    btns = page.locator('#remoteAuth .provider')
    count = btns.count()
    print(f"[DEBUG] Providers trouvés: {count}")
    clicked = False
    for i in range(count):
        txt = btns.nth(i).inner_text().strip()
        print(f"[DEBUG] provider[{i}] = {txt}")
        if "SSO" in txt.upper():
            btns.nth(i).click(); clicked = True
            print("[INFO] Clic sur SSO."); break
    if not clicked:
        btns.first.click()
        print("[WARN] 'SSO' non trouvé explicitement, clic sur le premier provider.")
    page.wait_for_load_state("load")

def cas_login(page, username, password, consent_choice="remember"):
    """
    Auth CAS + gestion de la page 'Transmission de données' (Shibboleth) si nécessaire.
    consent_choice: 'remember' | 'once' | 'global'
    """
    print("[INFO] Attente page CAS…")
    page.wait_for_url(lambda u: "cas.imt-atlantique.fr/cas/login" in u, timeout=30000)
    print(f"[INFO] Sur CAS: {page.url}")

    page.wait_for_selector("#username", timeout=15000)
    page.fill("#username", username)
    page.fill("#password", password)

    if page.locator('button:has-text("Se connecter")').count():
        page.click('button:has-text("Se connecter")')
    else:
        page.click('input[type="submit"]')

    page.wait_for_load_state("networkidle")
    print(f"[INFO] Après soumission CAS, URL: {page.url}")

    # Consentement Shibboleth (Transmission de données)
    def is_consent_page():
        url = (page.url or "").lower()
        title = (page.title() or "").strip().lower()
        return ("/idp/profile/saml2/post/sso" in url) or ("transmission de données" in title) or ("transmission de donnees" in title)

    if is_consent_page():
        print(f"[INFO] Page de consentement détectée: {page.url}")
        mapping = {
            "once":    '#_shib_idp_doNotRememberConsent',
            "remember":'#_shib_idp_rememberConsent',
            "global":  '#_shib_idp_globalConsent',
        }
        selector = mapping.get(consent_choice, '#_shib_idp_rememberConsent')
        try:
            if page.locator(selector).count():
                page.check(selector)
                print(f"[INFO] Option consentement cochée: {consent_choice}")
        except Exception as e:
            print(f"[WARN] Impossible de cocher l’option {consent_choice}: {e}")

        page.wait_for_selector('input[name="_eventId_proceed"]', timeout=10000)
        page.click('input[name="_eventId_proceed"]')
        page.wait_for_load_state("networkidle")
        print(f"[INFO] Consentement validé, URL: {page.url}")

# =========================
# Clic “Agenda” (opentop)
# =========================
def click_agenda_in_opentop(page, agenda_sel='text=Agenda', timeout_ms=8000) -> bool:
    top = page.frame(name="opentop")
    if not top:
        print("[WARN] Frame 'opentop' introuvable.")
        return False

    # 1) par rôle (si c'est un lien)
    try:
        link = top.get_by_role("link", name="Agenda")
        if link.count():
            link.first.scroll_into_view_if_needed()
            link.first.click(timeout=timeout_ms)
            print("[INFO] Agenda cliqué via role=link (opentop).")
            return True
    except Exception as e:
        print(f"[DEBUG] get_by_role('Agenda') KO: {e}")

    # 2) par texte → ancêtre <a>
    try:
        span = top.locator(agenda_sel).first
        if span.count():
            if span.evaluate("el => !!el.closest('a')"):
                top.evaluate("el => el.closest('a').click()", span.element_handle())
                print("[INFO] Agenda cliqué via ancêtre <a> (opentop).")
                return True
    except Exception as e:
        print(f"[DEBUG] Ancêtre <a> KO: {e}")

    # 3) clic JS direct même si non “visible”
    try:
        el = top.locator(agenda_sel).first
        if el.count():
            top.evaluate("el => el.click()", el.element_handle())
            print("[INFO] Agenda cliqué via evaluate(click) (opentop).")
            return True
    except Exception as e:
        print(f"[DEBUG] evaluate(click) KO: {e}")

    print("[WARN] Impossible de cliquer 'Agenda' dans 'opentop'.")
    return False

# =========================
# Export PDF style “Cmd+P → PDF”
# =========================
def export_pdf_like_dialog(page, pdf_path: str):
    """
    A4, paysage, arrière-plans ON, échelle 100 %, en-têtes/pieds (date, titre, URL, pagination)
    """
    page.emulate_media(media="print")

    header_tpl = """
    <div style="width:100%; font-size:9px; color:#444; padding:4px 8px; border-bottom:1px solid #ddd;">
      <span class="date"></span><span style="margin:0 8px;">|</span><span class="title"></span>
    </div>"""
    footer_tpl = """
    <div style="width:100%; font-size:9px; color:#444; padding:4px 8px; border-top:1px solid #ddd; display:flex; justify-content:space-between;">
      <span class="url" style="max-width:70%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"></span>
      <span>Page <span class="pageNumber"></span>/<span class="totalPages"></span></span>
    </div>"""

    # verrouille la taille si le site n’a pas de @page
    page.add_style_tag(content="@page { size: A4 landscape; margin: 10mm; }")
    page.wait_for_load_state("networkidle")

    page.pdf(
        path=pdf_path,
        format="A4",
        landscape=True,
        print_background=True,
        scale=1,
        display_header_footer=True,
        header_template=header_tpl,
        footer_template=footer_tpl,
        margin={"top": "14mm", "bottom": "14mm", "left": "10mm", "right": "10mm"},
    )

# =========================
# Orchestration principale
# =========================
def export_agenda_pdf(cfg):
    pass_url   = cfg["pass_url"]
    username   = cfg["username"]
    password   = cfg["password"]
    pdf_out    = cfg.get("pdf_out", "agenda.pdf")
    agenda_sel = cfg.get("agenda_link_selector", 'text=Agenda')
    consent    = cfg.get("consent_choice", "remember")

    # Sanity check réseau côté OS
    print("[INFO] Auto-check réseau…")
    hosts = ["pass.imt-atlantique.fr", "cas.imt-atlantique.fr"]
    for h in hosts:
        print(f"  - Résolution DNS {h}: {'OK' if can_resolve(h) else 'KO'}")
    print(f"  - TCP {hosts[0]}:443 -> {'OK' if can_tcp_connect(hosts[0], 443) else 'KO'}")
    print(f"  - TCP {hosts[1]}:443 -> {'OK' if can_tcp_connect(hosts[1], 443) else 'KO'}")

    with sync_playwright() as pw:
        # Lancement (Chrome canal recommandé)
        try:
            browser, context, page = launch_browser(pw, cfg)
            print(f"[INFO] Ouverture PASS: {pass_url}")
            goto_with_retry(page, pass_url, attempts=3, wait_between=2.5, timeout_ms=35000)
        except Exception as e:
            print(f"[ERROR] Chromium/Chrome a échoué: {e}")
            # Secours WebKit
            browser, context, page = try_webkit_fallback(pw, cfg)
            print(f"[INFO] Ouverture PASS (WebKit): {pass_url}")
            goto_with_retry(page, pass_url, attempts=2, wait_between=2.0, timeout_ms=35000)

        # SSO → CAS
        click_sso_button(page)
        cas_login(page, username, password, consent_choice=consent)

        # Retour PASS (frameset)
        page.wait_for_load_state("networkidle")
        print(f"[INFO] Retour PASS: {page.url}")
        list_frames(page)

        # Clic “Agenda” dans 'opentop'
        clicked = click_agenda_in_opentop(page, agenda_sel=agenda_sel, timeout_ms=8000)
        if not clicked:
            print("[WARN] Agenda pas cliqué (peut-être déjà affiché).")

        # Attendre que 'content' charge l’URL réelle
        content_frame = wait_for_content_loaded(page, name="content", timeout_ms=25000, settle_ms=1500)
        content_url = content_frame.url
        print(f"[INFO] URL agenda détectée: {content_url}")

        # Onglet dédié pour export
        # (NOUVEAU) Export via un Chromium headless séparé (avec les mêmes cookies)
        state = get_storage_state(context)
        export_pdf_via_headless_chromium(
            pw,
            content_url=content_url,
            pdf_path=pdf_out,
            storage_state=state,
            ignore_https_errors=bool(cfg.get("ignore_https_errors", False)),
            settle_seconds=5,  # ou 6-8s si besoin
        )
        print(f"[INFO] PDF sauvegardé: {pdf_out}")
        context.close()
        browser.close()

    return pdf_out
def export_pdf_via_headless_chromium(
    pw,
    content_url: str,
    pdf_path: str,
    storage_state: dict,
    ignore_https_errors: bool,
    settle_seconds: int = 5
):
    """
    Ouvre Chromium headless, réutilise la session, trouve l'iframe interne qui contient l'agenda,
    bascule dessus et exporte un PDF fidèle (couleurs + paysage). Ajoute un délai de stabilisation.
    """
    browser_h = pw.chromium.launch(headless=True)
    ctx_h = browser_h.new_context(ignore_https_errors=ignore_https_errors, storage_state=storage_state)
    page_h = ctx_h.new_page()

    # 1) Charger la page 'content' (peut encore contenir un iframe agenda)
    page_h.goto(content_url, wait_until="load", timeout=45000)
    page_h.wait_for_load_state("networkidle")

    # 2) Chercher une iframe interne "réelle"
    def pick_inner_frame(p):
        # écarte about:blank/blank.html, garde la 1re frame non vide différente de l’URL parent
        parent_url = (p.url or "").lower()
        candidates = []
        for fr in p.frames:
            url = (fr.url or "").lower()
            if not url:
                continue
            if url in ("about:blank", "/blank.html") or url.endswith("/blank.html"):
                continue
            if url == parent_url:
                continue
            candidates.append(fr)
        return candidates[0] if candidates else None

    inner = pick_inner_frame(page_h)
    if inner:
        target_url = inner.url
    else:
        # Pas d’iframe détectée : on tente quand même la page courante
        target_url = page_h.url

    # 3) Ouvrir directement l’URL "agenda" (hors conteneur) dans un onglet headless propre
    page_h2 = ctx_h.new_page()
    page_h2.goto(target_url, wait_until="load", timeout=45000)
    page_h2.wait_for_load_state("networkidle")

    # 4) Rendu "comme à l’écran" (évite @media print qui masque parfois le grid)
    page_h2.emulate_media(media="screen")
    page_h2.add_style_tag(content="""
        @page { size: A4 landscape; margin: 10mm; }
        * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        html, body { background: white !important; }
    """)

    # 5) Tempo de stabilisation
    print(f"[INFO] Attente {settle_seconds}s pour stabilisation de l'agenda…")
    page_h2.wait_for_timeout(settle_seconds * 1000)

    # 6) Export PDF (A4 paysage, arrière-plan, 100 %, en-têtes/pieds)
    header_tpl = """
    <div style="width:100%; font-size:9px; color:#444; padding:4px 8px; border-bottom:1px solid #ddd;">
      <span class="date"></span><span style="margin:0 8px;">|</span><span class="title"></span>
    </div>"""
    footer_tpl = """
    <div style="width:100%; font-size:9px; color:#444; padding:4px 8px; border-top:1px solid #ddd; display:flex; justify-content:space-between;">
      <span class="url" style="max-width:70%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"></span>
      <span>Page <span class="pageNumber"></span>/<span class="totalPages"></span></span>
    </div>"""

    page_h2.pdf(
        path=pdf_path,
        format="A4",
        landscape=True,
        print_background=True,
        scale=1,
        display_header_footer=True,
        header_template=header_tpl,
        footer_template=footer_tpl,
        margin={"top": "14mm", "bottom": "14mm", "left": "10mm", "right": "10mm"},
    )

    ctx_h.close()
    browser_h.close()
def get_storage_state(context):
    """
    Récupère l'état (cookies, localStorage) du contexte courant pour le réutiliser
    dans le Chromium headless d'export.
    """
    return context.storage_state()
# =========================
# Main
# =========================
if __name__ == "__main__":
    cfg = load_cfg("conf.yaml")
    out = export_agenda_pdf(cfg)
    print(f"✅ PDF final: {out}")