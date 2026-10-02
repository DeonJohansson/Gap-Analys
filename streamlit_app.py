"""
GAP-analys – Streamlit-app

Första gången visar appen en guide: koppla Fortnox med en knapp, välj vilket
artikelfält som är kategorin, och starta första hämtningen. Därefter visas
rapporten direkt från databasen och synkas mot Fortnox i bakgrunden.
"""
import csv
import io
import json
import os
import secrets
import threading

import streamlit as st

st.set_page_config(page_title="GAP-analys", page_icon="📊", layout="wide")

# Streamlit Secrets -> miljövariabler (som fortnox_core läser)
try:
    for k, v in st.secrets.items():
        if isinstance(v, (str, int, float)):
            os.environ.setdefault(k, str(v))
except Exception:
    pass

import fortnox_core as fc  # noqa: E402

st.markdown("""
<style>
  header[data-testid="stHeader"], footer {display:none}
  .block-container {padding: .6rem 1rem 0; max-width: 100%}
  div[data-testid="stHorizontalBlock"] {align-items: center}
  .guide {max-width: 760px}
</style>""", unsafe_allow_html=True)

FORTNOX_DEV = "https://www.fortnox.se/developer"
SCOPE_TEXT = "Faktura (invoice), Artikel (article), Kund (customer), Företagsinformation (companyinformation)"

# --------------------------------------------------------------------------- #
# Lösenord (valfritt, APP_LOSENORD i Secrets)
# --------------------------------------------------------------------------- #
pw = os.environ.get("APP_LOSENORD", "")
if pw and not st.session_state.get("inloggad"):
    st.subheader("GAP-analys")
    x = st.text_input("Lösenord", type="password")
    if x == pw:
        st.session_state.inloggad = True
        st.rerun()
    elif x:
        st.error("Fel lösenord")
    st.stop()

# --------------------------------------------------------------------------- #
# Databas
# --------------------------------------------------------------------------- #
if not os.environ.get("DATABASE_URL"):
    st.title("GAP-analys – installation")
    st.error("Databasen är inte inlagd än.")
    st.markdown("Öppna appens **Settings → Secrets** på Streamlit och lägg in raden nedan med er "
                "connection string från Neon. Appen startar om av sig själv när du sparar.")
    st.code('DATABASE_URL = "postgresql://..."', language="toml")
    st.stop()


@st.cache_resource
def db_conn():
    return fc.DB(autocommit=True)


def db():
    con = db_conn()
    try:
        con.execute("SELECT 1").fetchone()
    except Exception:  # anslutningen kan ha tappats – öppna en ny
        try:
            con.con.rollback()
            con.execute("SELECT 1").fetchone()
        except Exception:
            db_conn.clear()
            con = db_conn()
    return con


D = db()


# --------------------------------------------------------------------------- #
# Bakgrundssynk: en tråd per server-process, kan väckas direkt
# --------------------------------------------------------------------------- #
@st.cache_resource
def worker():
    wake = threading.Event()

    def loop():
        while True:
            try:
                fc.sync_if_stale(15)
            except Exception as e:
                print("Synkfel:", e, flush=True)
            wake.wait(300)
            wake.clear()

    threading.Thread(target=loop, daemon=True).start()
    return wake


WAKE = worker()


def force_sync_soon():
    D.meta_set("last_sync_utc", "2000-01-01T00:00:00")
    WAKE.set()


# --------------------------------------------------------------------------- #
# Hjälp
# --------------------------------------------------------------------------- #
def app_url():
    u = os.environ.get("APP_URL") or D.meta_get("app_url") or ""
    if not u:
        try:
            u = st.context.url or ""
        except Exception:
            u = ""
    u = u.split("?")[0].split("/~/")[0]
    return u.rstrip("/")


def settings():
    return fc.load_settings(D)


def chosen_settings():
    return json.loads(D.meta_get("settings") or "{}")


# --------------------------------------------------------------------------- #
# Svar från Fortnox efter godkännande (?code=...&state=...)
# --------------------------------------------------------------------------- #
qp = st.query_params
if "code" in qp or "error" in qp:
    # Felet sparas i databasen så att det syns efter omladdningen (även i en annan flik)
    if "error" in qp:
        D.meta_set("oauth_error", f"Fortnox svarade: {qp.get('error')}"
                   + (f" – {qp.get('error_description')}" if qp.get("error_description") else ""))
    elif qp.get("state") != (D.meta_get("oauth_state") or "#"):
        D.meta_set("oauth_error", "Svaret från Fortnox hörde till ett äldre försök. Klicka på 'Koppla Fortnox' igen.")
    else:
        try:
            with st.spinner("Slutför kopplingen till Fortnox …"):
                tenant, name = fc.exchange_code(settings(), qp["code"], app_url())
            D.meta_set("tenant_id", tenant)
            if name:
                D.meta_set("company", name)
            D.meta_set("oauth_state", "")
            D.meta_set("oauth_error", "")
            st.session_state.flash = f"Kopplat till Fortnox{': ' + name if name else ''}!"
        except Exception as e:
            D.meta_set("oauth_error", f"Kopplingen misslyckades: {e}")
    st.query_params.clear()
    st.rerun()

if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))


# --------------------------------------------------------------------------- #
# Guiden
# --------------------------------------------------------------------------- #
def step_header(n, title):
    st.title("GAP-analys – installation")
    st.progress(n / 4, text=f"Steg {n} av 4 · {title}")


def step1_integration(s):
    step_header(1, "Skapa integrationen i Fortnox")
    url = st.text_input("Appens adress (den du ser i webbläsarens adressfält)", value=app_url(),
                        help="Behövs för att Fortnox ska kunna skicka tillbaka dig hit efter godkännandet.")
    if url and url.rstrip("/") != D.meta_get("app_url"):
        D.meta_set("app_url", url.rstrip("/"))
    st.markdown(f"""
1. Öppna Fortnox Developer Portal och skapa en ny integration.
2. Ange **Redirect URI** exakt så här:""")
    st.code(url.rstrip("/") or "https://<er-app>.streamlit.app", language=None)
    st.markdown(f"""
3. Kryssa i behörigheterna: **{SCOPE_TEXT}**. Appen läser bara – den ändrar aldrig något i Fortnox.
4. Kopiera **Client ID** och **Client Secret** och lägg in dem i appens **Settings → Secrets** här på Streamlit:""")
    st.code('FORTNOX_CLIENT_ID = "..."\nFORTNOX_CLIENT_SECRET = "..."', language="toml")
    st.link_button("Öppna Fortnox Developer Portal", FORTNOX_DEV)
    st.caption("När du sparar Secrets startar appen om och fortsätter till nästa steg.")


def step2_connect(s):
    step_header(2, "Koppla Fortnox")
    st.markdown("En **systemadministratör i Fortnox** behöver godkänna kopplingen en gång. "
                "Klicka på knappen, logga in i Fortnox och godkänn – du skickas sedan tillbaka hit.")
    state = D.meta_get("oauth_state")
    if not state:
        state = secrets.token_urlsafe(16)
        D.meta_set("oauth_state", state)
    if not app_url():
        st.warning("Appens adress saknas – fyll i den i steg 1.")
        return
    err = D.meta_get("oauth_error") or ""
    if err:
        st.error(err)
        low = err.lower()
        if "redirect" in low:
            st.info(f"Kontrollera att Redirect URI i Fortnox Developer Portal är exakt **{app_url()}** "
                    "(utan snedstreck på slutet).")
        elif "scope" in low:
            st.info(f"Kontrollera att integrationen i Fortnox har behörigheterna: {SCOPE_TEXT}.")
        elif "access_denied" in low or "denied" in low:
            st.info("Kopplingen nekades. Den som godkänner måste vara systemadministratör i Fortnox.")
        elif "invalid_client" in low or "401" in low:
            st.info("Client ID eller Client Secret stämmer inte – kontrollera dem i appens Secrets.")
    st.link_button("Koppla Fortnox", fc.auth_url(s, app_url(), state), type="primary")
    st.caption(f"Redirect URI i Fortnox måste vara exakt: {app_url()}")


@st.cache_data(ttl=600, show_spinner="Hämtar några artiklar från Fortnox …")
def samples(tenant):
    return fc.article_samples(settings(), 6)


PREFERRED = ["Manufacturer", "SalesAccount", "Type", "Unit", "SupplierName", "SupplierNumber",
             "Note", "ArticleNumber", "Description", "EAN", "StockPlace"]


def step3_category(s, is_change=False):
    if not is_change:
        step_header(3, "Välj kategorifält")
    else:
        st.title("Byt kategorifält")
    try:
        arts = samples(s["tenant_id"])
    except Exception as e:
        st.error(f"Kunde inte hämta artiklar från Fortnox: {e}")
        return
    if not arts:
        st.warning("Hittade inga artiklar i Fortnox.")
        return
    fields = []
    for a in arts:
        for k, v in a.items():
            if k not in fields and v not in (None, "", False) and not isinstance(v, (dict, list)) and not k.startswith("@"):
                fields.append(k)
    fields.sort(key=lambda f: (PREFERRED.index(f) if f in PREFERRED else 99, f))

    st.markdown("Här är några av era artiklar. Leta upp **raden där produktkategorin står**.")
    table = {f: [str(a.get(f, "") or "") for a in arts] for f in fields}
    st.dataframe({"Fält": fields, **{f"Artikel {i + 1}": [table[f][i] for f in fields] for i in range(len(arts))}},
                 hide_index=True, use_container_width=True, height=min(38 * len(fields) + 40, 520))

    cur = s["kategori"]
    c1, c2 = st.columns([2, 1])
    falt = c1.selectbox("Fält som innehåller kategorin", fields,
                        index=fields.index(cur["falt"]) if cur["falt"] in fields else 0)
    m = __import__("re").match(r"^\^\(\.\{(\d+)\}\)$", cur.get("regex") or "")
    n = c2.number_input("Använd bara de första … tecknen (0 = hela värdet)", 0, 50, int(m.group(1)) if m else 0)
    regex = f"^(.{{{n}}})" if n else None
    excl = st.text_input("Artikelnummer som inte ska räknas, t.ex. frakt (kommaseparerade)",
                         ", ".join(map(str, s.get("exkludera_artiklar", []))))
    preview = sorted({fc.category_for(a, {**cur, "falt": falt, "regex": regex, "mappning": {}}) for a in arts})
    st.caption("Kategorier bland dessa artiklar: " + ", ".join(preview))

    if st.button("Spara" + ("" if is_change else " och starta första hämtningen"), type="primary"):
        changed = falt != cur["falt"]
        fc.save_settings(D, {"kategori": {"falt": falt, "regex": regex, "mappning": {}, "saknas": "Okategoriserad"},
                             "exkludera_artiklar": [x.strip() for x in excl.split(",") if x.strip()]})
        if changed:
            rows = D.all("SELECT json FROM articles LIMIT 20")
            if rows and not any(falt in json.loads(r[0]) for r in rows):
                D.execute("UPDATE articles SET detailed=0")
                D.commit()
        if D.one("SELECT 1 FROM report WHERE id=1"):
            fc.save_report(D)
        st.session_state.pop("change_category", None)
        hamta_rapport.clear()
        force_sync_soon()
        st.rerun()


@st.fragment(run_every=5)
def progress_box(first_time):
    msg = D.meta_get("sync_progress") or "Startar …"
    err = D.meta_get("sync_error") or ""
    if err:
        st.error(f"Senaste hämtningen misslyckades: {err}. Appen försöker igen automatiskt.")
    if first_time:
        st.info(f"**Första hämtningen från Fortnox pågår.** {msg}\n\n"
                "Fortnox tillåter 25 anrop per 5 sekunder, så fyra års fakturor tar en stund "
                "(ca 15 min per 4 000 fakturor). Du kan stänga sidan – det fortsätter ändå.")
    if D.one("SELECT 1 FROM report WHERE id=1") and not st.session_state.get("had_report"):
        st.session_state.had_report = True
        hamta_rapport.clear()
        st.rerun()


def step4_first_sync():
    step_header(4, "Första hämtningen")
    WAKE.set()
    progress_box(True)


# --------------------------------------------------------------------------- #
# Rapporten
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=60, show_spinner=False)
def hamta_rapport():
    return fc.load_report(D)


def radata_csv(d):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Kundnr", "Kund", "Ort", "Kategori", "År", "Hela året", "Samma period (YTD)"])
    for c, k, y, full, ytd in d["cells"]:
        nr, name, city, _ = d["customers"][c]
        w.writerow([nr, name, city, d["categories"][k], d["years"][y], full, ytd])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def show_report(ds):
    st.session_state.had_report = True
    first_running = not D.meta_get("last_sync_fortnox")
    left, a, b, c = st.columns([6, 1.3, 1.3, 0.5])
    with left:
        st.caption(f"Senast synkad mot Fortnox: {ds['generated']} · uppdateras automatiskt")
    with a:
        st.download_button("Ladda ner rådata", radata_csv(ds), file_name=f"gap-radata-{ds['today']}.csv",
                           mime="text/csv", use_container_width=True)
    with b:
        if st.button("Hämta senaste nu", use_container_width=True):
            ok = False
            with st.spinner("Hämtar nytt från Fortnox …"):
                try:
                    ok = fc.sync()
                except Exception as e:
                    ok = None
                    st.toast(f"Kunde inte nå Fortnox just nu – visar senaste data. ({e})")
            if ok:
                hamta_rapport.clear()
                st.rerun()
            elif ok is False:
                st.toast("En hämtning pågår redan – nya siffror kommer inom några minuter.")
    with c:
        with st.popover("⚙", use_container_width=True):
            s = settings()
            st.markdown(f"**Kategorifält:** {s['kategori']['falt']}"
                        + (f" (första {s['kategori']['regex'][4:-2]} tecknen)" if s['kategori'].get('regex') else ""))
            if st.button("Byt kategorifält"):
                st.session_state.change_category = True
                st.rerun()
            st.divider()
            st.caption("Koppla om Fortnox, t.ex. om kopplingen har tagits bort i Fortnox.")
            if st.button("Koppla om Fortnox"):
                D.meta_set("tenant_id", "")
                D.meta_set("oauth_state", "")
                st.rerun()
    if first_running or D.meta_get("sync_error"):
        progress_box(first_running)
    html = fc.render_html(ds)
    if hasattr(st, "iframe"):
        st.iframe(html, height=1150)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=1150, scrolling=True)


# --------------------------------------------------------------------------- #
# Vad ska visas?
# --------------------------------------------------------------------------- #
s = settings()
ds = hamta_rapport()

if not (s["client_id"] and s["client_secret"]):
    step1_integration(s)
elif not s["tenant_id"]:
    step2_connect(s)
elif "kategori" not in chosen_settings():
    step3_category(s)
elif st.session_state.get("change_category"):
    step3_category(s, is_change=True)
    if st.button("Avbryt"):
        st.session_state.pop("change_category")
        st.rerun()
elif not ds:
    step4_first_sync()
else:
    show_report(ds)
