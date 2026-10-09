from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


def main() -> int:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        print("Database connectivity check failed.")
        return 1

    print("Database connectivity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
