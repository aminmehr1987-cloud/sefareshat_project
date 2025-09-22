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
    Returns a list of unique sub-orders associated with a shipment
    by looking at the ShipmentItem records.
    """
    if not shipment:
        return []
    
    # Get the IDs of the orders linked through the shipment's items
    order_ids = shipment.items.values_list('order_id', flat=True).distinct()
    
    # Fetch the actual Order objects
    return Order.objects.filter(id__in=order_ids)