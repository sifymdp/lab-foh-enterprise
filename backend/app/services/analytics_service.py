from sqlalchemy.orm import Session
from app.models.order_analytics import OrderAnalytics
from datetime import datetime
from uuid import uuid4
from statistics import median

def log_completed_order(
    db: Session,
    order_id: str,
    item_name: str,
    item_count: int,
    station: str,
    cooking_time_minutes: float,
    complexity: str = None  # ΓåÉ Change this
) -> None:
    """Save order data for future predictions"""
    
    # Auto-detect complexity if not provided
    if complexity is None:
        complexity = get_item_complexity(item_name)
    
    analytics = OrderAnalytics(
        id=str(uuid4()),
        order_id=order_id,
        item_name=item_name,
        item_count=item_count,
        station=station,
        actual_cooking_time=cooking_time_minutes,
        complexity=complexity,
        created_at=datetime.utcnow()
    )
    db.add(analytics)
    db.commit()


def predict_cooking_time(
    db: Session,
    item_name: str,
    quantity: int,
    station: str,
    current_workload: int = 0
) -> dict:
    """
    Predict how long an order will take with SMART ALGORITHM
    
    Considers:
    - Historical average for this item
    - Item complexity
    - Station workload
    - Quantity multiplier
    - Time of day (rush hour detection)
    
    Returns: {
        "estimated_minutes": 12,
        "confidence": 0.85,
        "based_on_orders": 23,
        "reason": "Based on 23 similar orders"
    }
    """
    from datetime import datetime
    
    # Find all similar past orders
    similar_orders = db.query(OrderAnalytics).filter(
        OrderAnalytics.item_name == item_name,
        OrderAnalytics.station == station
    ).all()
    
    if not similar_orders:
        # No data yet - return smart default estimate
        default_time = get_default_estimate(item_name)
        return {
            "estimated_minutes": default_time,
            "confidence": 0.0,
            "based_on_orders": 0,
            "reason": "No historical data for this item yet"
        }
    
    # ========== ALGORITHM ==========
    
    # Historical values are recorded for the whole line. Normalize by quantity
    # before applying the requested quantity multiplier, and use a median so one
    # unusually late order cannot produce a multi-hour estimate.
    default_time = float(get_default_estimate(item_name))
    normalized_times = [
        float(o.actual_cooking_time) / max(int(o.item_count or 1), 1)
        for o in similar_orders
        if o.actual_cooking_time is not None
    ]
    # Do not let old timeout/queue measurements become cooking-time history.
    normalized_times = [
        value for value in normalized_times
        if 0.5 <= value <= default_time * 3
    ]
    avg_time = median(normalized_times) if normalized_times else default_time
    
    # 2. Calculate complexity factor
    complexity = get_item_complexity(item_name)
    complexity_factor = {
        "simple": 0.8,      # Simple items = 20% faster
        "medium": 1.0,      # Medium = normal
        "complex": 1.3      # Complex = 30% slower
    }.get(complexity, 1.0)
    
    base_time = avg_time * complexity_factor
    
    # 3. Adjust for quantity (diminishing returns)
    # 1x item = 1.0, 2x = 1.5x, 3x = 1.85x
    quantity_multiplier = 1.0 + (quantity - 1) * 0.6
    time_with_quantity = base_time * quantity_multiplier
    
    # 4. Adjust for current workload at station
    # Each item in queue = +20% time
    bounded_workload = min(max(current_workload, 0), 10)
    workload_multiplier = 1.0 + (bounded_workload * 0.08)
    time_with_workload = time_with_quantity * workload_multiplier
    
    # 5. Adjust for time of day (rush hour detection)
    current_hour = datetime.now().hour
    rush_hour_multiplier = get_rush_hour_multiplier(current_hour)
    final_time = time_with_workload * rush_hour_multiplier
    
    # 6. Calculate confidence based on data quality
    confidence = min(0.98, len(similar_orders) / 50)
    
    # 7. Build detailed reason
    reason = f"Based on {len(similar_orders)} similar orders"
    factors = []
    
    if complexity != "medium":
        factors.append(f"complexity ({complexity})")
    if quantity > 1:
        factors.append(f"quantity ({quantity}x)")
    if bounded_workload > 0:
        factors.append(f"workload ({bounded_workload} items)")
    if rush_hour_multiplier > 1.0:
        factors.append("rush hour")
    
    if factors:
        reason += " ΓÇó " + ", ".join(factors)
    
    return {
        "estimated_minutes": round(final_time, 1),
        "confidence": round(confidence, 2),
        "based_on_orders": len(similar_orders),
        "reason": reason,
        "breakdown": {
            "base_time": round(base_time, 1),
            "quantity_factor": round(quantity_multiplier, 2),
            "workload_factor": round(workload_multiplier, 2),
            "rush_factor": round(rush_hour_multiplier, 2)
        }
    }


# ========== HELPER FUNCTIONS ==========

def get_default_estimate(item_name: str) -> int:
    """Return default estimate for unknown items"""
    defaults = {
        "biryani": 12,
        "fried rice": 8,
        "fries": 3,
        "noodles": 10,
        "curry": 15,
        "soup": 5,
    }
    
    item_lower = item_name.lower()
    for key, value in defaults.items():
        if key in item_lower:
            return value
    
    return 10  # Default to 10 minutes


def get_item_complexity(item_name: str) -> str:
    """Determine item complexity"""
    item_lower = item_name.lower()
    
    # Simple items (quick to make)
    if any(x in item_lower for x in ["fries", "water", "juice", "salad"]):
        return "simple"
    
    # Complex items (take time)
    if any(x in item_lower for x in ["biryani", "curry", "special", "bake"]):
        return "complex"
    
    # Everything else is medium
    return "medium"


def get_rush_hour_multiplier(hour: int) -> float:
    """
    Adjust for rush hours
    12-13 (lunch) and 19-20 (dinner) are busier
    """
    rush_hours = [12, 13, 19, 20]  # Lunch (12-1 PM) and Dinner (7-8 PM)
    
    if hour in rush_hours:
        return 1.3  # 30% slower during rush
    elif hour in [11, 14, 18, 21]:
        return 1.15  # 15% slower during pre/post rush
    else:
        return 1.0  # Normal speed
