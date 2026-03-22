# backend/db/supabase_client.py
from datetime import datetime, timezone
from supabase import create_client, Client
from config import settings


def get_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)


# --- Searches ---

def create_search(query: str, max_results: int, requirements: list[str] | None = None) -> dict:
    client = get_client()
    result = client.table("searches").insert({
        "query": query,
        "max_results": max_results,
        "requirements": requirements or [],
        "status": "pending",
    }).execute()
    return result.data[0]


def update_search_status(search_id: str, status: str) -> None:
    client = get_client()
    client.table("searches").update({"status": status}).eq("id", search_id).execute()


def get_search(search_id: str) -> dict | None:
    client = get_client()
    result = client.table("searches").select("*").eq("id", search_id).execute()
    return result.data[0] if result.data else None


def list_searches() -> list[dict]:
    client = get_client()
    result = client.table("searches").select("*").order("created_at", desc=True).execute()
    return result.data


def delete_search(search_id: str) -> None:
    client = get_client()
    client.table("searches").delete().eq("id", search_id).execute()


# --- Products ---

def insert_products(products: list[dict]) -> list[dict]:
    client = get_client()
    result = client.table("products").insert(products).execute()
    return result.data


def confirm_products(product_ids: list[str]) -> None:
    client = get_client()
    client.table("products").update({"confirmed": True}).in_("id", product_ids).execute()


def get_products_by_search(search_id: str) -> list[dict]:
    client = get_client()
    result = client.table("products").select("*").eq("search_id", search_id).execute()
    return result.data


def get_confirmed_products(search_id: str) -> list[dict]:
    client = get_client()
    result = (
        client.table("products")
        .select("*")
        .eq("search_id", search_id)
        .eq("confirmed", True)
        .execute()
    )
    return result.data


def get_product(product_id: str) -> dict | None:
    client = get_client()
    result = client.table("products").select("*").eq("id", product_id).execute()
    return result.data[0] if result.data else None


# --- Reviews ---

def insert_reviews(reviews: list[dict]) -> None:
    client = get_client()
    client.table("reviews").insert(reviews).execute()


def get_reviews_by_product(product_id: str) -> list[dict]:
    client = get_client()
    result = client.table("reviews").select("*").eq("product_id", product_id).execute()
    return result.data


# --- Analysis ---

def insert_analysis(analysis: dict) -> dict:
    client = get_client()
    result = client.table("analysis").insert(analysis).execute()
    return result.data[0]


def get_analysis_by_product(product_id: str) -> dict | None:
    client = get_client()
    result = client.table("analysis").select("*").eq("product_id", product_id).execute()
    return result.data[0] if result.data else None


def find_or_create_product_by_asin(product: dict) -> dict:
    """Find an existing product by ASIN or create a new standalone one (no search_id)."""
    client = get_client()
    existing = client.table("products").select("*").eq("asin", product["asin"]).limit(1).execute()
    if existing.data:
        return existing.data[0]
    result = client.table("products").insert({**product, "confirmed": True}).execute()
    return result.data[0]


# --- Watchlist ---

def add_to_watchlist(product_id: str) -> dict:
    client = get_client()
    result = client.table("watchlist").upsert({"product_id": product_id}).execute()
    return result.data[0]


def get_watchlist() -> list[dict]:
    client = get_client()
    result = (
        client.table("watchlist")
        .select("*, products(*)")
        .order("added_at", desc=True)
        .execute()
    )
    return result.data


def delete_watchlist_item(watchlist_id: str) -> None:
    client = get_client()
    client.table("watchlist").delete().eq("id", watchlist_id).execute()


def update_watchlist_checked(watchlist_id: str) -> None:
    client = get_client()
    client.table("watchlist").update({
        "last_checked_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", watchlist_id).execute()


# --- Price history ---

def insert_price_history(product_id: str, price: float, currency: str = "USD") -> None:
    client = get_client()
    client.table("price_history").insert({
        "product_id": product_id,
        "price": price,
        "currency": currency
    }).execute()


def get_price_history(product_id: str) -> list[dict]:
    client = get_client()
    result = (
        client.table("price_history")
        .select("*")
        .eq("product_id", product_id)
        .order("checked_at", desc=True)
        .limit(30)
        .execute()
    )
    return result.data
