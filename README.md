# Campus Marketplace

An OLX-style marketplace for university students. List items, browse and filter, contact sellers, meet on
campus, pay in person (cash/UPI outside the app), then review the seller. **There is no online payment.**

**Stack:** Python + Flask, MongoDB (PyMongo), Jinja2 templates + HTML/CSS/JavaScript, bcrypt, Flask-WTF (CSRF),
Flask-Limiter, Cloudinary (optional), pytest + mongomock.

## Quick start (local)
```
python -m venv venv
venv\Scripts\activate            # Windows   |   source venv/bin/activate   (macOS/Linux)
pip install -r requirements.txt
copy .env.example .env           # Windows   |   cp .env.example .env
python seed.py                   # optional sample data (password for all: Password123)
python app.py                    # http://127.0.0.1:5000
```
MongoDB must be running (local `mongodb://localhost:27017`, or a MongoDB Atlas URI in `MONGO_URI`).
Sample logins after seeding: `aarav@example.com`, `diya@example.com`, `kabir@example.com`, `meera@example.com`.

## Features
- Register / login / logout / edit profile (name, phone, year, picture). Email and registration number are fixed.
- Create, edit, view listings with 1-5 images; mark as SOLD (confirmation page, atomic update, optional buyer + agreed price).
- Homepage: search (title + description), category, condition, price range, sort (newest / price asc / desc), pagination.
- Product page with seller profile + rating, and an in-app **Contact seller** inquiry system (seller can reply, optionally sharing phone).
- Completed-sale transaction records, buyer reviews (1-5 stars), seller average rating + review count.
- Pages: marketplace, register, login, product, create/edit listing, profile, my listings, my sold items, my purchases, my inquiries, public seller profile.

## Project structure
```
app.py            app factory, error pages, security headers
config.py         environment-based settings (.env)
constants.py      categories, conditions, statuses, sort options
db.py             MongoDB connection, schema validation, indexes
extensions.py     CSRF + rate limiter objects
models/           database access: users, products, transactions, reviews, inquiries
services/         validators.py (all input validation), auth.py (bcrypt, login_required), images.py (uploads)
routes/           Flask Blueprints: main, auth, products, profile, inquiries, reviews
templates/        Jinja2 pages (+ _macros.html)    static/  css, js, images, uploads
tests/            pytest suite (40 tests)          seed.py  sample data
```

## MongoDB design (database `campus_marketplace`)
| Collection | Key fields | Notes |
|---|---|---|
| users | full_name, email, registration_number, phone, academic_year, password_hash, avg_rating, review_count, created_at | unique indexes on email, registration_number |
| products | title, description, price (int ₹), category, condition, images[], seller_id, pickup_location, status, created_at | indexes: (status, created_at), (status, category), (status, price), (seller_id, status) |
| transactions | product_id, seller_id, buyer_id (nullable), price, status, completed_at | unique product_id: an item sells once |
| reviews | transaction_id, product_id, buyer_id, seller_id, rating, comment, created_at | unique transaction_id: one review per sale |
| inquiries | product_id, buyer_id, seller_id, message, reply, share_phone, created_at | unique (product_id, buyer_id) |

- **References, not copies:** products store `seller_id`; the seller is joined with `$lookup` when displaying.
- **Embedding:** image metadata is embedded in the product (always read together, bounded to 5).
- **Denormalised rating summary** (`avg_rating`, `review_count`) lives on the user so product cards need no review scan; it is recomputed from `reviews` with a `$group` aggregation on every new review, so it is always exact.
- **Aggregation pipelines** use `$match`, `$sort`, `$skip`, `$limit`, `$group`, `$lookup`, `$unwind`, `$project`.
- **Schema validation:** `$jsonSchema` validators are applied to every collection at startup (`db.py`).
- **Atomic update:** `find_one_and_update({_id, seller_id, status: AVAILABLE}, {$set: SOLD})`: ownership and state are checked in the same operation that changes it.

## Security checklist
bcrypt hashing · server-side Flask sessions with HttpOnly/SameSite cookies (`SESSION_COOKIE_SECURE=1` on HTTPS) ·
CSRF tokens on every POST · rate limits on login/register/inquiries · ownership checks on every edit/sold/reply/review ·
input validated server-side with allow-lists (blocks NoSQL operator injection; search text is regex-escaped) ·
Jinja auto-escaping (XSS) · image type, size and magic-byte checks · open-redirect-safe `next` · generic login errors with
constant-time-ish behaviour · password hash/phone/registration number never in public pages · CSP + security headers ·
secrets only in `.env` (git-ignored) · logs contain no passwords or secrets.

## Tests
```
pytest
```
Tests run against `mongomock` (a fake in-memory MongoDB), so no database is needed. They cover registration, login,
permissions (owner-only edit/sold), validation, uploads, search/filter/sort/pagination, inquiries, sales, reviews,
rating math, CSRF, rate limiting, injection attempts and XSS escaping.

## Deployment (Render / Railway / any Linux host)
1. Create a free **MongoDB Atlas** cluster, allow your host's IP, copy the connection string into `MONGO_URI`.
2. Create a **Cloudinary** account and set the three `CLOUDINARY_*` variables. (Local uploads vanish on hosts with ephemeral disks.)
3. Push to GitHub (`.env` is git-ignored). Create a web service from the repo:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn "app:create_app()"` (also in `Procfile`)
4. Set environment variables: `SECRET_KEY` (long random), `MONGO_URI`, `MONGO_DB_NAME`, `SESSION_COOKIE_SECURE=1`,
   `FLASK_DEBUG=0`, optionally `ALLOWED_EMAIL_DOMAINS=your-university.edu`.
5. If you run several gunicorn workers, set `RATELIMIT_STORAGE_URI` to a Redis URL so rate limits are shared.
6. Visit `/health` to confirm the app reaches MongoDB.

## Known limits / next steps
Prices are whole rupees. Image checks verify type and magic bytes but do not decode pixels. Email verification and
password reset are not implemented. Inquiries are one message per buyer per item with a single seller reply.
