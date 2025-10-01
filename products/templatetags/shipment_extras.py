from django import template
from django.db.models import Q
from products.models import Order

register = template.Library()
 
@register.filter
def quantity_shipped(item, shipment):
    si = item.shipmentitem_set.filter(shipment=shipment).first()
    return si.quantity_shipped if si else 0 

@register.filter
def shipment_number_for_order(order):
    """
    Returns the latest shipment number associated with the given order (sub-order or main).
    Looks up shipments where this order is either the main `order` or included in `sub_orders`.
    """
    if not order:
        return '-'
    from products.models import Shipment
    shipment = Shipment.objects.filter(Q(order=order) | Q(sub_orders=order)).order_by('-shipment_date').first()
    return shipment.shipment_number if shipment else '-'

@register.simple_tag
def get_sub_orders_for_shipment(shipment):
    """
    Returns a list of unique sub-orders associated with a shipment.
    First tries to get from sub_orders field, then falls back to items.
    Excludes backorder sub-orders (status='backorder') from shipment details.
    """
    if not shipment:
        return []
    
    # First try to get sub_orders directly from the ManyToMany field
    sub_orders = shipment.sub_orders.all()
    if sub_orders.exists():
        # Filter out backorder sub-orders
        return sub_orders.exclude(status='backorder')
    
    # Fallback: Get orders through ShipmentItem records
    from products.models import ShipmentItem
    shipment_items = ShipmentItem.objects.filter(shipment=shipment).select_related('order_item__order')
    order_ids = set()
    for item in shipment_items:
        if item.order_item and item.order_item.order:
            order_ids.add(item.order_item.order.id)
    
    if order_ids:
        # Filter out backorder sub-orders
        return Order.objects.filter(id__in=order_ids).exclude(status='backorder')
    
    # Final fallback: if shipment is attached to a parent order, return its sub-orders
    if shipment.order:
        try:
            # If the attached order has sub orders, prefer those over the parent itself
            related_sub_orders = shipment.order.sub_orders.all()
            if related_sub_orders.exists():
                # Filter out backorder sub-orders
                return related_sub_orders.exclude(status='backorder')
        except Exception:
            pass
        # As a last resort, return the single attached order (only if not backorder)
        if shipment.order.status != 'backorder':
            return [shipment.order]
    
    return []
