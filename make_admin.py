import sys

from config import Config
from models import build_db_from_config


def main():
    args = sys.argv[1:]
    if not args or len(args) > 2:
        print("Usage: python make_admin.py <email> [--revoke]")
        sys.exit(1)

    email = args[0].strip().lower()
    revoke = "--revoke" in args[1:]

    db = build_db_from_config(Config)
    user = db.get_user_by_email(email)
    if not user:
        print(f"No user found with email {email}")
        sys.exit(1)

    db.update_user(user["user_id"], is_admin=not revoke)
    if revoke:
        print(f"{email} is no longer an admin")
    else:
        print(f"{email} is now aan admin")


if __name__ == "__main__":
    main()
