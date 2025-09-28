from django import template
from products.models import Order

register = template.Library()
 
@register.filter
def quantity_shipped(item, shipment):
    si = item.shipmentitem_set.filter(shipment=shipment).first()
    return si.quantity_shipped if si else 0 

@register.simple_tag
def get_sub_orders_for_shipment(shipment):
    """
    Returns a list of unique sub-orders associated with a shipment.
    First tries to get from sub_orders field, then falls back to items.
    """
    if not shipment:
        return []
    
    # First try to get sub_orders directly from the ManyToMany field
    sub_orders = shipment.sub_orders.all()
    if sub_orders.exists():
        return sub_orders
    
    # Fallback: Get orders through ShipmentItem records
    from products.models import ShipmentItem
    shipment_items = ShipmentItem.objects.filter(shipment=shipment).select_related('order_item__order')
    order_ids = set()
    for item in shipment_items:
        if item.order_item and item.order_item.order:
            order_ids.add(item.order_item.order.id)
    
    if order_ids:
        return Order.objects.filter(id__in=order_ids)
    
    # Final fallback: return single order if available
    if shipment.order:
        return [shipment.order]
    
    return []
