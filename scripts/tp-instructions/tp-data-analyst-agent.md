# TP Data Analyst Agent — Guide de l'étudiant

## Objectif
Apprendre à analyser des données avec Python/Pandas en utilisant un agent IA comme assistant. L'agent exécute le code dans un terminal sandbox.

## Prérequis
- Accès à la plateforme Open WebUI
- Notions de base en Python (variables, boucles, fonctions)
- Curiosité pour la data science

## Comment démarrer
1. Connectez-vous à Open WebUI
2. Sélectionnez le modèle **TP Data Analyst Agent**
3. Envoyez : "Bonjour, les datasets sont dans ~/datasets/. On commence ?"
4. Le tuteur explore les données et vous guide pas à pas

## Datasets disponibles

### ventes_ecommerce.csv (1000 lignes)
Données de ventes d'un site e-commerce sur l'année 2024.
| Colonne | Description | Exemple |
|---------|-------------|---------|
| id | Identifiant unique | 1 |
| date | Date de vente | 2024-05-20 |
| produit | Nom du produit | Laptop Pro |
| categorie | Catégorie | Électronique |
| region | Région française | PACA |
| montant | Montant en euros | 527.14 |
| quantite | Quantité vendue | 4 |

### donnees_rh.csv (500 lignes)
Données anonymisées de ressources humaines d'une entreprise.
| Colonne | Description | Exemple |
|---------|-------------|---------|
| employe_id | Identifiant | 1 |
| nom | Nom complet | Jean Martin |
| departement | Département | Engineering |
| salaire | Salaire annuel | 55000 |
| anciennete | Années | 8 |
| evaluation | Note /5 | 4.2 |
| genre | M/F | M |
| ville | Ville | Paris |

> Note : ~5% des évaluations sont manquantes (pour pratiquer le nettoyage de données)

### logs_web.csv (2000 lignes)
Logs de navigation sur un site web pendant 30 jours (juin 2024).
| Colonne | Description | Exemple |
|---------|-------------|---------|
| timestamp | Date et heure | 2024-06-15 14:32:01 |
| page | URL visitée | /produits |
| user_id | Identifiant utilisateur | user_42 |
| duree_sec | Durée de visite (sec) | 45.3 |
| device | Appareil | Mobile |
| status_code | Code HTTP | 200 |
| referrer | Source du trafic | Google |

## Programme (5 modules progressifs)

### Module 1 — Exploration de données (⭐)
- Charger un CSV avec `pd.read_csv()`
- Utiliser `head()`, `shape`, `dtypes`, `describe()`, `value_counts()`
- **Défi** : Explorer le dataset ventes et identifier 3 insights

### Module 2 — Questions en langage naturel → Pandas (⭐⭐)
- Traduire des questions business en code Pandas
- Exemples : "Top 5 produits par CA", "Ventes par région", "Évolution mensuelle"
- **Défi** : Poser 5 questions business et écrire le code Pandas correspondant

### Module 3 — Nettoyage et transformation (⭐⭐)
- Gérer les valeurs manquantes (`fillna`, `dropna`)
- Supprimer les doublons, corriger les types
- Créer des colonnes dérivées (mois, trimestre, panier moyen)
- **Défi** : Préparer le dataset RH pour une analyse salariale

### Module 4 — Visualisation automatisée (⭐⭐⭐)
- Créer des graphiques avec matplotlib/seaborn
- Types : barplot, lineplot, heatmap, scatter
- Sauvegarder en PNG (`plt.savefig()`)
- **Défi** : Créer un dashboard de 4 graphiques pour le directeur commercial

### Module 5 — Pipeline agent complet (⭐⭐⭐⭐)
- Chaîner les étapes : chargement → nettoyage → analyse → visualisation → rapport
- Orchestrer un pipeline d'analyse de bout en bout
- **Défi final** : Analyser le dataset logs_web et produire un rapport complet

## Commandes Python essentielles

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Charger
df = pd.read_csv('~/datasets/ventes_ecommerce.csv')

# Explorer
df.head()
df.shape
df.dtypes
df.describe()
df['categorie'].value_counts()

# Filtrer
df[df['montant'] > 500]
df[df['region'] == 'PACA']

# Grouper
df.groupby('categorie')['montant'].sum()
df.groupby(['region', 'categorie'])['montant'].mean()

# Visualiser
df.groupby('categorie')['montant'].sum().plot(kind='bar')
plt.savefig('graphique.png')
```

## Évaluation
- Chaque défi est évalué par le tuteur
- Critères : exactitude du code, pertinence des insights, qualité des visualisations

## Commandes utiles
- Tapez **"aide"** ou **"indice"** si vous bloquez
- Tapez **"solution"** pour voir la réponse complète
- Tapez **"module suivant"** pour avancer
- Tapez **"change de dataset"** pour travailler sur un autre jeu de données

## Durée estimée
- 3 à 4 heures pour les 5 modules
- Modules 1-2 : session 1 (découverte)
- Modules 3-5 : session 2 (approfondissement)
