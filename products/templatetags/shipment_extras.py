from django import template

register = template.Library()
 
@register.filter
def quantity_shipped(item, shipment):
    si = item.shipmentitem_set.filter(shipment=shipment).first()
    return si.quantity_shipped if si else 0 