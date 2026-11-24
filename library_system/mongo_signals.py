import logging
import sys
from decimal import Decimal
from datetime import datetime, date
import threading
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger('mongo_signals')

_client = None
_client_lock = threading.Lock()


def is_testing():
    """Detect if Django is running under test runner."""
    return 'test' in sys.argv or getattr(settings, 'TESTING', False)


def get_mongo_db():
    global _client
    if is_testing():
        return None

    if _client is None:
        with _client_lock:
            if _client is None:
                try:
                    import pymongo
                    uri = getattr(settings, 'MONGODB_URI', None)
                    if not uri:
                        return None

                    try:
                        import certifi
                        ca_file = certifi.where()
                    except ImportError:
                        ca_file = None

                    mongo_kwargs = {
                        'serverSelectionTimeoutMS': 2000,
                        'connectTimeoutMS': 2000,
                        'socketTimeoutMS': 3000,
                    }
                    if ca_file:
                        mongo_kwargs['tlsCAFile'] = ca_file

                    _client = pymongo.MongoClient(uri, **mongo_kwargs)
                except Exception as e:
                    logger.warning(f"Could not connect to MongoDB: {e}")
                    return None
    try:
        db_name = getattr(settings, 'MONGODB_NAME', 'library_management_db')
        return _client[db_name]
    except Exception as e:
        logger.warning(f"Error accessing MongoDB database: {e}")
        return None


def convert_val(val):
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def run_async(func, *args, **kwargs):
    """Run Mongo sync in background thread so HTTP requests don't lag."""
    if is_testing():
        return
    t = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    t.start()


def _upsert_doc(collection_name, doc_id, doc):
    db = get_mongo_db()
    if db is None:
        return
    try:
        db[collection_name].update_one({'_id': doc_id}, {'$set': doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error syncing {collection_name} to MongoDB: {e}")


def _delete_doc(collection_name, doc_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        db[collection_name].delete_one({'_id': doc_id})
    except Exception as e:
        logger.error(f"Error deleting from {collection_name}: {e}")


def _build_user_doc(user):
    doc = {
        '_id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': convert_val(user.date_joined),
    }
    if hasattr(user, 'member_profile'):
        try:
            mp = user.member_profile
            if mp:
                doc['member_profile'] = {
                    'membership_id': mp.membership_id,
                    'phone': mp.phone,
                    'address': mp.address,
                    'max_books_allowed': mp.max_books_allowed,
                    'is_blocked': mp.is_blocked,
                }
        except Exception:
            pass
    if hasattr(user, 'staff_profile'):
        try:
            sp = user.staff_profile
            if sp:
                doc['staff_profile'] = {
                    'staff_id': sp.staff_id,
                    'designation': getattr(sp, 'department', 'Circulation'),
                    'phone': sp.phone,
                }
        except Exception:
            pass
    return doc


def _build_book_doc(b):
    return {
        '_id': b.id,
        'title': b.title,
        'author': b.author,
        'isbn': b.isbn,
        'category': b.category.name if getattr(b, 'category', None) else None,
        'category_id': b.category_id,
        'total_copies': b.total_copies,
        'available_copies': b.available_copies,
        'shelf_location': b.shelf_location,
        'book_value': convert_val(b.book_value),
        'description': b.description,
        'added_date': convert_val(b.added_date),
        'updated_date': convert_val(b.updated_date),
    }


def _build_borrow_record_doc(rec):
    return {
        '_id': rec.id,
        'book_id': rec.book_id,
        'book_title': rec.book.title if getattr(rec, 'book', None) else '',
        'book_isbn': rec.book.isbn if getattr(rec, 'book', None) else '',
        'member_id': rec.member_id,
        'member_username': rec.member.username if getattr(rec, 'member', None) else '',
        'issued_by': rec.issued_by.username if getattr(rec, 'issued_by', None) else None,
        'requested_days': rec.requested_days,
        'issue_date': convert_val(rec.issue_date),
        'due_date': convert_val(rec.due_date),
        'return_date': convert_val(rec.return_date),
        'status': rec.status,
        'notes': rec.notes,
    }


def _build_fine_doc(f):
    book_title = ''
    try:
        if f.borrow_record and f.borrow_record.book:
            book_title = f.borrow_record.book.title
    except Exception:
        pass
    member_username = ''
    try:
        if f.member:
            member_username = f.member.username
    except Exception:
        pass
    return {
        '_id': f.id,
        'borrow_record_id': f.borrow_record_id,
        'member_username': member_username,
        'book_title': book_title,
        'amount': convert_val(f.amount),
        'duration_days': f.duration_days,
        'overdue_days': f.overdue_days,
        'fine_rate': convert_val(f.fine_rate),
        'is_paid': f.is_paid,
        'paid_date': convert_val(f.paid_date),
        'created_at': convert_val(f.created_at),
    }


def _build_borrow_request_doc(req):
    return {
        '_id': req.id,
        'member_id': req.member_id,
        'member_username': req.member.username if getattr(req, 'member', None) else '',
        'book_id': req.book_id,
        'book_title': req.book.title if getattr(req, 'book', None) else '',
        'requested_days': req.requested_days,
        'status': req.status,
        'requested_at': convert_val(req.requested_at),
        'reviewed_at': convert_val(req.reviewed_at),
        'reviewed_by': req.reviewed_by.username if getattr(req, 'reviewed_by', None) else None,
        'notes': req.notes,
    }


def register_signals():
    """Register all real-time post_save and post_delete signals"""
    if is_testing():
        return

    from accounts.models import User, MemberProfile, StaffProfile
    from books.models import Book
    from circulation.models import BorrowRecord, BorrowRequest, Fine

    @receiver(post_save, sender=User)
    def on_user_save(sender, instance, **kwargs):
        doc = _build_user_doc(instance)
        run_async(_upsert_doc, 'users', instance.id, doc)

    @receiver(post_delete, sender=User)
    def on_user_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'users', instance.id)

    @receiver(post_save, sender=MemberProfile)
    def on_member_profile_save(sender, instance, **kwargs):
        try:
            user = getattr(instance, 'user', None)
            if user:
                doc = _build_user_doc(user)
                run_async(_upsert_doc, 'users', user.id, doc)
        except Exception:
            pass

    @receiver(post_save, sender=StaffProfile)
    def on_staff_profile_save(sender, instance, **kwargs):
        try:
            user = getattr(instance, 'user', None)
            if user:
                doc = _build_user_doc(user)
                run_async(_upsert_doc, 'users', user.id, doc)
        except Exception:
            pass

    @receiver(post_save, sender=Book)
    def on_book_save(sender, instance, **kwargs):
        doc = _build_book_doc(instance)
        run_async(_upsert_doc, 'books', instance.id, doc)

    @receiver(post_delete, sender=Book)
    def on_book_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'books', instance.id)

    @receiver(post_save, sender=BorrowRecord)
    def on_borrow_record_save(sender, instance, **kwargs):
        doc = _build_borrow_record_doc(instance)
        run_async(_upsert_doc, 'borrow_records', instance.id, doc)

    @receiver(post_delete, sender=BorrowRecord)
    def on_borrow_record_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'borrow_records', instance.id)

    @receiver(post_save, sender=BorrowRequest)
    def on_borrow_request_save(sender, instance, **kwargs):
        doc = _build_borrow_request_doc(instance)
        run_async(_upsert_doc, 'borrow_requests', instance.id, doc)

    @receiver(post_delete, sender=BorrowRequest)
    def on_borrow_request_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'borrow_requests', instance.id)

    @receiver(post_save, sender=Fine)
    def on_fine_save(sender, instance, **kwargs):
        doc = _build_fine_doc(instance)
        run_async(_upsert_doc, 'fines', instance.id, doc)

    @receiver(post_delete, sender=Fine)
    def on_fine_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'fines', instance.id)
