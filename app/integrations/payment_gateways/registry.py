from fastapi import HTTPException, status

from app.integrations.payment_gateways.base import PaymentGateway
from app.models.payment import PaymentMethod

_REGISTRY: dict[PaymentMethod, PaymentGateway] = {}


def register_gateway(method: PaymentMethod, gateway: PaymentGateway) -> None:
    _REGISTRY[method] = gateway


def get_gateway(method: PaymentMethod) -> PaymentGateway:
    gateway = _REGISTRY.get(method)
    if gateway is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment method {method} is not supported",
        )
    return gateway
