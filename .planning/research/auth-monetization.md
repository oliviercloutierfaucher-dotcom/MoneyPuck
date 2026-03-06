# Research: Authentication & Monetization for MoneyPuck

**Domain:** NHL betting edge platform (SaaS)
**Researched:** 2026-03-06
**Overall confidence:** MEDIUM-HIGH

---

## 1. Authentication Options

### Recommendation: Supabase Auth (Phase 1) with JWT token validation in Python

The current server is Python stdlib `ThreadingHTTPServer`. Adding Flask/Django just for auth is overkill. Here are the viable options ranked:

### Option A: Supabase Auth (RECOMMENDED)

**Why:** 50,000 free MAUs (dwarfs Auth0's 7,500 and Clerk's 10,000). Supabase Auth issues JWTs that your Python server can verify with PyJWT -- no SDK dependency needed. You get Google/GitHub OAuth, email/password, and magic links out of the box.

**How it works with stdlib server:**
1. Frontend calls Supabase Auth JS SDK (hosted login UI or embedded)
2. Supabase issues a JWT on successful login
3. Frontend sends JWT in `Authorization: Bearer <token>` header
4. Python server verifies JWT using PyJWT + Supabase's JWT secret
5. Decode the JWT to get `user_id`, `email`, `role` (free/paid)

**Implementation complexity:** LOW. ~50 lines of Python middleware.

```python
# Pseudocode for JWT verification middleware
import jwt

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

def authenticate(handler_func):
    def wrapper(self, *args, **kwargs):
        token = self.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"],
                                 audience="authenticated")
            self.user = payload
        except jwt.InvalidTokenError:
            self.send_error(401, "Invalid or expired token")
            return
        return handler_func(self, *args, **kwargs)
    return wrapper
```

**Cost:** Free up to 50K MAUs. Pro plan $25/mo adds more features. Even at scale, $0.00325/MAU is cheapest in class.

**Confidence:** HIGH -- Supabase Auth is well-documented, JWT verification with PyJWT is standard.

### Option B: Auth0

50x more expensive per MAU ($0.07 vs $0.00325). Enterprise features (SAML SSO, HIPAA) you don't need. Only 7,500 free MAUs. Skip it.

### Option C: Clerk

Frontend-focused (React components). 10K free MAUs is fine but costs $0.02/MAU after. Better DX for Next.js apps, worse fit for a Python stdlib backend. Skip it.

### Option D: Roll Your Own JWT Auth

PyJWT + bcrypt + SQLite user table. Full control but you're building password reset, email verification, OAuth flows, rate limiting, CSRF protection all yourself. Not worth it when Supabase Auth is free and handles all of this.

### Option E: Session-Based Auth with Cookies

Works with stdlib server but requires server-side session storage, CSRF tokens, and doesn't scale across multiple Railway instances. JWT is stateless and simpler. Skip it.

### Decision: Supabase Auth
- Free tier covers you well past product-market fit
- JWT verification is ~50 lines in your existing server
- Google/GitHub OAuth included free
- Email/password with verification included
- No framework dependency needed

**Sources:**
- [Supabase Auth docs](https://supabase.com/docs/guides/auth)
- [PyJWT docs](https://pyjwt.readthedocs.io/)
- [Auth provider pricing comparison](https://designrevision.com/blog/auth-providers-compared)
- [Zuplo auth pricing comparison](https://zuplo.com/learning-center/api-authentication-pricing)

---

## 2. Payment Processing

### Recommendation: Stripe Checkout with Subscriptions

Stripe is the only serious option for a Canadian SaaS product. No need to evaluate alternatives.

### Integration Pattern

Use **Stripe Checkout** (Stripe-hosted payment page) -- NOT Stripe Elements. Reasons:
- Zero frontend payment UI to build
- PCI compliance handled entirely by Stripe
- Works with any backend including stdlib Python
- Supports subscriptions natively

**Flow:**
1. User clicks "Upgrade to Pro" on your dashboard
2. Python server creates a Stripe Checkout Session via `stripe` Python SDK
3. User is redirected to Stripe's hosted checkout page
4. After payment, Stripe redirects back to your success URL
5. Stripe sends `checkout.session.completed` webhook to your server
6. Your server updates user's tier in SQLite (or Supabase)

**Webhook handling in stdlib server:**
```python
# Add a /webhook endpoint to your ThreadingHTTPServer
def handle_stripe_webhook(self):
    payload = self.rfile.read(int(self.headers['Content-Length']))
    sig_header = self.headers.get('Stripe-Signature')
    event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)

    if event['type'] == 'checkout.session.completed':
        user_id = event['data']['object']['client_reference_id']
        update_user_tier(user_id, 'paid')
    elif event['type'] == 'customer.subscription.deleted':
        user_id = lookup_user_by_customer(event['data']['object']['customer'])
        update_user_tier(user_id, 'free')
```

### Subscription vs One-Time Payment

**Use monthly subscription.** Reasons:
- Competitors all use monthly subscriptions (OddsJam, BetQL, Unabated)
- Betting tools have ongoing costs (Odds API calls, compute, data)
- Recurring revenue is what makes a SaaS viable
- Offer annual plan at ~20% discount for retention

**Confidence:** HIGH -- Stripe Checkout with Python is well-documented and battle-tested.

**Sources:**
- [Stripe Checkout docs](https://docs.stripe.com/payments/checkout/how-checkout-works)
- [Stripe subscription integration](https://docs.stripe.com/billing/subscriptions/build-subscriptions)
- [Stripe webhooks](https://docs.stripe.com/webhooks)

---

## 3. Pricing & Competitive Landscape

### Competitor Pricing (verified 2026)

| Product | Cheapest Tier | Mid Tier | Top Tier | Focus |
|---------|--------------|----------|----------|-------|
| OddsJam | $20/mo (Trends) | $60/mo (Fantasy) | $200-400/mo (Gold/Global) | Arb/+EV scanning, 150+ books |
| BetQL | $20/mo (1 sport) | $25-30/mo (2-3 sports) | $50/mo (All Sports) | Mobile-first, star ratings |
| Unabated | ~$50/mo | ~$100/mo | ~$150/mo | Juice-free lines, simulation |
| Picks services | $30-50/mo | $50-100/mo | $100-200/mo | Curated picks |

### Recommended MoneyPuck Pricing

**Free Tier** -- the hook:
- Tonight's games with team matchups
- Model win probability for each team (the unique value prop)
- Basic game scores / standings
- Limited to 3 games per night (or delayed 30 min)

**Pro Tier -- $29/mo ($249/yr annual):**
- Full value bet recommendations with Kelly sizing
- Arbitrage scanner across all books
- Hedge calculator
- CLV (closing line value) tracking
- Performance tracker with ROI history
- Player prop edges
- Sparkline odds movement charts
- Email alerts for high-edge opportunities

**Why $29/mo:**
- Significantly undercuts OddsJam ($200/mo for comparable features)
- Below BetQL's all-sport tier ($50/mo)
- Accessible enough for recreational bettors
- NHL-only focus justifies lower price vs multi-sport tools
- At 100 subscribers = $2,900/mo recurring revenue
- Room to raise price later as features mature

**Why NOT a higher price:**
- You're NHL-only (smaller TAM than multi-sport tools)
- Model is unproven publicly (no track record yet)
- Lower price = faster user acquisition = faster social proof
- Can always raise prices; harder to lower them

### Free/Paid Split Strategy

The goal is to give enough free value that users understand the model works, but gate the actionable output:

| Feature | Free | Paid |
|---------|------|------|
| Game matchups tonight | Yes | Yes |
| Model win probability | Yes (delayed 30min or 3 games) | Yes (real-time, all games) |
| Value bet recommendations | No | Yes |
| Kelly bet sizing | No | Yes |
| Arbitrage scanner | No | Yes |
| Hedge calculator | No | Yes |
| CLV tracking | No | Yes |
| Performance history | Summary only (weekly ROI) | Full detail |
| Player prop edges | No | Yes |
| Odds movement sparklines | No | Yes |
| Email alerts | No | Yes |
| Region/book filtering | Quebec only | All regions |

**Lock-in mechanism:** Performance tracking. Once a user has weeks/months of bet history in MoneyPuck, switching costs are high. This is the real moat, not the model itself.

**Confidence:** MEDIUM -- pricing is always a guess until tested. Competitor pricing is verified.

**Sources:**
- [OddsJam pricing (RotoWire review)](https://www.rotowire.com/betting/oddsjam-review)
- [BetQL pricing](https://www.fantasylabs.com/articles/best-apps-for-bettors/)
- [Betting tools comparison (Smartico)](https://www.smartico.ai/blog-post/best-sports-betting-analytics-tools)

---

## 4. Legal Considerations (Canada/Quebec)

### Summary: Selling betting information is legal. You are NOT a sportsbook.

**Key distinction:** MoneyPuck sells analytical information and tools. It does not accept bets, hold funds, or operate as a sportsbook. This is the same legal category as newspapers publishing odds, tipsters selling picks, or analytics tools like OddsJam.

### What you need:

1. **Terms of Service (mandatory):**
   - "MoneyPuck provides sports analytics for informational purposes only"
   - "We do not guarantee results or profits"
   - "Users are responsible for complying with local gambling laws"
   - "Past performance does not guarantee future results"
   - "This is not financial or investment advice"

2. **Quebec-specific requirements:**
   - **French language:** Quebec's Charter of the French Language (Bill 96, strengthened 2022) requires commercial websites serving Quebec consumers to be available in French. You are based in Quebec, so this likely applies.
   - **Age restriction:** Include 18+ age gate (Quebec gambling age is 18, not 19 like other provinces)
   - **Consumer protection:** Quebec consumer protection laws are aggressive. Avoid language that guarantees profits.

3. **Privacy (PIPEDA + Quebec Law 25):**
   - Quebec's Law 25 (in effect since Sept 2023) is Canada's strictest privacy law
   - Requires: privacy policy, consent for data collection, data breach notification, privacy impact assessment for any system collecting personal info
   - If collecting email/payment info, you MUST have a privacy policy and get explicit consent
   - Appoint a privacy officer (can be yourself for a small operation)

4. **Tax implications:**
   - Subscription revenue is taxable business income
   - Must charge QST (9.975%) + GST (5%) on subscriptions sold to Quebec/Canadian customers
   - Consider registering for GST/QST if revenue exceeds $30K/year (small supplier threshold)
   - Stripe handles tax calculation if you enable Stripe Tax

5. **What you do NOT need:**
   - Gambling license (you're not a sportsbook)
   - RACJ approval (you're not operating games of chance)
   - Money transmitter license (Stripe handles all payment processing)

### Risk Level: LOW

Selling sports analytics tools is well-established in Canada. OddsJam, BetQL, and many picks services operate freely. The main compliance burden is privacy law (Law 25) and French language requirements.

**Recommendation:** Get a 1-hour consult with a Quebec business lawyer before launch (~$200-400). Cover: ToS review, privacy policy, Law 25 compliance, tax registration.

**Confidence:** MEDIUM -- legal research via web search has limits. The general pattern (info services are legal) is well-established, but Quebec-specific requirements (Law 25, Bill 96) should be verified with a lawyer.

**Sources:**
- [JustAnswer: selling sports betting info in Canada](https://www.justanswer.com/canada-law/mlnaj-want-know-legal-canada-sell-sports.html)
- [Canada sports betting regulations 2025](https://durhampost.ca/understanding-canadas-sports-betting-regulations-in-2025)
- [Quebec sports betting legal status](https://theplayoffs.news/ca/sports-betting-quebec/)
- [Canada gambling laws 2026](https://www.bettingtop10.ca/legal-betting/)

---

## 5. Proving Model Performance Without Giving Away Picks

### Strategy: Delayed Transparency + Aggregate Stats

**The problem:** You need to prove the model works to attract paying users, but publishing picks in real-time eliminates the reason to pay.

### Recommended approach:

1. **Public track record page (free):**
   - Show aggregate stats: overall ROI%, win rate, total bets, Brier score
   - Updated daily AFTER games complete
   - Show monthly breakdown (e.g., "January: +14.2% ROI on 87 bets")
   - Show a ROI chart over time (equity curve)
   - This proves the model works without revealing WHICH bets to take

2. **Delayed pick publishing (free):**
   - Publish yesterday's picks with results after games complete
   - "Yesterday we identified 4 value bets. 3 hit for +$127 profit."
   - Shows specific examples but too late to act on

3. **Third-party verification:**
   - Use BetStamp or similar platform to independently verify your record
   - Links to verified record on your free tier / marketing page
   - Third-party verification is the gold standard for credibility

4. **Teaser picks (free):**
   - Show 1 of tonight's value bets (the weakest edge) for free
   - "Tonight's free pick: MTL ML at +165 (model: 43.2% vs market 37.7%)"
   - Gate the remaining picks behind the paywall

5. **Backtest results (marketing page):**
   - "2024-25 season backtest: $1K to $29.7K, 18.6% ROI, 60.1% win rate"
   - Disclose this is backtested, not live
   - Once you have live results, phase out backtest emphasis

### What NOT to do:
- Don't show win probability without context (users will reverse-engineer picks)
- Don't delay too long (24h+ feels like you're hiding something)
- Don't cherry-pick results (show losing months too)
- Don't show cumulative ROI without sample size

**Confidence:** MEDIUM -- these are industry-standard patterns. The specific implementation details need testing.

---

## 6. Email Collection & User Onboarding

### Strategy: Free tier requires email signup (no anonymous access)

**Flow:**
1. Landing page shows value prop + aggregate model performance
2. "Sign up free to see tonight's picks" -- email + password via Supabase Auth
3. Free user sees: tonight's games, model probabilities (delayed/limited)
4. CTA throughout: "Upgrade to Pro for full value bets, arb scanner, bet sizing"
5. Drip email sequence after signup

### Email collection patterns:

1. **Gate the free tier behind signup.** No anonymous access to model probabilities. This is your most valuable free feature -- trade it for an email.

2. **Drip sequence (post-signup):**
   - Day 0: Welcome + how to read the dashboard
   - Day 1: "Last night's results: 3/4 value bets hit, +$127"
   - Day 3: "This week's ROI: +8.3%. Here's how Pro users bet on these edges"
   - Day 7: "You've been using MoneyPuck for a week. Here's your free trial of Pro (3 days)"
   - Day 10: "Your Pro trial ended. Upgrade for $29/mo"
   - Weekly: "This week's model performance: X% ROI" (ongoing engagement)

3. **Email service:** Use Resend ($0 for 3K emails/mo) or Loops.so (free tier). Both have simple HTTP APIs -- no SDK needed for your stdlib server.

4. **Pre-launch email list:**
   - Before auth is built, add an email capture form to the current Railway dashboard
   - "Get notified when MoneyPuck Pro launches"
   - Collect emails now, convert later
   - Simple: POST to a Google Form or Supabase table

### Onboarding within the app:

1. First visit: brief tooltip tour ("This is your model probability", "This is the edge")
2. Show a "getting started" checklist: set bankroll, choose region, understand Kelly sizing
3. Track onboarding completion -- users who complete onboarding convert 2-3x better

**Confidence:** MEDIUM -- these are standard SaaS onboarding patterns. Conversion rates are domain-specific.

---

## 7. Implementation Phases (Auth & Monetization)

Based on all research above, here's the recommended build order:

### Phase 1: Email Gate + Supabase Auth (1-2 weeks)
- Set up Supabase project (free tier)
- Add JWT verification middleware to `ThreadingHTTPServer`
- Add login/signup pages (can be Supabase hosted UI initially)
- Gate the dashboard behind authentication
- Store user metadata in Supabase (or SQLite)
- **Why first:** You need users before you can charge them

### Phase 2: Free/Paid Tier Split (1 week)
- Add `tier` field to user profile (free/paid)
- Implement feature gating in API endpoints
- Free users: limited games, delayed data, no arbs/sizing
- Paid users: everything
- Add "Upgrade" CTAs throughout dashboard
- **Why second:** Establishes what paid users get

### Phase 3: Stripe Integration (1 week)
- Create Stripe products (MoneyPuck Pro Monthly, Annual)
- Add checkout session creation endpoint
- Add webhook handler for subscription events
- Wire subscription status to user tier
- Test with Stripe test mode
- **Why third:** Can't charge until tiers exist

### Phase 4: Public Track Record (1 week)
- Add public performance page (no login required)
- Show aggregate ROI, win rate, Brier score
- Delayed pick publishing (yesterday's results)
- Set up BetStamp or similar for third-party verification
- **Why fourth:** Marketing page for conversion

### Phase 5: Email Drip & Onboarding (1 week)
- Integrate Resend for transactional + drip emails
- Build onboarding flow for new users
- Set up conversion tracking
- **Why fifth:** Optimization after core monetization works

### Phase 6: Legal Compliance
- French language support (or at minimum, French ToS/privacy policy)
- Privacy policy compliant with Law 25
- Terms of Service with gambling disclaimers
- Age verification gate (18+)
- GST/QST tax setup via Stripe Tax
- **Why last:** Can launch English-only initially, add French before scaling

---

## 8. Architecture Impact

Adding auth and payments to the existing `ThreadingHTTPServer` requires:

1. **New endpoints:**
   - `POST /auth/verify` -- validate JWT (or just middleware on all endpoints)
   - `POST /api/checkout` -- create Stripe Checkout session
   - `POST /webhook/stripe` -- handle Stripe webhooks
   - `GET /api/user` -- get user profile + tier
   - `GET /api/performance` -- public track record (no auth)

2. **Middleware layer:**
   - JWT verification on protected endpoints
   - Tier checking for paid features
   - Rate limiting per user

3. **Database additions (SQLite or Supabase):**
   - `users` table: id, email, tier, stripe_customer_id, created_at
   - `subscriptions` table: user_id, stripe_subscription_id, status, current_period_end

4. **Frontend changes:**
   - Login/signup UI (or redirect to Supabase hosted page)
   - Upgrade CTA components
   - Feature gates (blur/lock paid features for free users)

5. **Environment variables to add:**
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
   - `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_MONTHLY`, `STRIPE_PRICE_ID_ANNUAL`

---

## 9. Key Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| French language requirement (Bill 96) | MEDIUM | Launch English-only, add French before marketing in Quebec. Consult lawyer. |
| Law 25 privacy compliance | MEDIUM | Write privacy policy before collecting emails. Simple for small operations. |
| Stripe account suspension (gambling-adjacent) | LOW | Stripe explicitly supports "information services." You're not processing bets. Clarify in Stripe application. |
| Model underperformance live vs backtest | HIGH | Be transparent about backtest vs live results. Don't oversell. Show losing periods. |
| Low conversion free->paid | MEDIUM | Test different free tier limits. Start generous, tighten if conversion is too low. |
| ThreadingHTTPServer scalability with auth | LOW | JWT verification is stateless and fast. Not a bottleneck until 1000s of concurrent users. |

---

## 10. Open Questions

- **Supabase vs Firebase Auth:** Both work. Supabase has better free tier and is more developer-friendly. But if you later want a real database, Supabase gives you Postgres too. Worth investigating if you want to migrate from SQLite.
- **Stripe Tax for Canadian sales:** Need to verify exact setup for QST+GST collection. Stripe Tax may handle this automatically.
- **BetStamp API:** Need to verify if BetStamp has an API for automated pick logging, or if it's manual entry only.
- **Email deliverability:** Betting-related emails often hit spam filters. Resend has good deliverability but test thoroughly.
