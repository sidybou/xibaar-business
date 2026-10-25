"""Collecte automatique des nouvelles d'affaires du Sénégal (Xibaar Business).

Ce programme lit sources.json, interroge Google Actualités pour chaque
recherche, retire les doublons et écrit le résultat dans articles.json.
Il n'utilise que des outils inclus dans Python : rien à installer.
"""
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

with open("sources.json", encoding="utf-8") as f:
    config = json.load(f)

JOURS = config.get("jours", 7)
MAX = config.get("max_articles", 200)
LIMITE = datetime.now(timezone.utc) - timedelta(days=JOURS)


def adresse(recherche):
    params = {"q": f"{recherche} when:{JOURS}d", "hl": "fr", "gl": "SN", "ceid": "SN:fr"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Xibaar Business)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def cle(titre):
    t = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:90]


EXCLURE = []  # rempli plus bas, après la définition de cle()


def exclu(titre):
    """Vrai si le titre contient un mot de la liste « exclure » (faits divers, sport, politique pure)."""
    t = " " + cle(titre) + " "
    return any(" " + m + " " in t for m in EXCLURE)


def lire_flux(contenu, secteur, articles):
    racine = ET.fromstring(contenu)
    for item in racine.iter("item"):
        titre = (item.findtext("title") or "").strip()
        lien = (item.findtext("link") or "").strip()
        el = item.find("source")
        source = (el.text or "").strip() if el is not None else ""
        if source and titre.endswith(" - " + source):
            titre = titre[: -len(" - " + source)].strip()
        try:
            date = parsedate_to_datetime(item.findtext("pubDate"))
        except Exception:
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        k = cle(titre)
        if exclu(titre):
            continue
        if date < LIMITE or not k or not lien.startswith("http") or k in articles:
            continue
        articles[k] = {
            "titre": titre,
            "source": source or "Source",
            "lien": lien,
            "date": date.astimezone(timezone.utc).isoformat(),
            "secteur": secteur,
        }


def main():
    EXCLURE.extend(cle(m) for m in config.get("exclure", []))
    articles = {}
    for s in config["secteurs"]:
        for recherche in s["recherches"]:
            try:
                lire_flux(telecharger(adresse(recherche)), s["id"], articles)
                print(f"OK      {recherche}")
            except Exception as e:
                print(f"ÉCHEC   {recherche} : {e}")
            time.sleep(1)

    if not articles:
        print("Aucun article récupéré : on garde la version précédente.")
        return

    liste = sorted(articles.values(), key=lambda a: a["date"], reverse=True)[:MAX]
    sortie = {
        "maj": datetime.now(timezone.utc).isoformat(),
        "secteurs": [{"id": s["id"], "nom": s["nom"], "couleur": s["couleur"]} for s in config["secteurs"]],
        "articles": liste,
    }
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)
    print(f"{len(liste)} articles enregistrés.")


if __name__ == "__main__":
    main()
