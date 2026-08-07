LOCATIONS = [
    # --- Assam (deep coverage) ---
    ("Guwahati", "Assam", "26.1445, 91.7362"),
    ("Dibrugarh", "Assam", "27.4728, 94.9120"),
    ("Jorhat", "Assam", "26.7509, 94.2037"),
    ("Silchar", "Assam", "24.8333, 92.7789"),
    ("Nagaon", "Assam", "26.3480, 92.6840"),
    ("Dhemaji", "Assam", "27.4833, 94.5667"),
    ("North Lakhimpur", "Assam", "27.2333, 94.1000"),
    ("Barpeta", "Assam", "26.3220, 91.0060"),
    ("Majuli", "Assam", "26.9500, 94.1667"),
    ("Tinsukia", "Assam", "27.4900, 95.3600"),
    ("Golaghat", "Assam", "26.5100, 93.9700"),
    ("Morigaon", "Assam", "26.2500, 92.3400"),
    ("Bongaigaon", "Assam", "26.4800, 90.5500"),
    ("Dhubri", "Assam", "26.0200, 89.9800"),
    ("Kokrajhar", "Assam", "26.4000, 90.2700"),

    # --- Other Northeast states ---
    ("Itanagar", "Arunachal Pradesh", "27.0844, 93.6053"),
    ("Pasighat", "Arunachal Pradesh", "28.0667, 95.3333"),
    ("Imphal", "Manipur", "24.8170, 93.9368"),
    ("Churachandpur", "Manipur", "24.3333, 93.6667"),
    ("Shillong", "Meghalaya", "25.5788, 91.8933"),
    ("Tura", "Meghalaya", "25.5138, 90.2027"),
    ("Aizawl", "Mizoram", "23.7271, 92.7176"),
    ("Lunglei", "Mizoram", "22.8833, 92.7333"),
    ("Kohima", "Nagaland", "25.6751, 94.1086"),
    ("Dimapur", "Nagaland", "25.9091, 93.7266"),
    ("Gangtok", "Sikkim", "27.3389, 88.6065"),
    ("Namchi", "Sikkim", "27.1667, 88.3667"),
    ("Agartala", "Tripura", "23.8315, 91.2868"),
    ("Udaipur", "Tripura", "23.5333, 91.4833"),
]

NE_STATES = [
    "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Sikkim", "Tripura",
]

LOCATION_CHOICES = [f"{name} ({state})" for name, state, _ in LOCATIONS]
LOCATION_BY_LABEL = {f"{name} ({state})": latlon for name, state, latlon in LOCATIONS}
LOCATION_BY_LATLON = {latlon: f"{name} ({state})" for name, state, latlon in LOCATIONS}

# Roughly centers the Leaflet map on the Northeast India region.
NE_INDIA_MAP_CENTER = (26.3, 92.5)
NE_INDIA_MAP_DEFAULT_ZOOM = 7


def location_display_name(latlon: str) -> str:
    return LOCATION_BY_LATLON.get((latlon or "").strip(), latlon or "Unknown location")


BLOOD_GROUPS = [
    "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-",
]

# Disaster catalog: NE India is flood-prone (Brahmaputra/Barak basins), but
# also sees earthquakes, landslides, and other hazards, so the reporting
# system now covers disasters generally rather than floods only. Every
# disaster type maps to one of three severities, which drives badge color
# and the intensity-map heat weight.
DISASTER_CATALOG = {
    "Severe": [
        "Major Flood", "Flash Flood", "Earthquake", "Embankment Breach",
        "Cyclone", "Landslide (Major)", "Building Collapse",
        "Large-Scale Industrial Fire", "Dam Failure", "Epidemic Outbreak",
    ],
    "Moderate": [
        "Flood", "Waterlogging", "Landslide (Minor)", "Heavy Rainfall",
        "Bridge/Road Damage", "Power Grid Failure", "River Erosion",
        "Storm / High Winds",
    ],
    "Mild": [
        "Localized Waterlogging", "Minor Roadblock", "Lightning Strike",
        "Small Fire", "Hailstorm", "Minor Infrastructure Damage",
    ],
}

SEVERITY_COLORS = {
    "Severe": "#e74c3c",    # red
    "Moderate": "#f1a208",  # amber/orange
    "Mild": "#2ecc71",      # green
}

# Used for the intensity-map heat layer -- same spirit as the old
# per-flood-level "weight" but keyed by severity bucket instead.
SEVERITY_WEIGHTS = {
    "Severe": 4,
    "Moderate": 2,
    "Mild": 1,
}

DISASTER_TO_SEVERITY = {
    d: sev for sev, disasters in DISASTER_CATALOG.items() for d in disasters
}


def severity_for_disaster(disaster_name: str) -> str:
    return DISASTER_TO_SEVERITY.get(disaster_name, "Mild")


def severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(severity, "#888")


def severity_weight(severity: str) -> int:
    return SEVERITY_WEIGHTS.get(severity, 1)
