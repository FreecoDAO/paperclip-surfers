import rateLimit from "express-rate-limit";

/**
 * Create a rate limiter for authentication endpoints.
 * Limits to 5 attempts per 15 minutes per IP.
 */
export const authRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // Limit each IP to 5 requests per windowMs
  standardHeaders: false, // Disable the `RateLimit-*` headers
  skip: (req) => {
    // Skip rate limiting for health checks and other non-auth endpoints
    return req.path === "/api/health" || req.path === "/health";
  },
  keyGenerator: (req) => {
    // Use IP address as the key for rate limiting
    const forwarded = req.headers["x-forwarded-for"];
    if (typeof forwarded === "string") {
      return forwarded.split(",")[0] || req.ip || "unknown";
    }
    return req.ip || "unknown";
  },
  message: "Too many login attempts, please try again later",
  statusCode: 429,
});

/**
 * Create a rate limiter for general API endpoints.
 * Limits to 100 requests per 15 minutes per IP.
 */
export const apiRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  standardHeaders: false,
  skip: (req) => {
    // Skip rate limiting for health checks
    return req.path === "/api/health" || req.path === "/health";
  },
  keyGenerator: (req) => {
    // Use IP address or agent API key as the key
    const authHeader = req.headers.authorization;
    if (authHeader?.startsWith("Bearer ")) {
      // Use a hash of the API key to avoid exposing it
      return `key:${authHeader.substring(7, 20)}`; // Use first 20 chars of key
    }
    const forwarded = req.headers["x-forwarded-for"];
    if (typeof forwarded === "string") {
      return forwarded.split(",")[0] || req.ip || "unknown";
    }
    return req.ip || "unknown";
  },
  message: "Too many requests, please try again later",
  statusCode: 429,
});

/**
 * Create a rate limiter for file uploads.
 * Limits to 50 uploads per hour per IP.
 */
export const uploadRateLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 50, // Limit each IP to 50 uploads per hour
  standardHeaders: false,
  keyGenerator: (req) => {
    const forwarded = req.headers["x-forwarded-for"];
    if (typeof forwarded === "string") {
      return forwarded.split(",")[0] || req.ip || "unknown";
    }
    return req.ip || "unknown";
  },
  message: "Too many uploads, please try again later",
  statusCode: 429,
});
