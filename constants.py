"""Shared constants: allowed values are defined once and reused everywhere."""

CATEGORIES = [
    "Books and Study Materials", "Electronics", "Clothing and Shoes", "Furniture",
    "Hostel Essentials", "Sports Equipment", "Accessories", "Other",
]
CONDITIONS = ["New", "Like New", "Good", "Fair"]

AVAILABLE = "AVAILABLE"
SOLD = "SOLD"

ACADEMIC_YEARS = [1, 2, 3, 4, 5]
MAX_PRICE = 1_000_000  # rupees

# key -> (label shown in the UI, MongoDB sort spec). _id is a tie-breaker so
# pagination never repeats or skips items that share the same price/date.
SORT_OPTIONS = {
    "newest": ("Newest first", {"created_at": -1, "_id": -1}),
    "price_asc": ("Price: low to high", {"price": 1, "_id": -1}),
    "price_desc": ("Price: high to low", {"price": -1, "_id": -1}),
}
