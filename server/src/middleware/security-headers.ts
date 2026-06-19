import type { RequestHandler } from "express";

/**
 * Middleware to add security headers to all responses.
 * Includes HSTS, CSP, X-Content-Type-Options, X-Frame-Options, etc.
 */
export function securityHeadersMiddleware(opts?: { publicUrl?: string }): RequestHandler {
  return (_req, res, next) => {
    // Strict-Transport-Security: Force HTTPS for 1 year (including subdomains)
    res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload");

    // X-Content-Type-Options: Prevent MIME type sniffing
    res.setHeader("X-Content-Type-Options", "nosniff");

    // X-Frame-Options: Prevent clickjacking
    res.setHeader("X-Frame-Options", "DENY");

    // X-XSS-Protection: Enable XSS protection (legacy browsers)
    res.setHeader("X-XSS-Protection", "1; mode=block");

    // Referrer-Policy: Control referrer information
    res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");

    // Permissions-Policy (formerly Feature-Policy): Restrict browser features
    res.setHeader(
      "Permissions-Policy",
      "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
    );

    // Content-Security-Policy: Prevent XSS, clickjacking, etc.
    // Allow inline scripts for React (CSP level 2), but restrict other resources
    const cspDirectives = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // Unsafe-eval needed for dynamic script loading, unsafe-inline for React
      "style-src 'self' 'unsafe-inline'", // Tailwind and other styles need unsafe-inline
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ];

    // If public URL is provided and is HTTPS, upgrade insecure requests
    if (opts?.publicUrl?.startsWith("https://")) {
      cspDirectives.unshift("upgrade-insecure-requests");
    }

    res.setHeader("Content-Security-Policy", cspDirectives.join("; "));

    next();
  };
}
