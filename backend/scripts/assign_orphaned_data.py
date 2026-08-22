"""Assigns every document/conversation with a NULL user_id to a given user.

Needed after 52842fc8bb30_add_users_table_and_user_id_ownership_.py: that
migration adds user_id as nullable (not backfilled), since documents and
conversations created before accounts existed have no real owner. Those
rows are invisible to every user until explicitly claimed — every list/get/
delete query filters by user_id (see app/db/crud.py), so a NULL owner is
simply inaccessible, not a data-integrity problem.

Resumable / idempotent by construction: always selects rows WHERE
user_id IS NULL, so re-running after an interruption only ever touches
whatever is still unclaimed — already-assigned rows are never revisited.

Usage (run from backend/, with the same DATABASE_URL as the target
environment):

    python -m scripts.assign_orphaned_data --email you@example.com
    python -m scripts.assign_orphaned_data --email you@example.com --dry-run
"""
import argparse

from app.db import crud
from app.db.models import Conversation, Document
from app.db.session import SessionLocal


def assign_orphaned_data(*, email: str, dry_run: bool) -> None:
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, email)
        if user is None:
            print(f"[assign] no account found for {email!r} — sign up first, then re-run this script.")
            return

        orphaned_documents = db.query(Document).filter(Document.user_id.is_(None)).all()
        orphaned_conversations = db.query(Conversation).filter(Conversation.user_id.is_(None)).all()

        print(f"[assign] {len(orphaned_documents)} document(s) and {len(orphaned_conversations)} "
              f"conversation(s) currently have no owner.")

        if not orphaned_documents and not orphaned_conversations:
            print("[assign] nothing to do.")
            return

        if dry_run:
            print(f"[assign] dry run — would assign all of the above to {email!r}. Nothing written.")
            for document in orphaned_documents[:5]:
                print(f"  document {document.id}: {document.original_filename!r}")
            for conversation in orphaned_conversations[:5]:
                print(f"  conversation {conversation.id}: {conversation.title!r}")
            return

        for document in orphaned_documents:
            document.user_id = user.id
        for conversation in orphaned_conversations:
            conversation.user_id = user.id
        db.commit()

        print(f"[assign] done — {len(orphaned_documents)} document(s) and "
              f"{len(orphaned_conversations)} conversation(s) now belong to {email!r}.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Email of the account to assign orphaned data to.")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be assigned without writing.")
    args = parser.parse_args()

    assign_orphaned_data(email=args.email, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
