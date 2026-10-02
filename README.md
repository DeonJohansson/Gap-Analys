# GAP-analys – kom igång

Det mesta av installationen sker i appen, som en guide med knappar. Du behöver inte installera något på din dator.

## 1. Koden på GitHub
Filerna ska ligga i det privata repositoryt `DeonJohansson/Gap-Analys`.

## 2. Databas (Neon)
Skapa ett gratiskonto på **neon.tech** och skapa ett projekt med regionen **Frankfurt**. Kopiera sedan **connection string**, som börjar med `postgresql://`.

## 3. Publicera appen (Streamlit)
1. Gå till **share.streamlit.io** och logga in med GitHub.
2. Klicka på **Create app**, välj repositoryt `DeonJohansson/Gap-Analys` och ange `streamlit_app.py` som fil.
3. Välj en adress, till exempel `optinord-gap`.
4. Öppna **Advanced settings**, välj Python **3.12** och klistra in följande under **Secrets**:
   ```
   DATABASE_URL = "postgresql://..."
   ```
5. Klicka på **Deploy**.

## 4. Följ guiden i appen
Guiden i appen tar dig igenom resten:

1. **Skapa integrationen i Fortnox.** Appen visar exakt vilken redirect-adress och vilka behörigheter du ska ange. Klistra sedan in Client ID och Client Secret i appens Secrets.
2. **Koppla Fortnox.** Klicka på knappen. En systemadministratör i Fortnox godkänner kopplingen.
3. **Välj kategorifält.** Appen visar era artiklar, och du väljer i en lista vilket fält som är kategorin.
4. **Första hämtningen.** Den startar automatiskt och tar cirka 15 minuter per 4 000 fakturor. Du kan stänga sidan under tiden.

## 5. Begränsa åtkomsten
- I Streamlit kan du under **Share** begränsa vilka som får se appen.
- Du kan också lägga till ett lösenord för appen i Secrets:
  ```
  APP_LOSENORD = "..."
  ```

---

### Valfritt: synk även när appen sover
Appen synkar själv var 15:e minut så länge den är igång. Gratisappar på Streamlit somnar dock efter en tids inaktivitet. När appen väcks visas den senaste datan direkt, och det nya hämtas inom någon minut.

Vill du att datan alltid ska vara färsk direkt kan du lägga in Secrets även i GitHub:
1. Gå till repositoryt och öppna **Settings → Secrets and variables → Actions**.
2. Lägg in `FORTNOX_CLIENT_ID`, `FORTNOX_CLIENT_SECRET` och `DATABASE_URL`.

Då synkar GitHub varje timme kl. 06–19 på vardagar.

### Bra att veta
- Beloppen är exkl. moms och i SEK.
- Makulerade fakturor räknas inte med, och krediter dras av.
- Rader utan artikelnummer ingår inte.
- Kategorifältet kan bytas när som helst via ⚙ uppe till höger i appen.
