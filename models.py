import secrets
from datetime import datetime, timezone

from pymysqlhelper import Database, LocalDatabase, Text, Boolean, DateTime, String

from config import Config


def _new_id(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LifeLinkDB:

    def __init__(self, backend: str = "sqlite", **kwargs):
        if backend == "mysql":
            self.db = Database(
                username=kwargs["username"],
                password=kwargs["password"],
                host=kwargs["host"],
                port=kwargs["port"],
                database=kwargs["database"],
            )
        else:
            self.db = LocalDatabase(db_path=kwargs.get("db_path", "lifelinkne.db"))

        self._define_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _define_tables(self):
        self.db.define_table(
            "users",
            user_id=String(64),          # primary key
            username=Text,
            email=String(255),
            password_hash=Text,
            birthday=String(32),
            disabilities=Text,
            home_location=String(64),    # "lat, lon"
            exact_location=String(64),   # "lat, lon"
            is_admin=Boolean,
            is_health_worker=Boolean,
            blood_group=String(64),
            diseases=Text,
            allergies=Text,
            important_contacts=Text,
            created_at=String(64),
        )

        # Generalized disaster reports -- floods, earthquakes, landslides,
        # etc. Replaces the old flood-only "flood_reports" table.
        self.db.define_table(
            "disasters",
            disaster_id=String(64),      # primary key
            reporter_id=String(64),
            reporter_name=Text,
            location=String(64),
            disaster=String(128),
            severity=String(16),         # "Severe" | "Moderate" | "Mild"
            notes=Text,
            reported_at=String(64),
        )

        # Blood donation network -- people signing up as available donors.
        # (Intentionally no blood *request* table -- donation network only.)
        self.db.define_table(
            "blood_donations",
            id=String(64),               # primary key
            user_id=String(64),
            name=Text,
            location=String(64),
            blood_type=String(64),
            contact=String(64),
            created_at=String(64),
        )

        self.db.define_table(
            "api_tokens",
            token=String(64),            # primary key
            user_id=String(64),
            created_at=String(64),
        )

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    def get_user_by_email(self, email: str):
        return self.db.get("users", email=email.strip().lower())

    def get_user_by_id(self, user_id: str):
        return self.db.get("users", user_id=user_id)

    def email_taken(self, email: str, exclude_user_id: str | None = None) -> bool:
        existing = self.get_user_by_email(email)
        if not existing:
            return False
        if exclude_user_id and existing["user_id"] == exclude_user_id:
            return False
        return True

    def create_user(self, *, username, email, password_hash, birthday,
                     disabilities, home_location, exact_location, blood_group,
                     diseases, allergies, important_contacts, is_admin=False,
                     is_health_worker=False):
        user_id = _new_id()
        self.db.insert(
            "users",
            user_id=user_id,
            username=username,
            email=email.strip().lower(),
            password_hash=password_hash,
            birthday=birthday,
            disabilities=disabilities,
            home_location=home_location,
            exact_location=exact_location,
            is_admin=is_admin,
            is_health_worker=is_health_worker,
            blood_group=blood_group,
            diseases=diseases,
            allergies=allergies,
            important_contacts=important_contacts,
            created_at=_now_iso(),
        )
        return user_id

    def update_user(self, user_id: str, **fields):
        if not fields:
            return
        self.db.update("users", {"user_id": user_id}, fields)

    def search_users_by_name(self, query: str, limit: int = 25):
        """Used by the health-worker "look up a person's health data" tab.
        Case-insensitive substring match on username; never returns the
        password hash."""
        query = (query or "").strip().lower()
        if not query:
            return []
        rows = self.db.search("users")
        matches = [r for r in rows if query in (r.get("username") or "").lower()]
        matches.sort(key=lambda r: (r.get("username") or "").lower())
        return matches[:limit]

    # ------------------------------------------------------------------
    # Disasters
    # ------------------------------------------------------------------
    def list_disasters(self):
        rows = self.db.search("disasters")
        rows.sort(key=lambda r: r.get("reported_at") or "", reverse=True)
        return rows

    def report_disaster(self, *, reporter_id, reporter_name, location,
                         disaster, severity, notes=""):
        disaster_id = _new_id()
        self.db.insert(
            "disasters",
            disaster_id=disaster_id,
            reporter_id=reporter_id,
            reporter_name=reporter_name,
            location=location,
            disaster=disaster,
            severity=severity,
            notes=notes or "",
            reported_at=_now_iso(),
        )
        return disaster_id

    def get_disaster(self, disaster_id: str):
        return self.db.get("disasters", disaster_id=disaster_id)

    def delete_disaster(self, disaster_id: str):
        self.db.delete("disasters", disaster_id=disaster_id)

    def clear_disasters(self):
        self.db.delete("disasters")

    # ------------------------------------------------------------------
    # Blood donation network
    # ------------------------------------------------------------------
    def list_blood_donations(self):
        rows = self.db.search("blood_donations")
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows

    def create_blood_donation(self, *, user_id, name, location, blood_type, contact):
        row_id = _new_id()
        self.db.insert(
            "blood_donations", id=row_id, user_id=user_id, name=name,
            location=location, blood_type=blood_type, contact=contact,
            created_at=_now_iso(),
        )
        return row_id

    def get_blood_donation(self, row_id: str):
        return self.db.get("blood_donations", id=row_id)

    def delete_blood_donation(self, row_id: str):
        self.db.delete("blood_donations", id=row_id)

    def clear_blood_donations(self):
        self.db.delete("blood_donations")

    # ------------------------------------------------------------------
    # API tokens
    # ------------------------------------------------------------------
    def create_api_token(self, user_id: str) -> str:
        token = _new_id(32)
        self.db.insert(
            "api_tokens", token=token, user_id=user_id, created_at=_now_iso(),
        )
        return token

    def get_user_by_token(self, token: str):
        if not token:
            return None
        row = self.db.get("api_tokens", token=token)
        if not row:
            return None
        return self.get_user_by_id(row["user_id"])

    def delete_api_token(self, token: str):
        self.db.delete("api_tokens", token=token)

    def delete_all_tokens_for_user(self, user_id: str):
        self.db.delete("api_tokens", user_id=user_id)


def build_db_from_config(cfg: Config) -> LifeLinkDB:
    if cfg.DB_BACKEND == "mysql":
        return LifeLinkDB(
            backend="mysql",
            username=cfg.MYSQL_USER,
            password=cfg.MYSQL_PASSWORD,
            host=cfg.MYSQL_HOST,
            port=cfg.MYSQL_PORT,
            database=cfg.MYSQL_DATABASE,
        )
    return LifeLinkDB(backend="sqlite", db_path=cfg.SQLITE_PATH)
