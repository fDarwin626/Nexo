# Nexo — Multi-Vendor Marketplace
### Nigerian Marketplace // Converge & Sell

---

## v1.0.0 — In Development

### ✅ Completed

- **Project Foundation** — Django 6, PostgreSQL (Supabase), settings split (dev/prod), environment variables
- **Database Models** — 40+ models across 9 apps (accounts, stores, products, orders, payments, disputes, notifications, core)
- **Authentication** — Email registration, verification, login/logout, forgot password, Google OAuth, remember me, role-based redirects
- **Security** — Custom ban system (shadow/hard/permanent), fraud scoring, device fingerprint ready, rate limiting
- **Seller Onboarding** — 4-step registration flow, Flutterwave subscription payment (test mode), admin approval system
- **Approval Emails** — Auto-email on store approval and rejection
- **Product System** — Categories (39), variant types (8), variant options (87), SKU builder, image upload (PNG enforced)
- **Admin Panel** — Full Django admin for all models, seller management, approval workflow
- **Marketplace & Storefronts** — Homepage, marketplace browse, category pages, seller storefront, currency toggle (NGN/USD), wishlist
- **Cart & Checkout** — Guest + user cart, cart merge on login, delivery zones, coupon system, POD eligibility
- **Payments** — Flutterwave split payments, subaccount architecture, atomic order creation, race condition protection, PaymentLog audit trail
- **Seller Dashboard** — Home stats, product management, order management, coupons, subscription status, store settings, delivery zones, revenue tracker, dispute center
- **Admin Super Dashboard** — GMV, seller approvals, dispute queue, reserve fund, exchange rate setter, platform coupons, fraud/ban log, top products
- **Dispute System** — Buyer opens dispute, seller 48hr response, admin-seller chat, strike ladder, compensation tiers, Flutterwave refund API
- **Celery Tasks** — Subscription expiry warnings (30d/7d/1d), store auto-expire, seller account cleanup (60 days), product restock deadlines, price drop alerts, POD monthly reset, monthly revenue reset
- **Notifications** — In-app notification system, unread count API, mark read, mark all read
- **Reviews & Ratings** — Verified purchase only, photo upload, seller one-reply, auto-calculated product rating_avg and rating_count

### 📋 Planned
- **Section 13** — DRF API Layer (Flutter-ready)
- **Section 14** — Full Frontend UI (Tailwind + Alpine.js + GSAP)
- **Section 15** — SEO & Legal Pages
- **Section 16** — Deployment (Render)
- **Phase 2** — Flutter Mobile App

---

*Built with Django · PostgreSQL · Flutterwave · Cloudinary · Supabase · Celery · Redis*