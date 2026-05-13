"""OpenAPI tag metadata shown in `/docs` and `/redoc`.

Order here controls the section order in the rendered docs.
"""

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Register, login, refresh JWT tokens",
    },
    {
        "name": "users",
        "description": "User profile (`/me`) and super-admin user management",
    },
    {
        "name": "sanatoriums",
        "description": (
            "Sanatorium + wellness-center listings (one table, two property "
            "types). Filters: `property_type`, `wellness_category`, `city`, "
            "`region`, `stars`, `min_rating`, `amenity_ids`, `treatment_focus`."
        ),
    },
    {
        "name": "amenities",
        "description": (
            "Global amenity catalog (Wi-Fi, Pool, Ozonotherapy…). "
            "Categories: `facility`, `medical`, `nutrition`, `wellness`. "
            "Managed by super_admin; referenced by sanatoriums and programs."
        ),
    },
    {
        "name": "programs",
        "description": (
            "Treatment & wellness programs per sanatorium. Two flavours: "
            "(a) sanatorium medical packages bundled with a room stay "
            "(`min_nights`/`max_nights`, no standalone price); "
            "(b) wellness sessions/retreats with `price` + `currency` "
            "(plus `duration_minutes`, instructor info, group size)."
        ),
    },
    {
        "name": "rooms",
        "description": (
            "Room categories, daily availability (per-date inventory), "
            "seasonal price periods, and search."
        ),
    },
    {
        "name": "extra-beds",
        "description": (
            "Per-sanatorium extra bed configurations (children, additional "
            "mattress, etc.). Snapshot is frozen onto the booking when added."
        ),
    },
    {
        "name": "bookings",
        "description": (
            "Booking creation, listing, cancellation. Two booking types: "
            "`room` (overnight stay, locks daily availability) and `session` "
            "(program-based, charges `program.price × guests`)."
        ),
    },
    {
        "name": "reviews",
        "description": (
            "Guest reviews per sanatorium. Maintains denormalized "
            "`avg_rating` and `review_count` on the sanatorium."
        ),
    },
    {
        "name": "exchange-rates",
        "description": "USD/UZS exchange rate management for price display",
    },
    {
        "name": "health",
        "description": "Liveness + database connectivity probes",
    },
]
