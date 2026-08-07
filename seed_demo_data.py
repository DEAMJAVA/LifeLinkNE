import argparse
import random

from config import Config
from models import build_db_from_config
from data import severity_for_disaster

DEMO_EMAIL = "demo-reporter@lifelinkne.local"
DEMO_NAME = "Demo Reporter"

# (location label, lat, lon, disaster type, count)
# Mostly flood-heavy for the Brahmaputra basin (the historical crisis this
# app was built around), with a scattering of other disaster types so the
# generalized catalog actually shows some variety on the map.
SCENARIO = [
    # --- Assam: Brahmaputra basin, flood-heavy ---
    ("Dhemaji",         27.4833, 94.5667, "Major Flood", 10),
    ("Majuli",          26.9500, 94.1667, "Major Flood", 9),
    ("Barpeta",         26.3220, 91.0060, "Flash Flood", 8),
    ("Dhubri",          26.0200, 89.9800, "Major Flood", 7),
    ("Nagaon",          26.3480, 92.6840, "Flood", 7),
    ("North Lakhimpur", 27.2333, 94.1000, "Flood", 6),
    ("Morigaon",        26.2500, 92.3400, "River Erosion", 6),
    ("Bongaigaon",      26.4800, 90.5500, "Flood", 5),
    ("Golaghat",        26.5100, 93.9700, "Waterlogging", 4),
    ("Kokrajhar",       26.4000, 90.2700, "Flood", 4),
    ("Tinsukia",        27.4900, 95.3600, "Localized Waterlogging", 3),
    ("Jorhat",          26.7509, 94.2037, "Heavy Rainfall", 3),
    ("Dibrugarh",       27.4728, 94.9120, "Bridge/Road Damage", 2),
    ("Guwahati",        26.1445, 91.7362, "Waterlogging", 2),
    ("Silchar",         24.8333, 92.7789, "Flood", 2),

    # --- Other Northeast states: mix of disaster types for contrast ---
    ("Itanagar, Arunachal Pradesh", 27.0844, 93.6053, "Landslide (Minor)", 2),
    ("Pasighat, Arunachal Pradesh", 28.0667, 95.3333, "Landslide (Major)", 1),
    ("Imphal, Manipur",             24.8170, 93.9368, "Earthquake", 2),
    ("Shillong, Meghalaya",         25.5788, 91.8933, "Landslide (Minor)", 2),
    ("Tura, Meghalaya",             25.5138, 90.2027, "Heavy Rainfall", 1),
    ("Aizawl, Mizoram",             23.7271, 92.7176, "Landslide (Major)", 1),
    ("Kohima, Nagaland",            25.6751, 94.1086, "Storm / High Winds", 1),
    ("Gangtok, Sikkim",             27.3389, 88.6065, "Earthquake", 1),
    ("Agartala, Tripura",           23.8315, 91.2868, "Flood", 2),
]

NOTES_BY_DISASTER = {
    "Major Flood": [
        "Embankment breach reported, water entering villages rapidly.",
        "River well above danger level, large-scale evacuation underway.",
    ],
    "Flash Flood": [
        "Flash flood -- multiple homes submerged, people moving to relief camps.",
    ],
    "Flood": [
        "Road submerged near the market, vehicles rerouting.",
        "Water entered a few ground-floor homes near the river.",
    ],
    "Waterlogging": [
        "Minor waterlogging on the main road after last night's rain.",
    ],
    "Localized Waterlogging": [
        "Some low-lying fields flooded, houses still dry.",
    ],
    "River Erosion": [
        "Riverbank eroding fast, a few homes at risk of collapse.",
    ],
    "Heavy Rainfall": [
        "Continuous heavy rain since last night, drainage struggling to keep up.",
    ],
    "Bridge/Road Damage": [
        "Approach road to the bridge washed out, traffic diverted.",
    ],
    "Landslide (Minor)": [
        "Small landslip blocking one lane, being cleared.",
    ],
    "Landslide (Major)": [
        "Major landslide -- road fully blocked, some houses damaged.",
    ],
    "Earthquake": [
        "Moderate tremors felt, minor cracks in a few older buildings.",
    ],
    "Storm / High Winds": [
        "High winds have downed several trees and power lines.",
    ],
}


def _jitter(lat, lon):
    return (
        lat + random.uniform(-0.045, 0.045),
        lon + random.uniform(-0.045, 0.045),
    )


def get_or_create_demo_user(db):
    user = db.get_user_by_email(DEMO_EMAIL)
    if user:
        return user["user_id"]
    return db.create_user(
        username=DEMO_NAME,
        email=DEMO_EMAIL,
        password_hash="!",  # not a real login-capable account
        birthday="",
        disabilities="",
        home_location="26.1445, 91.7362",
        exact_location="26.1445, 91.7362",
        blood_group="",
        diseases="",
        allergies="",
        important_contacts="",
        is_admin=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true",
                         help="Delete existing disaster reports before seeding.")
    args = parser.parse_args()

    db = build_db_from_config(Config)

    if args.clear:
        db.clear_disasters()
        print("Cleared existing disaster reports.")

    reporter_id = get_or_create_demo_user(db)

    total = 0
    for label, lat, lon, disaster, count in SCENARIO:
        for _ in range(count):
            jlat, jlon = _jitter(lat, lon)
            notes = random.choice(NOTES_BY_DISASTER.get(disaster, [""]))
            db.report_disaster(
                reporter_id=reporter_id,
                reporter_name=DEMO_NAME,
                location=f"{jlat:.4f}, {jlon:.4f}",
                disaster=disaster,
                severity=severity_for_disaster(disaster),
                notes=notes,
            )
            total += 1

    print(f"Seeded {total} demo disaster reports across Northeast India.")
    print("Log in and open the Disaster Intensity Map to see it.")


if __name__ == "__main__":
    main()
