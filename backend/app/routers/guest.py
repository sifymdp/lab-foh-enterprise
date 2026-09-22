import html
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Bill, DiningSession, Table, TableQRCode
from app.services import menu_service
from app.services.floor_service import get_current_floor
from app.services.table_service import active_session_for_table
from app.services import ai_service
from app.schemas.ai import AIEventCreate
from urllib.parse import quote
from datetime import datetime, timezone
from app.schemas.common import CamelModel

from app.services.order_service import get_bill, list_orders, mark_paid, request_bill

router = APIRouter(prefix="/guest", tags=["guest"])

RESTAURANT_NAME = "FOH Restaurant"
CATEGORY_ORDER = ["Starters", "Mains", "Drinks", "Desserts"]


def _resolve_qr(db: Session, token: str) -> TableQRCode:
    qr = (
        db.query(TableQRCode)
        .filter(TableQRCode.token == token, TableQRCode.is_active.is_(True))
        .first()
    )
    if not qr:
        raise HTTPException(404, "Invalid or expired table token")
    return qr


def _slugify(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def _build_guest_menu_html(
    *,
    token: str,
    table: Table,
    restaurant_name: str,
    items_by_category: dict[str, list],
    guest_name: str | None,
    session_id: str | None,
) -> str:
    menu_json = json.dumps(
        {
            "token": token,
            "tableId": table.id,
            "sessionId": session_id,
            "tableNumber": table.number,
            "apiBase": settings.guest_menu_base_url.rstrip("/"),
        }
    )

    ordered_cats = [c for c in CATEGORY_ORDER if c in items_by_category]
    ordered_cats += sorted(k for k in items_by_category if k not in CATEGORY_ORDER)

    sidebar_html = []
    sections_html = []
    for i, category in enumerate(ordered_cats):
        slug = _slugify(category)
        sidebar_html.append(
            f'<button type="button" class="side-tab{" is-active" if i == 0 else ""}" '
            f'data-cat="cat-{slug}" onclick="selectCategory(\'cat-{slug}\')">'
            f'{html.escape(category)}</button>'
        )
        items_html = []
        for item in items_by_category[category]:
            desc = html.escape(item.description or "")
            items_html.append(
                f"""
                <article class="menu-item" data-id="{html.escape(item.id)}"
                         data-name="{html.escape(item.name)}"
                         data-price="{float(item.price):.2f}">
                  <div class="menu-item__info">
                    <h3>{html.escape(item.name)}</h3>
                    {f'<p class="desc">{desc}</p>' if desc else ''}
                    <p class="price">Γé╣{float(item.price):.2f}</p>
                  </div>
                  <div class="stepper">
                    <button type="button" class="stepper__btn" onclick="changeQty('{html.escape(item.id)}', -1)" aria-label="Remove one">ΓêÆ</button>
                    <span class="stepper__qty" id="qty-{html.escape(item.id)}">0</span>
                    <button type="button" class="stepper__btn stepper__btn--add" onclick="changeQty('{html.escape(item.id)}', 1)" aria-label="Add one">+</button>
                  </div>
                </article>
                """
            )
        sections_html.append(
            f'<section class="category{" is-active" if i == 0 else ""}" id="cat-{slug}">'
            f'<h2>{html.escape(category)}</h2>{"".join(items_html)}</section>'
        )

    welcome_line = (
        f"Welcome {html.escape(guest_name)} ┬╖ Table {html.escape(table.number)}"
        if guest_name
        else f"Table {html.escape(table.number)}"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(restaurant_name)} ΓÇö Table {html.escape(table.number)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --ink: #1c1b19; --cream: #faf6ef; --green: #26402f; --green-dark: #182a1e;
      --gold: #c89b3c; --gold-dark: #a9812e; --line: #e4dfd3; --muted: #6b6357; --red: #b3261e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: 'Inter', system-ui, sans-serif;
      background: var(--cream); color: var(--ink); padding-bottom: 84px;
    }}
    h1, h2 {{ font-family: 'Fraunces', serif; }}
    header {{
      background: var(--green); color: #fff; padding: 16px 16px;
      position: sticky; top: 0; z-index: 20;
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
    }}
    header h1 {{ margin: 0; font-size: 1.3rem; font-weight: 600; letter-spacing: -0.01em; }}
    header p {{ margin: 3px 0 0; opacity: 0.82; font-size: 0.82rem; }}
    .track-btn {{
      flex-shrink: 0; position: relative; background: rgba(255,255,255,0.12); color: #fff;
      border: 1px solid rgba(255,255,255,0.25); border-radius: 10px; padding: 8px 12px;
      font-size: 0.78rem; font-weight: 600; cursor: pointer; font-family: 'Inter', sans-serif;
    }}
    .track-btn__dot {{
      position: absolute; top: -4px; right: -4px; width: 10px; height: 10px;
      border-radius: 50%; background: var(--gold); display: none;
    }}
    .track-btn.has-active .track-btn__dot {{ display: block; }}

    .layout {{ display: flex; align-items: flex-start; }}
    .sidebar {{
      width: 92px; flex-shrink: 0; position: sticky; top: 64px;
      background: var(--green-dark); height: calc(100vh - 64px);
      display: flex; flex-direction: column; padding: 10px 0; overflow-y: auto;
    }}
    .side-tab {{
      border: none; background: transparent; color: rgba(255,255,255,0.65);
      font-family: 'Inter', sans-serif; font-size: 0.76rem; font-weight: 600;
      padding: 14px 8px; cursor: pointer; text-align: center; line-height: 1.2;
      border-left: 3px solid transparent;
    }}
    .side-tab.is-active {{ background: var(--cream); color: var(--green); border-left-color: var(--gold); }}

    main {{ flex: 1; min-width: 0; padding: 16px; }}
    .category {{ display: none; }}
    .category.is-active {{ display: block; }}
    .category h2 {{ font-size: 1.15rem; font-weight: 500; margin: 0 0 14px; color: var(--green); }}
    .menu-item {{
      display: flex; gap: 12px; align-items: center;
      background: #fff; border-radius: 14px; padding: 14px;
      margin-bottom: 10px; border: 1px solid var(--line);
    }}
    .menu-item__info {{ flex: 1; min-width: 0; }}
    .menu-item h3 {{ margin: 0 0 3px; font-size: 0.96rem; font-weight: 600; font-family: 'Inter', sans-serif; }}
    .desc {{ margin: 0 0 6px; font-size: 0.8rem; color: var(--muted); line-height: 1.4; }}
    .price {{ margin: 0; font-weight: 600; color: var(--green); font-size: 0.9rem; }}
    .stepper {{
      display: flex; align-items: center; gap: 8px; flex-shrink: 0;
      background: var(--cream); border-radius: 999px; padding: 4px;
    }}
    .stepper__btn {{
      width: 28px; height: 28px; border-radius: 50%; border: none;
      background: #fff; color: var(--green); font-size: 1.05rem; font-weight: 700;
      cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,0.08); line-height: 1;
    }}
    .stepper__btn--add {{ background: var(--gold); color: #fff; }}
    .stepper__qty {{ min-width: 14px; text-align: center; font-weight: 600; font-size: 0.86rem; }}

    .cart-bar {{
      position: fixed; bottom: 0; left: 0; right: 0;
      background: var(--gold); color: #fff; border: none;
      padding: 15px 18px calc(15px + env(safe-area-inset-bottom));
      display: none; align-items: center; justify-content: space-between;
      z-index: 25; cursor: pointer; font-family: 'Inter', sans-serif;
    }}
    .cart-bar.is-visible {{ display: flex; }}
    .cart-bar__left {{ font-weight: 600; font-size: 0.92rem; }}
    .cart-bar__right {{ font-weight: 700; font-size: 0.92rem; }}

    .overlay {{
      position: fixed; inset: 0; background: rgba(24,42,30,0.55);
      backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
      display: none; align-items: flex-end; z-index: 50;
    }}
    .overlay--center {{ align-items: center; justify-content: center; }}
    .overlay--top {{ z-index: 70; }}
    .overlay--payment {{ z-index: 60; }}
    .overlay.is-open {{ display: flex; }}
    .sheet {{
      background: var(--cream); width: 100%; max-height: 82vh; overflow-y: auto;
      border-radius: 20px 20px 0 0; padding: 18px 18px calc(18px + env(safe-area-inset-bottom));
    }}
    .sheet__header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }}
    .sheet__header h2 {{ margin: 0; font-size: 1.15rem; }}
    .sheet__close {{
      border: none; background: var(--line); width: 30px; height: 30px; border-radius: 50%;
      font-size: 1rem; cursor: pointer; color: var(--ink);
    }}
    .review-line {{
      display: flex; align-items: center; justify-content: space-between; gap: 10px;
      padding: 10px 0; border-bottom: 1px solid var(--line);
    }}
    .review-line__name {{ font-size: 0.9rem; font-weight: 600; }}
    .review-line__price {{ font-size: 0.78rem; color: var(--muted); }}
    .review-total {{
      display: flex; justify-content: space-between; align-items: center;
      margin-top: 14px; padding-top: 12px; font-weight: 700; font-size: 1.05rem; color: var(--green);
    }}
    .btn-confirm {{
      width: 100%; margin-top: 16px; border: none; background: var(--green); color: #fff;
      padding: 14px; border-radius: 12px; font-size: 0.95rem; font-weight: 600; cursor: pointer;
      font-family: 'Inter', sans-serif;
    }}
    .btn-confirm:disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .empty-note {{ color: var(--muted); font-size: 0.88rem; padding: 20px 0; text-align: center; }}

    .status-tracker {{ background: #fff; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid var(--line); }}
    .status-tracker__items {{ font-size: 0.83rem; color: var(--muted); margin-bottom: 12px; }}
    .status-steps {{ display: flex; align-items: center; }}
    .status-step {{ display: flex; flex-direction: column; align-items: center; flex: 1; position: relative; }}
    .status-step__dot {{
      width: 22px; height: 22px; border-radius: 50%; background: var(--line);
      display: flex; align-items: center; justify-content: center; z-index: 1;
      font-size: 0.7rem; color: #fff; font-weight: 700;
    }}
    .status-step__label {{ font-size: 0.66rem; color: var(--muted); margin-top: 6px; text-align: center; }}
    .status-step__line {{ position: absolute; top: 11px; left: 50%; width: 100%; height: 2px; background: var(--line); z-index: 0; }}
    .status-step:first-child .status-step__line {{ display: none; }}
    .status-step.is-done .status-step__dot {{ background: var(--green); }}
    .status-step.is-done .status-step__line {{ background: var(--green); }}
    .status-step.is-current .status-step__dot {{ background: var(--gold); }}
    .status-tracker.rejected .status-step__dot {{ background: var(--red) !important; }}
    .status-tracker.rejected .status-step__line {{ background: var(--red) !important; }}

    .toast {{
      position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
      background: var(--green); color: #fff; padding: 10px 18px; border-radius: 10px;
      font-size: 0.88rem; font-weight: 500; display: none; z-index: 60;
    }}
    .toast.error {{ background: var(--red); }}
    #bill-banner:empty {{ display: none; }}
    @keyframes bill-pulse {{
      0%, 100% {{ box-shadow: 0 0 0 0 rgba(200,155,60,0.5); }}
      50% {{ box-shadow: 0 0 0 6px rgba(200,155,60,0); }}
    }}
    #top-banners {{
      position: fixed; left: 16px; right: 16px; z-index: 30;
      display: flex; flex-direction: column; gap: 8px;
    }}
    .bill-banner-btn {{
      width: 100%; border: none; background: var(--gold); color: #fff;
      padding: 14px 16px; display: flex; justify-content: space-between; align-items: center;
      font-family: 'Inter', sans-serif; font-size: 0.92rem; font-weight: 700; cursor: pointer;
      border-radius: 12px; animation: bill-pulse 1.6s infinite; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    .bill-banner-btn.is-paid {{ background: var(--green); animation: none; }}
    .pay-field {{
      width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px;
      font-family: 'Inter', sans-serif; font-size: 0.88rem; margin-bottom: 10px;
    }}
    .pay-row {{ display: flex; gap: 10px; }}
    .pay-row .pay-field {{ flex: 1; }}
    .demo-note {{ font-size: 0.75rem; color: var(--muted); text-align: center; margin-top: 8px; }}

    .pay-method-grid {{ display: flex; flex-direction: column; gap: 10px; }}
    .pay-method-btn {{
      display: flex; align-items: center; gap: 14px; width: 100%; text-align: left;
      border: 1px solid var(--line); background: #fff; border-radius: 14px; padding: 14px 16px;
      cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s;
      font-family: 'Inter', sans-serif;
    }}
    .pay-method-btn:hover {{ border-color: var(--gold); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .pay-method-btn__icon {{
      width: 42px; height: 42px; border-radius: 11px; display: flex; align-items: center;
      justify-content: center; font-size: 20px; flex-shrink: 0; background: var(--cream);
    }}
    .pay-method-btn__text {{ flex: 1; }}
    .pay-method-btn__title {{ font-weight: 700; font-size: 0.94rem; color: var(--ink); }}
    .pay-method-btn__sub {{ font-size: 0.76rem; color: var(--muted); margin-top: 2px; }}
    .pay-method-btn__chevron {{ color: var(--muted); font-size: 1rem; }}

    .payment-card {{
      background: var(--cream); border-radius: 20px; padding: 28px 24px;
      max-width: 360px; width: calc(100% - 32px); text-align: center;
    }}
    .payment-card h2 {{ margin: 0 0 4px; font-size: 1.1rem; }}
    .payment-card .amount {{ font-size: 1.4rem; font-weight: 700; color: var(--green); margin: 4px 0 18px; }}
    .payment-card img {{ border-radius: 14px; border: 1px solid var(--line); margin-bottom: 14px; }}
    .ordering-locked .stepper__btn {{ opacity: 0.35; pointer-events: none; }}
    .overlay--center {{ align-items: center; }}
    .action-card {{
      background: var(--cream); border-radius: 18px; padding: 28px 24px;
      max-width: 340px; width: calc(100% - 32px); text-align: center;
    }}
    .action-card__icon {{ font-size: 36px; margin-bottom: 10px; }}
    .action-card h2 {{ margin: 0 0 8px; font-size: 1.15rem; }}
    .action-card p {{ margin: 0 0 20px; font-size: 0.9rem; color: var(--muted); line-height: 1.4; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{html.escape(restaurant_name)}</h1>
      <p>{welcome_line}</p>
    </div>
    <button type="button" class="track-btn" onclick="callWaiter()">≡ƒÖï Call waiter</button>
    <button type="button" class="track-btn" id="bill-btn" style="display:none;" onclick="toggleOverlay('bill-overlay', true)">
      ≡ƒº╛ Bill
      <span class="track-btn__dot"></span>
    </button>
    <button type="button" class="track-btn" id="track-btn" onclick="toggleOverlay('track-overlay', true)">
      Track order
      <span class="track-btn__dot"></span>
    </button>
  </header>

  <div class="layout">
    <nav class="sidebar">{"".join(sidebar_html)}</nav>
    <main>
      {"".join(sections_html) if sections_html else '<p>No menu items available right now.</p>'}
    </main>
  </div>

  <div id="toast" class="toast"></div>

  <div class="overlay overlay--center overlay--top" id="action-card-overlay">
    <div class="action-card">
      <div class="action-card__icon" id="action-card-icon">≡ƒÖï</div>
      <h2 id="action-card-title"></h2>
      <p id="action-card-message"></p>
      <button type="button" class="btn-confirm" onclick="dismissActionCard()">Got it</button>
    </div>
  </div>

  <div class="overlay overlay--center overlay--payment" id="upi-overlay" onclick="if(event.target===this) toggleOverlay('upi-overlay', false)">
    <div class="payment-card" onclick="event.stopPropagation()">
      <h2>Scan to pay</h2>
      <div class="amount" id="upi-amount"></div>
      <div id="upi-qr-holder"></div>
      <p class="demo-note" style="margin-bottom:16px;">Scan with any UPI app ΓÇö GPay, PhonePe, Paytm, etc.</p>
      <button type="button" class="btn-confirm" onclick="confirmUpiPaid()">I've completed the payment</button>
      <button type="button" class="btn btn-ghost" style="margin-top:8px;" onclick="toggleOverlay('upi-overlay', false)">Cancel</button>
    </div>
  </div>

  <div class="overlay overlay--center overlay--payment" id="card-overlay" onclick="if(event.target===this) toggleOverlay('card-overlay', false)">
    <div class="payment-card" onclick="event.stopPropagation()">
      <h2>Pay by card</h2>
      <div class="amount" id="card-amount"></div>
      <input class="pay-field" placeholder="Card number" maxlength="19" value="4242 4242 4242 4242" />
      <div class="pay-row">
        <input class="pay-field" placeholder="MM/YY" maxlength="5" value="12/28" />
        <input class="pay-field" placeholder="CVC" maxlength="3" value="123" />
      </div>
      <button type="button" class="btn-confirm" onclick="confirmCardPaid()">Pay now</button>
      <button type="button" class="btn btn-ghost" style="margin-top:8px;" onclick="toggleOverlay('card-overlay', false)">Cancel</button>
      <p class="demo-note">Demo mode ΓÇö no real card is charged.</p>
    </div>
  </div>

  <div class="overlay" id="bill-overlay" onclick="if(event.target===this) toggleOverlay('bill-overlay', false)">
    <div class="sheet">
      <div class="sheet__header">
        <h2>Your bill</h2>
        <button type="button" class="sheet__close" onclick="toggleOverlay('bill-overlay', false)">Γ£ò</button>
      </div>
      <div id="bill-detail"></div>
    </div>
  </div>

  <button type="button" class="cart-bar" id="cart-bar" onclick="toggleOverlay('cart-overlay', true)">
    <span class="cart-bar__left" id="cart-bar-count">0 items</span>
    <span class="cart-bar__right" id="cart-bar-total">Γé╣0.00 ┬╖ Review order</span>
  </button>

  <div class="overlay" id="cart-overlay" onclick="if(event.target===this) toggleOverlay('cart-overlay', false)">
    <div class="sheet">
      <div class="sheet__header">
        <h2>Review your order</h2>
        <button type="button" class="sheet__close" onclick="toggleOverlay('cart-overlay', false)">Γ£ò</button>
      </div>
      <div id="review-lines"></div>
      <div class="review-total"><span>Total</span><span id="review-total">Γé╣0.00</span></div>
      <button type="button" id="confirm-order" class="btn-confirm" onclick="placeOrder()">Place Order</button>
    </div>
  </div>

  <div class="overlay" id="track-overlay" onclick="if(event.target===this) toggleOverlay('track-overlay', false)">
    <div class="sheet">
      <div class="sheet__header">
        <h2>Your order status</h2>
        <button type="button" class="sheet__close" onclick="toggleOverlay('track-overlay', false)">Γ£ò</button>
      </div>
      <div id="order-status-panel"><p class="empty-note">No orders placed yet.</p></div>
      <button type="button" id="request-bill-btn" class="btn-confirm" style="display:none;" onclick="toggleOverlay('confirm-bill-overlay', true)">
        Request the bill
      </button>
    </div>
  </div>

  <div class="overlay" id="confirm-bill-overlay" onclick="if(event.target===this) toggleOverlay('confirm-bill-overlay', false)">
    <div class="sheet">
      <h2 style="margin:0 0 8px;font-size:1.1rem;">Ready for the bill?</h2>
      <p class="empty-note" style="padding:0 0 16px;text-align:left;">
        You won't be able to order anything else after this. If you'd like something more, order it first.
      </p>
      <div style="display:flex;gap:8px;">
        <button type="button" class="btn-confirm" style="background:#94a3b8;" onclick="toggleOverlay('confirm-bill-overlay', false)">Not yet</button>
        <button type="button" class="btn-confirm" onclick="confirmRequestBill()">Yes, get my bill</button>
      </div>
    </div>
  </div>

  <script>
    const CONFIG = {menu_json};
    const API_BASE = window.location.origin;
    const CART_KEY = 'foh_cart_' + CONFIG.tableId;
    let cart = {{}};
    try {{
      const saved = localStorage.getItem(CART_KEY);
      if (saved) cart = JSON.parse(saved);
    }} catch (e) {{ cart = {{}}; }}

    function saveCart() {{
      try {{ localStorage.setItem(CART_KEY, JSON.stringify(cart)); }} catch (e) {{ /* ignore */ }}
    }}
    const STEPS = ['PENDING', 'APPROVED', 'PREPARING', 'READY'];
    const STEP_LABELS = {{ PENDING: 'Waiting for approval', APPROVED: 'Approved', PREPARING: 'Preparing', READY: 'Ready to serve' }};
    const CATEGORY_ICONS = {{ Starters: '≡ƒÑú', Mains: '≡ƒì╜∩╕Å', Drinks: '≡ƒì╖', Desserts: '≡ƒºü' }};
    let hasExistingBill = false;
    let waiterCallAcknowledged = false;

    function showToast(msg, isError) {{
      const el = document.getElementById('toast');
      el.textContent = msg;
      el.className = 'toast' + (isError ? ' error' : '');
      el.style.display = 'block';
      setTimeout(() => {{ el.style.display = 'none'; }}, 3000);
    }}

    function selectCategory(id) {{
      document.querySelectorAll('.side-tab').forEach(t => t.classList.toggle('is-active', t.dataset.cat === id));
      document.querySelectorAll('.category').forEach(c => c.classList.toggle('is-active', c.id === id));
    }}

    function toggleOverlay(id, open) {{
      document.getElementById(id).classList.toggle('is-open', open);
    }}

    function changeQty(id, delta) {{
      const row = document.querySelector('.menu-item[data-id="' + id + '"]');
      if (!row) return;
      const name = row.dataset.name;
      const price = parseFloat(row.dataset.price);
      if (!cart[id]) cart[id] = {{ id, name, price, qty: 0 }};
      cart[id].qty = Math.max(0, cart[id].qty + delta);
      document.getElementById('qty-' + id).textContent = cart[id].qty;
      renderCartBar();
      saveCart();
    }}

    function cartEntries() {{
      return Object.values(cart).filter(i => i.qty > 0);
    }}

    function renderCartBar() {{
      const entries = cartEntries();
      const bar = document.getElementById('cart-bar');
      const count = entries.reduce((sum, i) => sum + i.qty, 0);
      const total = entries.reduce((sum, i) => sum + i.price * i.qty, 0);
      bar.classList.toggle('is-visible', count > 0);
      document.getElementById('cart-bar-count').textContent = count + (count === 1 ? ' item' : ' items');
      document.getElementById('cart-bar-total').textContent = 'Γé╣' + total.toFixed(2) + ' ┬╖ Review order';
      renderReviewSheet();
    }}

    function renderReviewSheet() {{
      const entries = cartEntries();
      const linesEl = document.getElementById('review-lines');
      const totalEl = document.getElementById('review-total');
      const btn = document.getElementById('confirm-order');
      if (!entries.length) {{
        linesEl.innerHTML = '<p class="empty-note">Your cart is empty.</p>';
        totalEl.textContent = 'Γé╣0.00';
        btn.disabled = true;
        return;
      }}
      let total = 0;
      linesEl.innerHTML = entries.map(i => {{
        total += i.price * i.qty;
        return '<div class="review-line">'
          + '<div><div class="review-line__name">' + i.qty + '├ù ' + i.name + '</div>'
          + '<div class="review-line__price">Γé╣' + i.price.toFixed(2) + ' each</div></div>'
          + '<div class="review-line__price">Γé╣' + (i.price * i.qty).toFixed(2) + '</div>'
          + '</div>';
      }}).join('');
      totalEl.textContent = 'Γé╣' + total.toFixed(2);
      btn.disabled = false;
    }}

    function statusIndex(order) {{
      if (order.approvalStatus === 'REJECTED') return -1;
      if (order.approvalStatus === 'PENDING') return 0;
      if (order.status === 'READY' || order.status === 'SERVED') return 3;
      if (order.status === 'PREPARING') return 2;
      return 1;
    }}

    function renderOrderStatuses(orders) {{
      const panel = document.getElementById('order-status-panel');
      const trackBtn = document.getElementById('track-btn');
      if (!orders.length) {{
        panel.innerHTML = '<p class="empty-note">No orders placed yet.</p>';
        trackBtn.classList.remove('has-active');
        return;
      }}
      const hasActive = orders.some(o => o.approvalStatus !== 'REJECTED' && o.status !== 'SERVED');
      trackBtn.classList.toggle('has-active', hasActive);
      const requestBtn = document.getElementById('request-bill-btn');
      const approvedOrders = orders.filter(o => o.approvalStatus === 'APPROVED');
      requestBtn.style.display = (approvedOrders.length > 0 && !hasExistingBill) ? 'block' : 'none';
      panel.innerHTML = orders.map(order => {{
        const itemsText = order.items.map(i => i.quantity + '├ù ' + i.itemName).join(', ');
        if (order.approvalStatus === 'REJECTED') {{
          return '<div class="status-tracker rejected">'
            + '<div class="status-tracker__items">' + itemsText + '</div>'
            + '<div class="status-step is-current" style="align-items:flex-start"><span class="status-step__dot">Γ£ò</span>'
            + '<span class="status-step__label">Order was declined</span></div></div>';
        }}
        const idx = statusIndex(order);
        const steps = STEPS.map((s, i) => {{
          const cls = i < idx ? 'is-done' : i === idx ? 'is-current' : '';
          return '<div class="status-step ' + cls + '">'
            + '<span class="status-step__line"></span>'
            + '<span class="status-step__dot">' + (i < idx ? 'Γ£ô' : '') + '</span>'
            + '<span class="status-step__label">' + STEP_LABELS[s] + '</span>'
            + '</div>';
        }}).join('');
        return '<div class="status-tracker">'
          + '<div class="status-tracker__items">' + itemsText + '</div>'
          + '<div class="status-steps">' + steps + '</div></div>';
      }}).join('');
    }}

    async function pollOrderStatus() {{
      try {{
        const res = await fetch(API_BASE + '/guest/orders?token=' + encodeURIComponent(CONFIG.token));
        if (!res.ok) return;
        const orders = await res.json();
        orders.sort((a, b) => new Date(b.placedAt) - new Date(a.placedAt));
        renderOrderStatuses(orders);
      }} catch (e) {{ /* try again next poll */ }}
    }}

    async function placeOrder() {{
      const entries = cartEntries();
      if (!entries.length) return;
      const btn = document.getElementById('confirm-order');
      btn.disabled = true;
      btn.textContent = 'SendingΓÇª';
      try {{
        const res = await fetch(API_BASE + '/orders?token=' + encodeURIComponent(CONFIG.token), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            tableId: CONFIG.tableId,
            items: entries.map(i => ({{ menuItemId: i.id, quantity: i.qty }})),
          }}),
        }});
        if (!res.ok) {{
          const err = await res.json().catch(() => ({{}}));
          throw new Error(err.detail || res.statusText);
        }}
        Object.keys(cart).forEach(k => {{ cart[k].qty = 0; const el = document.getElementById('qty-' + k); if (el) el.textContent = '0'; }});
        renderCartBar();
        saveCart();
        toggleOverlay('cart-overlay', false);
        showToast('Order placed ΓÇö thank you!');
        pollOrderStatus();
      }} catch (e) {{
        showToast(e.message || 'Could not place order', true);
        toggleOverlay('cart-overlay', false);
      }} finally {{
        btn.textContent = 'Place Order';
      }}
    }}

    let wasOrderingLocked = false;

    function markSeen(key) {{ try {{ localStorage.setItem(key, '1'); }} catch (e) {{}} }}
    function hasSeen(key) {{ try {{ return !!localStorage.getItem(key); }} catch (e) {{ return false; }} }}

    function showActionCard(icon, title, message) {{
      const payload = {{ icon, title, message }};
      try {{ localStorage.setItem('foh_pending_card', JSON.stringify(payload)); }} catch (e) {{}}
      document.getElementById('action-card-icon').textContent = icon;
      document.getElementById('action-card-title').textContent = title;
      document.getElementById('action-card-message').textContent = message;
      toggleOverlay('action-card-overlay', true);
    }}

    function dismissActionCard() {{
      try {{ localStorage.removeItem('foh_pending_card'); }} catch (e) {{}}
      toggleOverlay('action-card-overlay', false);
    }}

    function restorePendingCard() {{
      try {{
        const saved = localStorage.getItem('foh_pending_card');
        if (!saved) return;
        const {{ icon, title, message }} = JSON.parse(saved);
        document.getElementById('action-card-icon').textContent = icon;
        document.getElementById('action-card-title').textContent = title;
        document.getElementById('action-card-message').textContent = message;
        toggleOverlay('action-card-overlay', true);
      }} catch (e) {{}}
    }}

    function setOrderingLocked(locked) {{
      document.body.classList.toggle('ordering-locked', locked);
      document.getElementById('cart-bar').style.display = locked ? 'none' : '';
      if (locked) {{
        Object.keys(cart).forEach(k => {{ cart[k].qty = 0; const el = document.getElementById('qty-' + k); if (el) el.textContent = '0'; }});
        renderCartBar();
        saveCart();
      }}
      if (locked && !wasOrderingLocked) {{
        const key = 'foh_seen_locked_' + CONFIG.sessionId;
        if (!hasSeen(key)) {{
          markSeen(key);
          showActionCard('≡ƒöÆ', 'Orders are closed', 'Your bill has been requested. Need something else? Tap Call waiter.');
        }}
      }}
      wasOrderingLocked = locked;
    }}

    function renderBill(bill) {{
      hasExistingBill = !!bill;
      setOrderingLocked(!!bill);
      const billBtn = document.getElementById('bill-btn');
      if (!bill) {{ billBtn.style.display = 'none'; return; }}
      const isPaid = bill.status === 'PAID';
      billBtn.style.display = 'inline-flex';
      billBtn.classList.toggle('has-active', !isPaid);

      const seenKey = 'foh_seen_bill_' + bill.id + '_' + bill.status;
      if (!hasSeen(seenKey)) {{
        markSeen(seenKey);
        if (isPaid) {{
          showActionCard('Γ£à', 'Bill paid', 'Thank you! We hope to see you again soon.');
        }} else {{
          showActionCard('≡ƒº╛', 'Your bill is ready', 'Γé╣' + bill.total.toFixed(2) + ' ΓÇö tap the Bill button anytime to view or pay.');
        }}
      }}

      const groups = {{}};
      bill.items.forEach(i => {{
        if (!groups[i.category]) groups[i.category] = [];
        groups[i.category].push(i);
      }});
      const catOrder = ['Starters', 'Mains', 'Drinks', 'Desserts'];
      const cats = catOrder.filter(c => groups[c]).concat(Object.keys(groups).filter(c => !catOrder.includes(c)));
      const rows = cats.map(cat => {{
        const items = groups[cat].map(i =>
          '<div class="review-line"><span>' + i.quantity + '├ù ' + i.itemName + '</span><span>Γé╣' + i.lineTotal.toFixed(2) + '</span></div>'
        ).join('');
        return '<div style="font-weight:700;font-size:0.85rem;color:#475569;margin:10px 0 4px;">'
          + (CATEGORY_ICONS[cat] || 'ΓÇó') + ' ' + cat.toUpperCase() + '</div>' + items;
      }}).join('');

      const statusLine = isPaid
        ? 'Γ£à PAID' + (bill.paymentMethod ? ' ┬╖ via ' + bill.paymentMethod : '')
        : 'ΓÅ│ AWAITING PAYMENT';

      const payBlock = isPaid ? '' : `
        <div style="border-top:1px dashed var(--line);margin-top:14px;padding-top:14px;">
          <h3 style="margin:0 0 12px;font-size:0.95rem;">Choose a payment method</h3>
          <div class="pay-method-grid">
            <button type="button" class="pay-method-btn" onclick="showUpiPayment(${{bill.total}})">
              <span class="pay-method-btn__icon">≡ƒô▒</span>
              <span class="pay-method-btn__text">
                <div class="pay-method-btn__title">UPI</div>
                <div class="pay-method-btn__sub">GPay, PhonePe, Paytm & more</div>
              </span>
              <span class="pay-method-btn__chevron">ΓÇ║</span>
            </button>
            <button type="button" class="pay-method-btn" onclick="showCardPayment(${{bill.total}})">
              <span class="pay-method-btn__icon">≡ƒÆ│</span>
              <span class="pay-method-btn__text">
                <div class="pay-method-btn__title">Card</div>
                <div class="pay-method-btn__sub">Debit or credit card</div>
              </span>
              <span class="pay-method-btn__chevron">ΓÇ║</span>
            </button>
            <button type="button" class="pay-method-btn" onclick="requestCashPayment()">
              <span class="pay-method-btn__icon">≡ƒÆ╡</span>
              <span class="pay-method-btn__text">
                <div class="pay-method-btn__title">Cash</div>
                <div class="pay-method-btn__sub">Pay your waiter directly</div>
              </span>
              <span class="pay-method-btn__chevron">ΓÇ║</span>
            </button>
          </div>
        </div>
      `;

      document.getElementById('bill-detail').innerHTML = rows
        + '<div class="review-total"><span>Total</span><span>Γé╣' + bill.total.toFixed(2) + '</span></div>'
        + '<div style="text-align:center;margin-top:12px;font-weight:700;color:' + (isPaid ? '#0f766e' : '#b45309') + ';">'
        + statusLine + '</div>'
        + payBlock;
    }}

    async function showUpiPayment(amount) {{
      toggleOverlay('card-overlay', false);
      toggleOverlay('upi-overlay', true);
      document.getElementById('upi-amount').textContent = 'Γé╣' + amount.toFixed(2);
      const holder = document.getElementById('upi-qr-holder');
      holder.innerHTML = '<p class="demo-note">Loading QRΓÇª</p>';
      try {{
        const res = await fetch(API_BASE + '/guest/upi-qr?token=' + encodeURIComponent(CONFIG.token));
        const data = await res.json();
        const qrImg = 'https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=' + encodeURIComponent(data.upiLink);
        holder.innerHTML = '<img src="' + qrImg + '" alt="UPI QR" width="220" height="220" />';
      }} catch (e) {{
        holder.innerHTML = '<p class="demo-note">Could not load QR code.</p>';
      }}
    }}

    async function confirmUpiPaid() {{
      try {{
        const res = await fetch(API_BASE + '/guest/pay-upi?token=' + encodeURIComponent(CONFIG.token), {{ method: 'POST' }});
        if (!res.ok) throw new Error();
        toggleOverlay('upi-overlay', false);
        pollBillStatus();
      }} catch (e) {{
        showActionCard('ΓÜá∩╕Å', 'Payment not confirmed', 'Please try again or ask your waiter for help.');
      }}
    }}

    function showCardPayment(amount) {{
      toggleOverlay('upi-overlay', false);
      toggleOverlay('card-overlay', true);
      document.getElementById('card-amount').textContent = 'Γé╣' + amount.toFixed(2);
    }}

    async function confirmCardPaid() {{
      try {{
        const res = await fetch(API_BASE + '/guest/pay-card?token=' + encodeURIComponent(CONFIG.token), {{ method: 'POST' }});
        if (!res.ok) throw new Error();
        toggleOverlay('card-overlay', false);
        pollBillStatus();
      }} catch (e) {{
        showActionCard('ΓÜá∩╕Å', 'Payment failed', 'Please try again.');
      }}
    }}

    async function requestCashPayment() {{
      try {{
        const statusRes = await fetch(API_BASE + '/guest/waiter-status?token=' + encodeURIComponent(CONFIG.token) + '&event_type=CASH_PAYMENT_REQUEST');
        const status = statusRes.ok ? await statusRes.json() : null;
        if (status) {{
          showActionCard(
            '≡ƒÆ╡',
            'Already on the way',
            status.acknowledged
              ? 'Your waiter is coming to collect the cash payment now.'
              : 'Your waiter has already been notified about your cash payment.'
          );
          return;
        }}
        await fetch(API_BASE + '/guest/request-cash-payment?token=' + encodeURIComponent(CONFIG.token), {{ method: 'POST' }});
        showActionCard('≡ƒÆ╡', 'Waiter notified', 'They\\u2019ll come collect the cash payment shortly. Please have the amount ready.');
      }} catch (e) {{
        showActionCard('ΓÜá∩╕Å', 'Could not notify waiter', 'Please try again.');
      }}
    }}

    async function confirmRequestBill() {{
      try {{
        const res = await fetch(API_BASE + '/guest/request-bill?token=' + encodeURIComponent(CONFIG.token), {{ method: 'POST' }});
        if (!res.ok) throw new Error('Could not request bill');
        toggleOverlay('confirm-bill-overlay', false);
        toggleOverlay('track-overlay', false);
        pollBillStatus();
      }} catch (e) {{
        showToast('Could not request bill', true);
      }}
    }}

    async function callWaiter() {{
      try {{
        const statusRes = await fetch(API_BASE + '/guest/waiter-status?token=' + encodeURIComponent(CONFIG.token) + '&event_type=WAITER_CALL');
        const status = statusRes.ok ? await statusRes.json() : null;
        if (status) {{
          showActionCard(
            '≡ƒÖÅ',
            'We\\u2019ve got your request',
            status.acknowledged
              ? 'Your waiter is already on the way ΓÇö thank you for your patience.'
              : 'Your waiter has already been notified and will be with you shortly.'
          );
          return;
        }}
        await fetch(API_BASE + '/guest/call-waiter?token=' + encodeURIComponent(CONFIG.token), {{ method: 'POST' }});
        showActionCard('≡ƒÖï', 'Waiter notified', 'They will be with you shortly!');
      }} catch (e) {{
        showActionCard('ΓÜá∩╕Å', 'Could not reach the waiter', 'Please try calling again.');
      }}
    }}

    async function pollWaiterStatus() {{
      try {{
        const res = await fetch(API_BASE + '/guest/waiter-status?token=' + encodeURIComponent(CONFIG.token));
        if (!res.ok) return;
        const status = await res.json();
        if (!status) {{ waiterCallAcknowledged = false; return; }}
        if (status.acknowledged && !waiterCallAcknowledged) {{
          showToast('≡ƒÜ╢ Waiter is on the way!');
        }}
        waiterCallAcknowledged = status.acknowledged;
      }} catch (e) {{ /* try again next poll */ }}
    }}

    

   
   

    async function pollBillStatus() {{
      try {{
        const res = await fetch(API_BASE + '/guest/bill?token=' + encodeURIComponent(CONFIG.token));
        if (!res.ok) return;
        const bill = await res.json();
        renderBill(bill);
      }} catch (e) {{ /* try again next poll */ }}
    }}

    

    Object.values(cart).forEach(item => {{
      const el = document.getElementById('qty-' + item.id);
      if (el) el.textContent = item.qty;
    }});
    renderCartBar();

    restorePendingCard();
    pollOrderStatus();
    pollBillStatus();
    pollWaiterStatus();
    setInterval(pollOrderStatus, 4000);
    setInterval(pollBillStatus, 4000);
    setInterval(pollWaiterStatus, 4000);
  </script>
</body>
</html>"""


@router.get("/menu")
def guest_menu(
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    qr = _resolve_qr(db, token)
    table = db.get(Table, qr.table_id)
    if not table:
        raise HTTPException(404, "Table not found")

    try:
        floor = get_current_floor(db)
        restaurant_name = floor.name or RESTAURANT_NAME
    except Exception:
        restaurant_name = RESTAURANT_NAME

    session = active_session_for_table(db, qr.table_id)

    items = menu_service.list_available_models(db)
    by_category: dict[str, list] = defaultdict(list)
    for item in items:
        by_category[item.category].append(item)

    page = _build_guest_menu_html(
        token=token,
        table=table,
        restaurant_name=restaurant_name,
        items_by_category=dict(by_category),
        guest_name=session.guest_name if session else None,
        session_id=session.id if session else None,
    )
    return HTMLResponse(page)


@router.get("/orders")
def guest_order_status(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    session = active_session_for_table(db, qr.table_id)
    if not session:
        return []
    orders = list_orders(db, session_id=session.id)
    return [o.model_dump(by_alias=True) for o in orders]


class GuestPayRequest(CamelModel):
    token: str
    split_count: int = 1
    amount_paid: float = 0.0
    tip: float = 0.0
    payment_method: str = "CARD"  # APPLE_PAY, GOOGLE_PAY, CARD, UPI, CASH
    guest_name: str | None = None


@router.get("/bill")
def get_guest_bill(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Retrieve the live itemized bill, unpaid exposure, and payment status for this table."""
    qr = _resolve_qr(db, token)
    table = db.get(Table, qr.table_id)
    if not table:
        raise HTTPException(404, "Table not found")

    session = active_session_for_table(db, table.id)
    if not session:
        # Check if table was recently in BILLING or has a completed session
        session = (
            db.query(DiningSession)
            .filter(DiningSession.table_id == table.id)
            .order_by(DiningSession.seated_at.desc())
            .first()
        )
    if not session:
        return {
            "hasActiveSession": False,
            "tableId": table.id,
            "tableNumber": table.number,
            "tableStatus": table.status,
            "items": [],
            "subtotal": 0.0,
            "total": 0.0,
            "isPaid": False,
        }

    bill = db.query(Bill).filter(Bill.session_id == session.id).first()

    items_map: dict[str, dict] = {}
    for order in session.orders or []:
        for item in order.items or []:
            key = f"{item.item_name}-{float(item.unit_price):.2f}"
            unit_price = float(item.unit_price)
            if key not in items_map:
                items_map[key] = {
                    "name": item.item_name,
                    "unitPrice": unit_price,
                    "quantity": item.quantity,
                    "lineTotal": round(unit_price * item.quantity, 2),
                }
            else:
                items_map[key]["quantity"] += item.quantity
                items_map[key]["lineTotal"] = round(
                    unit_price * items_map[key]["quantity"], 2
                )

    item_list = list(items_map.values())
    subtotal = round(sum(i["lineTotal"] for i in item_list), 2)
    total = float(bill.total) if bill and bill.total is not None else subtotal
    is_paid = bill.status == "PAID" if bill else False

    return {
        "hasActiveSession": True,
        "tableId": table.id,
        "tableNumber": str(table.number),
        "guestName": session.guest_name,
        "items": item_list,
        "subtotal": subtotal,
        "total": total,
        "isPaid": is_paid,
        "tableStatus": table.status,
        "billNumber": getattr(bill, "bill_number", f"T{table.number}") if bill else f"T{table.number}",
    }


guest_bill_status = get_guest_bill


@router.post("/pay")
def process_guest_payment(
    payload: GuestPayRequest,
    db: Session = Depends(get_db),
):
    """Guest 1-click Pay & Walk checkout via QR code / NFC."""
    from app.core.ids import new_id
    from app.models import Payment
    from app.services.table_service import change_table_status

    qr = _resolve_qr(db, payload.token)
    table = db.get(Table, qr.table_id)
    if not table:
        raise HTTPException(404, "Table not found")

    session = active_session_for_table(db, table.id)
    if not session:
        session = (
            db.query(DiningSession)
            .filter(DiningSession.table_id == table.id)
            .order_by(DiningSession.seated_at.desc())
            .first()
        )
    if not session:
        raise HTTPException(400, "No active dining session found for this table")

    now = datetime.now(timezone.utc)
    bill = db.query(Bill).filter(Bill.session_id == session.id).first()
    if not bill:
        items = []
        for o in session.orders or []:
            items.extend(o.items or [])
        subtotal = round(sum(float(i.unit_price) * i.quantity for i in items), 2)
        bill = Bill(
            id=new_id(),
            tenant_id=getattr(table, "tenant_id", "org-demo"),
            branch_id=getattr(table, "branch_id", None),
            session_id=session.id,
            subtotal=subtotal,
            total=subtotal,
            generated_at=now,
            status="OPEN",
        )
        db.add(bill)
        db.flush()

    if bill.status == "PAID":
        return {
            "success": True,
            "alreadyPaid": True,
            "tableNumber": table.number,
            "message": "Bill has already been paid in full.",
        }

    bill.status = "PAID"
    bill.paid_at = now
    session.status = "PAID"
    session.payment_method = payload.payment_method
    session.closed_at = now
    table.walkout_alert_sent = False
    table.departure_alert_sent = False

    payment = Payment(
        id=new_id(),
        tenant_id=getattr(table, "tenant_id", "org-demo"),
        branch_id=getattr(table, "branch_id", None),
        bill_id=bill.id,
        amount=payload.amount_paid or float(bill.total),
        method=payload.payment_method,
        payment_status="SUCCESS",
        paid_at=now,
        completed_at=now,
    )
    db.add(payment)

    change_table_status(db, table.id, "CLEANING")
    session.status = "PAID"
    db.commit()

    total_charged = round((payload.amount_paid or float(bill.total)) + (payload.tip or 0.0), 2)

    return {
        "success": True,
        "alreadyPaid": False,
        "tableNumber": table.number,
        "amountPaid": payload.amount_paid or float(bill.total),
        "tip": payload.tip or 0.0,
        "totalCharged": total_charged,
        "paymentMethod": payload.payment_method,
        "message": "Payment successful. Thank you for dining with us!",
    }


def _billing_session(db: Session, table_id: str) -> DiningSession:
    session = (
        db.query(DiningSession)
        .filter(DiningSession.table_id == table_id, DiningSession.status.in_(["BILLING"]))
        .order_by(DiningSession.seated_at.desc())
        .first()
    )
    if not session:
        raise HTTPException(404, "No bill awaiting payment for this table")
    return session


@router.get("/upi-qr")
def guest_upi_qr(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    session = _billing_session(db, qr.table_id)
    bill = get_bill(db, session.id)
    upi_link = (
        f"upi://pay?pa={quote(settings.restaurant_upi_id)}"
        f"&pn={quote(settings.restaurant_upi_name)}"
        f"&am={bill.total:.2f}&cu=INR&tn={quote('Table bill payment')}"
    )
    return {"upiLink": upi_link, "amount": bill.total}


@router.post("/pay-upi")
def guest_pay_upi(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    session = _billing_session(db, qr.table_id)
    bill = mark_paid(db, session.id, user_id=None, method="UPI")
    return bill.model_dump(by_alias=True)


@router.post("/pay-card")
def guest_pay_card(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    session = _billing_session(db, qr.table_id)
    bill = mark_paid(db, session.id, user_id=None, method="CARD")
    return bill.model_dump(by_alias=True)


@router.post("/request-cash-payment")
def guest_request_cash_payment(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    table = db.get(Table, qr.table_id)
    session = _billing_session(db, qr.table_id)
    bill = get_bill(db, session.id)
    guest_name = session.guest_name if session.guest_name else "A guest"
    ai_service.create_alert(
        db,
        AIEventCreate(
            event_type="CASH_PAYMENT_REQUEST",
            message=f"{guest_name} at Table {table.number} wants to pay Γé╣{bill.total:.2f} in cash",
            table_id=table.id,
        ),
    )
    return {"ok": True}


@router.post("/request-bill")
def guest_request_bill(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    session = active_session_for_table(db, qr.table_id)
    if not session:
        raise HTTPException(404, "No active session for table")
    bill = request_bill(db, session.id, user_id=None)
    return bill.model_dump(by_alias=True)


@router.post("/call-waiter")
def guest_call_waiter(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    qr = _resolve_qr(db, token)
    table = db.get(Table, qr.table_id)
    if not table:
        raise HTTPException(404, "Table not found")
    session = active_session_for_table(db, qr.table_id)
    guest_name = session.guest_name if session and session.guest_name else "A guest"
    ai_service.create_alert(
        db,
        AIEventCreate(
            event_type="WAITER_CALL",
            message=f"{guest_name} at Table {table.number} needs help",
            table_id=table.id,
        ),
    )
    return {"ok": True}



@router.get("/waiter-status")
def guest_waiter_status(
    token: str = Query(...),
    event_type: str = Query("WAITER_CALL"),
    db: Session = Depends(get_db),
):
    from app.models import AIEvent

    qr = _resolve_qr(db, token)
    event = (
        db.query(AIEvent)
        .filter(
            AIEvent.table_id == qr.table_id,
            AIEvent.event_type == event_type,
            AIEvent.resolved.is_(False),
        )
        .order_by(AIEvent.created_at.desc())
        .first()
    )
    if not event:
        return None
    return {"acknowledged": event.acknowledged, "eventType": event.event_type}
