import logging
from decimal import Decimal
from datetime import datetime, date
import threading
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger('mongo_signals')

_client = None

def get_mongo_db():
    global _client
    if _client is None:
        try:
            import pymongo
            uri = getattr(settings, 'MONGODB_URI', None)
            if not uri:
                return None
            _client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=4000)
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
    t = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    t.start()

def _sync_user(user_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        from accounts.models import User
        user = User.objects.filter(id=user_id).first()
        if not user:
            db.users.delete_one({'_id': user_id})
            return

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
            mp = user.member_profile
            doc['member_profile'] = {
                'membership_id': mp.membership_id,
                'phone': mp.phone,
                'address': mp.address,
                'max_books_allowed': mp.max_books_allowed,
                'is_blocked': mp.is_blocked,
            }
        if hasattr(user, 'staff_profile'):
            sp = user.staff_profile
            doc['staff_profile'] = {
                'staff_id': sp.staff_id,
                'designation': getattr(sp, 'department', 'Circulation'),
                'phone': sp.phone,
            }

        db.users.update_one({'_id': user.id}, {'$set': doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error syncing user to MongoDB: {e}")

def _sync_book(book_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        from books.models import Book
        b = Book.objects.filter(id=book_id).first()
        if not b:
            db.books.delete_one({'_id': book_id})
            return

        doc = {
            '_id': b.id,
            'title': b.title,
            'author': b.author,
            'isbn': b.isbn,
            'category': b.category.name if b.category else None,
            'category_id': b.category_id,
            'total_copies': b.total_copies,
            'available_copies': b.available_copies,
            'shelf_location': b.shelf_location,
            'book_value': convert_val(b.book_value),
            'description': b.description,
            'added_date': convert_val(b.added_date),
            'updated_date': convert_val(b.updated_date),
        }
        db.books.update_one({'_id': b.id}, {'$set': doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error syncing book to MongoDB: {e}")

def _sync_borrow_record(record_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        from circulation.models import BorrowRecord
        rec = BorrowRecord.objects.filter(id=record_id).first()
        if not rec:
            db.borrow_records.delete_one({'_id': record_id})
            return

        doc = {
            '_id': rec.id,
            'book_id': rec.book_id,
            'book_title': rec.book.title,
            'book_isbn': rec.book.isbn,
            'member_id': rec.member_id,
            'member_username': rec.member.username,
            'issued_by': rec.issued_by.username if rec.issued_by else None,
            'requested_days': rec.requested_days,
            'issue_date': convert_val(rec.issue_date),
            'due_date': convert_val(rec.due_date),
            'return_date': convert_val(rec.return_date),
            'status': rec.status,
            'notes': rec.notes,
        }
        db.borrow_records.update_one({'_id': rec.id}, {'$set': doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error syncing borrow record to MongoDB: {e}")

def _sync_fine(fine_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        from circulation.models import Fine
        f = Fine.objects.filter(id=fine_id).first()
        if not f:
            db.fines.delete_one({'_id': fine_id})
            return

        doc = {
            '_id': f.id,
            'borrow_record_id': f.borrow_record_id,
            'member_username': f.member.username,
            'book_title': f.borrow_record.book.title,
            'amount': convert_val(f.amount),
            'duration_days': f.duration_days,
            'overdue_days': f.overdue_days,
            'fine_rate': convert_val(f.fine_rate),
            'is_paid': f.is_paid,
            'paid_date': convert_val(f.paid_date),
            'created_at': convert_val(f.created_at),
        }
        db.fines.update_one({'_id': f.id}, {'$set': doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error syncing fine to MongoDB: {e}")

def _sync_borrow_request(request_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        from circulation.models import BorrowRequest
        req = BorrowRequest.objects.filter(id=request_id).first()
        if not req:
            db.borrow_requests.delete_one({'_id': request_id})
            return

        doc = {
            '_id': req.id,
            'member_id': req.member_id,
            'member_username': req.member.username,
            'book_id': req.book_id,
            'book_title': req.book.title,
            'requested_days': req.requested_days,
            'status': req.status,
            'requested_at': convert_val(req.requested_at),
            'reviewed_at': convert_val(req.reviewed_at),
            'reviewed_by': req.reviewed_by.username if req.reviewed_by else None,
            'notes': req.notes,
        }
        db.borrow_requests.update_one({'_id': req.id}, {'$set': doc}, upsert=True)
    except Exception as e:
        logger.error(f"Error syncing borrow request to MongoDB: {e}")

def _delete_doc(col_name, doc_id):
    db = get_mongo_db()
    if db is None:
        return
    try:
        db[col_name].delete_one({'_id': doc_id})
    except Exception as e:
        logger.error(f"Error deleting from {col_name}: {e}")

def register_signals():
    """Register all real-time post_save and post_delete signals"""
    from accounts.models import User, MemberProfile, StaffProfile
    from books.models import Book, Category
    from circulation.models import BorrowRecord, BorrowRequest, Fine

    @receiver(post_save, sender=User)
    def on_user_save(sender, instance, **kwargs):
        run_async(_sync_user, instance.id)

    @receiver(post_delete, sender=User)
    def on_user_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'users', instance.id)

    @receiver(post_save, sender=MemberProfile)
    def on_member_profile_save(sender, instance, **kwargs):
        run_async(_sync_user, instance.user_id)

    @receiver(post_save, sender=StaffProfile)
    def on_staff_profile_save(sender, instance, **kwargs):
        run_async(_sync_user, instance.user_id)

    @receiver(post_save, sender=Book)
    def on_book_save(sender, instance, **kwargs):
        run_async(_sync_book, instance.id)

    @receiver(post_delete, sender=Book)
    def on_book_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'books', instance.id)

    @receiver(post_save, sender=BorrowRecord)
    def on_borrow_record_save(sender, instance, **kwargs):
        run_async(_sync_borrow_record, instance.id)

    @receiver(post_delete, sender=BorrowRecord)
    def on_borrow_record_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'borrow_records', instance.id)

    @receiver(post_save, sender=BorrowRequest)
    def on_borrow_request_save(sender, instance, **kwargs):
        run_async(_sync_borrow_request, instance.id)

    @receiver(post_delete, sender=BorrowRequest)
    def on_borrow_request_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'borrow_requests', instance.id)

    @receiver(post_save, sender=Fine)
    def on_fine_save(sender, instance, **kwargs):
        run_async(_sync_fine, instance.id)

    @receiver(post_delete, sender=Fine)
    def on_fine_delete(sender, instance, **kwargs):
        run_async(_delete_doc, 'fines', instance.id)

