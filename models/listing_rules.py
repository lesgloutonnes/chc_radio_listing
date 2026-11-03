# -*- coding: utf-8 -*-
"""Règles métier du listing, indépendantes du registre Odoo."""

MATERIELS = [
    "RX & Med Nuc",
    "Autres disciplines",
    "Imprimantes",
    "Stations PACS",
]
STATION_MODALITE = "Stations PACS"
LEGACY_OS = "WIN"
OS_VALUES = ("WIN 10", "WIN 11", "Linux", LEGACY_OS)

_OS_ALIASES = {
    "win 10": "WIN 10",
    "win10": "WIN 10",
    "windows 10": "WIN 10",
    "windows10": "WIN 10",
    "win 11": "WIN 11",
    "win11": "WIN 11",
    "windows 11": "WIN 11",
    "windows11": "WIN 11",
    "linux": "Linux",
    "win": LEGACY_OS,
    "windows": LEGACY_OS,
    "win (à préciser)": LEGACY_OS,
    "win (a preciser)": LEGACY_OS,
}

LEGACY_OS_ERROR = (
    "L'OS « WIN » doit être précisé (WIN 10 ou WIN 11) avant l'enregistrement."
)


def _txt(value):
    if value is None or value is False:
        return ""
    return str(value).strip()


def normalize_os(os_val):
    if os_val is None or os_val is False:
        return False
    raw = str(os_val).strip()
    if not raw:
        return False
    if raw in OS_VALUES:
        return raw
    return _OS_ALIASES.get(raw.lower(), raw)


def normalize_materiel(value):
    materiel = _txt(value) or "RX & Med Nuc"
    if materiel not in MATERIELS:
        return "RX & Med Nuc"
    return materiel


def validate_payload(body):
    """Retourne un message d'erreur, ou None si la saisie peut être enregistrée.

    ``body`` utilise les clés de l'API HTML (``numeroInventaire``,
    ``carteGraphique``, ``modalite``…). Un OS historique ``WIN`` bloque
    toujours l'enregistrement. Les champs vides d'une fiche « en attente »
    restent tolérés.
    """
    if not isinstance(body, dict):
        body = {}
    os_val = normalize_os(body.get("os") or False)
    if os_val == LEGACY_OS:
        return LEGACY_OS_ERROR

    statut = _txt(body.get("statut")) or "en_service"
    if statut == "en_attente":
        return None

    materiel = normalize_materiel(
        body.get("modalite") or body.get("materiel") or body.get("equipement")
    )
    if materiel == STATION_MODALITE:
        checks = [
            ("site", "Le site est obligatoire."),
            ("aet", "L'AET est obligatoire."),
            ("service", "Le service est obligatoire."),
            ("salle", "La salle / localisation est obligatoire."),
            ("numeroInventaire", "Le n° CHC est obligatoire."),
            ("marque", "La marque est obligatoire."),
            ("modele", "Le modèle est obligatoire."),
        ]
        for key, message in checks:
            if not _txt(body.get(key)):
                return message
        if not os_val:
            return "L'OS est obligatoire."
        if not _txt(body.get("carteGraphique")):
            return "La carte graphique est obligatoire."
        if not _txt(body.get("ecran")):
            return "L'écran est obligatoire."
        return None

    if not _txt(body.get("site")):
        return "Le site est obligatoire."
    if not _txt(body.get("aet")):
        return "L'AET est obligatoire."
    if not _txt(body.get("ip")):
        return "L'IP est obligatoire."
    if not _txt(body.get("mac")):
        return "La MAC est obligatoire."
    return None
