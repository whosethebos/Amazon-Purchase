// frontend/lib/types.ts

export interface ProductInfo {
  asin: string;
  title: string;
  price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
}

/** Percentage values (0–100) for each star level, scraped from Amazon's review histogram. */
export interface Histogram {
  "1": number;
  "2": number;
  "3": number;
  "4": number;
  "5": number;
}

export interface ReviewAnalysis {
  summary: string;
  pros: string[];
  cons: string[];
  featured_review_indices: number[];
  score: number | null;
}

export interface SimilarProduct {
  asin: string;
  title: string;
  price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
  url: string;
}

export interface Review {
  stars: number;
  author: string;
  title: string;
  body: string;
}

export interface AnalyzeUrlResponse {
  product: ProductInfo;
  histogram: Histogram;
  analysis: ReviewAnalysis;
  reviews: Review[];
}
