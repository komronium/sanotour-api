from app.integrations.payment_gateways.base import (
    PaymentGateway,
    WebhookResult,
)
from app.integrations.payment_gateways.cash import CashGateway
from app.integrations.payment_gateways.click import ClickGateway
from app.integrations.payment_gateways.payme import PaymeGateway
from app.integrations.payment_gateways.registry import (
    get_gateway,
    register_gateway,
)
from app.models.payment import PaymentMethod

register_gateway(PaymentMethod.PAYME, PaymeGateway())
register_gateway(PaymentMethod.CLICK, ClickGateway())
register_gateway(PaymentMethod.CASH, CashGateway())

__all__ = [
    "PaymentGateway",
    "WebhookResult",
    "get_gateway",
    "register_gateway",
]
