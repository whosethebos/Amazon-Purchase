// frontend/lib/api.ts
import { API_URL } from "./config";
import type { AnalyzeUrlResponse, SimilarProduct } from "./types";

export async function startSearch(
  query: string,
  requirements: string[] = [],
  maxResults = 10
): Promise<{ search_id: string }> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, requirements, max_results: maxResults }),
  });
  if (!res.ok) throw new Error("Failed to start search");
  return res.json();
}

export async function confirmProducts(searchId: string, productIds: string[]): Promise<void> {
  const res = await fetch(`${API_URL}/api/search/${searchId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_ids: productIds }),
  });
  if (!res.ok) throw new Error("Failed to confirm products");
}

export async function getResults(searchId: string) {
  const res = await fetch(`${API_URL}/api/search/${searchId}/results`);
  if (!res.ok) throw new Error("Failed to fetch results");
  return res.json();
}

export async function getSearchHistory() {
  const res = await fetch(`${API_URL}/api/searches`);
  if (!res.ok) throw new Error("Failed to fetch search history");
  return res.json();
}

export async function deleteSearch(searchId: string): Promise<void> {
  await fetch(`${API_URL}/api/searches/${searchId}`, { method: "DELETE" });
}

export async function getWatchlist() {
  const res = await fetch(`${API_URL}/api/watchlist`);
  if (!res.ok) throw new Error("Failed to fetch watchlist");
  return res.json();
}

export async function addToWatchlist(productId: string) {
  const res = await fetch(`${API_URL}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId }),
  });
  if (!res.ok) throw new Error("Failed to add to watchlist");
  return res.json();
}

export async function removeFromWatchlist(watchlistId: string): Promise<void> {
  await fetch(`${API_URL}/api/watchlist/${watchlistId}`, { method: "DELETE" });
}

export async function refreshWatchlistItem(watchlistId: string) {
  const res = await fetch(`${API_URL}/api/watchlist/${watchlistId}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to refresh price");
  return res.json();
}

export async function getPreviewImages(q: string): Promise<{ images: string[] }> {
  try {
    const res = await fetch(`${API_URL}/api/preview-images?q=${encodeURIComponent(q)}`);
    if (!res.ok) return { images: [] };
    return res.json();
  } catch {
    return { images: [] };
  }
}

export async function addToWatchlistFromUrl(product: {
  asin: string; title: string; price: number | null; currency: string | null;
  rating: number | null; review_count: number | null; image_url: string | null; url: string;
}): Promise<void> {
  const res = await fetch(`${API_URL}/api/watchlist/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(product),
  });
  if (!res.ok) throw new Error("Failed to add to watchlist");
}

export async function fetchSimilarProducts(asin: string, title: string): Promise<SimilarProduct[]> {
  try {
    const res = await fetch(
      `${API_URL}/api/similar-products?asin=${encodeURIComponent(asin)}&title=${encodeURIComponent(title)}`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return data.products ?? [];
  } catch {
    return [];
  }
}

export async function analyzeUrl(url: string, signal?: AbortSignal): Promise<AnalyzeUrlResponse> {
  const res = await fetch(`${API_URL}/api/analyze-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error ?? "Request failed");
  }
  return res.json();
}
