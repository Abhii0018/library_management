import os
import django
from decimal import Decimal
from datetime import datetime, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_system.settings')
django.setup()

import pymongo
from accounts.models import User, MemberProfile, StaffProfile
from books.models import Category, Book
from circulation.models import BorrowRequest, BorrowRecord, Fine

def convert_value(val):
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val
def sync_to_mongodb(mongo_uri=None):
    if not mongo_uri:
        mongo_uri = os.environ.get('MONGODB_URI')
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable or argument is required.")
    client = pymongo.MongoClient(mongo_uri)
    db = client.get_database('library_management_db')
    
    print(f"Connecting to MongoDB at: {mongo_uri.split('@')[-1] if '@' in mongo_uri else mongo_uri}...")

    # 1. Categories
    db.categories.delete_many({})
    categories = []
    for cat in Category.objects.all():
        categories.append({
            '_id': cat.id,
            'name': cat.name,
            'description': cat.description,
        })
    if categories:
        db.categories.insert_many(categories)
    print(f"Synced {len(categories)} categories.")

    # 2. Books
    db.books.delete_many({})
    books = []
    for b in Book.objects.all():
        books.append({
            '_id': b.id,
            'title': b.title,
            'author': b.author,
            'isbn': b.isbn,
            'category': b.category.name if b.category else None,
            'category_id': b.category_id,
            'total_copies': b.total_copies,
            'available_copies': b.available_copies,
            'shelf_location': b.shelf_location,
            'book_value': convert_value(b.book_value),
            'description': b.description,
            'added_date': convert_value(b.added_date),
            'updated_date': convert_value(b.updated_date),
        })
    if books:
        db.books.insert_many(books)
    print(f"Synced {len(books)} books.")

    # 3. Users & Profiles
    db.users.delete_many({})
    users = []
    for u in User.objects.all():
        u_data = {
            '_id': u.id,
            'username': u.username,
            'email': u.email,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'role': u.role,
            'is_active': u.is_active,
            'is_staff': u.is_staff,
            'is_superuser': u.is_superuser,
            'date_joined': convert_value(u.date_joined),
        }
        if hasattr(u, 'member_profile'):
            mp = u.member_profile
            u_data['member_profile'] = {
                'membership_id': mp.membership_id,
                'phone': mp.phone,
                'address': mp.address,
                'max_books_allowed': mp.max_books_allowed,
                'is_blocked': mp.is_blocked,
            }
        if hasattr(u, 'staff_profile'):
            sp = u.staff_profile
            u_data['staff_profile'] = {
                'staff_id': sp.staff_id,
                'designation': getattr(sp, 'department', 'Circulation'),
                'phone': sp.phone,
            }
        users.append(u_data)
    if users:
        db.users.insert_many(users)
    print(f"Synced {len(users)} users.")

    # 4. Borrow Requests
    db.borrow_requests.delete_many({})
    requests = []
    for req in BorrowRequest.objects.all():
        requests.append({
            '_id': req.id,
            'member_id': req.member_id,
            'member_username': req.member.username,
            'book_id': req.book_id,
            'book_title': req.book.title,
            'requested_days': req.requested_days,
            'status': req.status,
            'requested_at': convert_value(req.requested_at),
            'reviewed_at': convert_value(req.reviewed_at),
            'reviewed_by': req.reviewed_by.username if req.reviewed_by else None,
            'notes': req.notes,
        })
    if requests:
        db.borrow_requests.insert_many(requests)
    print(f"Synced {len(requests)} borrow requests.")

    # 5. Borrow Records
    db.borrow_records.delete_many({})
    records = []
    for rec in BorrowRecord.objects.all():
        records.append({
            '_id': rec.id,
            'book_id': rec.book_id,
            'book_title': rec.book.title,
            'book_isbn': rec.book.isbn,
            'member_id': rec.member_id,
            'member_username': rec.member.username,
            'issued_by': rec.issued_by.username if rec.issued_by else None,
            'requested_days': rec.requested_days,
            'issue_date': convert_value(rec.issue_date),
            'due_date': convert_value(rec.due_date),
            'return_date': convert_value(rec.return_date),
            'status': rec.status,
            'notes': rec.notes,
        })
    if records:
        db.borrow_records.insert_many(records)
    print(f"Synced {len(records)} borrow records.")

    # 6. Fines
    db.fines.delete_many({})
    fines = []
    for f in Fine.objects.all():
        fines.append({
            '_id': f.id,
            'borrow_record_id': f.borrow_record_id,
            'member_username': f.member.username,
            'book_title': f.borrow_record.book.title,
            'amount': convert_value(f.amount),
            'duration_days': f.duration_days,
            'overdue_days': f.overdue_days,
            'fine_rate': convert_value(f.fine_rate),
            'is_paid': f.is_paid,
            'paid_date': convert_value(f.paid_date),
            'created_at': convert_value(f.created_at),
        })
    if fines:
        db.fines.insert_many(fines)
    print(f"Synced {len(fines)} fines.")

    print("\nSUCCESS: All data successfully synced to MongoDB database 'library_management_db'!")

if __name__ == '__main__':
    import sys
    uri = sys.argv[1] if len(sys.argv) > 1 else None
    sync_to_mongodb(uri)
