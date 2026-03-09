#!/usr/bin/env python3
"""Generate sample CSV datasets for TP Data Analyst Agent exercises."""

import csv
import random
import os
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
random.seed(42)


def generate_ecommerce_sales(n=1000):
    """Ventes e-commerce: id, date, produit, categorie, region, montant, quantite."""
    products = {
        "Électronique": ["Laptop Pro", "Smartphone X", "Casque Audio", "Tablette 10", "Clé USB 64Go", "Webcam HD"],
        "Vêtements": ["T-shirt Coton", "Jean Slim", "Veste Sport", "Sneakers Urban", "Écharpe Laine"],
        "Maison": ["Lampe LED", "Coussin Déco", "Tasse Design", "Plante Verte", "Cadre Photo"],
        "Livres": ["Roman Policier", "Guide Python", "BD Manga", "Livre Cuisine", "Atlas Monde"],
    }
    regions = ["Île-de-France", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Bretagne", "PACA"]
    start = datetime(2024, 1, 1)

    rows = []
    for i in range(1, n + 1):
        cat = random.choice(list(products.keys()))
        prod = random.choice(products[cat])
        region = random.choice(regions)
        date = start + timedelta(days=random.randint(0, 364))
        qty = random.randint(1, 10)
        base_price = {"Électronique": 150, "Vêtements": 45, "Maison": 25, "Livres": 18}[cat]
        montant = round(base_price * qty * random.uniform(0.7, 1.5), 2)
        rows.append([i, date.strftime("%Y-%m-%d"), prod, cat, region, montant, qty])

    path = os.path.join(SCRIPT_DIR, "ventes_ecommerce.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "date", "produit", "categorie", "region", "montant", "quantite"])
        w.writerows(rows)
    print(f"✅ {path} — {n} lignes")
    return path


def generate_hr_data(n=500):
    """Données RH: employe_id, nom, departement, salaire, anciennete, evaluation, genre, ville."""
    prenoms_m = ["Jean", "Pierre", "Marc", "Thomas", "Nicolas", "Julien", "Lucas", "Hugo", "Maxime", "Alexandre"]
    prenoms_f = ["Marie", "Sophie", "Julie", "Camille", "Emma", "Léa", "Chloé", "Manon", "Clara", "Alice"]
    noms = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau",
            "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier"]
    departements = ["Engineering", "Marketing", "Finance", "RH", "Commercial", "Support", "Direction"]
    villes = ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux", "Lille", "Nantes", "Strasbourg"]
    sal_ranges = {
        "Engineering": (42000, 85000), "Marketing": (35000, 65000), "Finance": (40000, 75000),
        "RH": (33000, 60000), "Commercial": (32000, 70000), "Support": (28000, 45000), "Direction": (70000, 130000),
    }

    rows = []
    for i in range(1, n + 1):
        genre = random.choice(["M", "F"])
        prenom = random.choice(prenoms_m if genre == "M" else prenoms_f)
        nom = random.choice(noms)
        dept = random.choice(departements)
        anc = random.randint(0, 25)
        lo, hi = sal_ranges[dept]
        salaire = round(random.uniform(lo, hi) + anc * random.uniform(500, 1500), 0)
        evaluation = round(random.gauss(3.5, 0.8), 1)
        evaluation = max(1.0, min(5.0, evaluation))
        ville = random.choice(villes)
        # ~5% missing values for evaluation
        eval_str = "" if random.random() < 0.05 else str(evaluation)
        rows.append([i, f"{prenom} {nom}", dept, int(salaire), anc, eval_str, genre, ville])

    path = os.path.join(SCRIPT_DIR, "donnees_rh.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["employe_id", "nom", "departement", "salaire", "anciennete", "evaluation", "genre", "ville"])
        w.writerows(rows)
    print(f"✅ {path} — {n} lignes")
    return path


def generate_web_logs(n=2000):
    """Logs web: timestamp, page, user_id, duree_sec, device, status_code, referrer."""
    pages = ["/", "/produits", "/produits/detail", "/panier", "/checkout", "/compte", "/aide",
             "/blog", "/blog/article", "/contact", "/api/search"]
    devices = ["Desktop", "Mobile", "Tablet"]
    referrers = ["Google", "Direct", "Facebook", "Email", "Twitter", "LinkedIn", "Autre"]
    status_codes = [200, 200, 200, 200, 200, 301, 404, 500]  # weighted toward 200

    start = datetime(2024, 6, 1)
    rows = []
    for i in range(n):
        ts = start + timedelta(seconds=random.randint(0, 30 * 24 * 3600))
        page = random.choice(pages)
        uid = f"user_{random.randint(1, 300)}"
        device = random.choices(devices, weights=[50, 40, 10])[0]
        duree = round(random.expovariate(1 / 45), 1)  # mean ~45s
        duree = max(0.5, min(600, duree))
        status = random.choice(status_codes)
        ref = random.choice(referrers)
        rows.append([ts.strftime("%Y-%m-%d %H:%M:%S"), page, uid, duree, device, status, ref])

    # Sort by timestamp
    rows.sort(key=lambda r: r[0])

    path = os.path.join(SCRIPT_DIR, "logs_web.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "page", "user_id", "duree_sec", "device", "status_code", "referrer"])
        w.writerows(rows)
    print(f"✅ {path} — {n} lignes")
    return path


if __name__ == "__main__":
    generate_ecommerce_sales()
    generate_hr_data()
    generate_web_logs()
    print("\n📊 Tous les datasets ont été générés.")
