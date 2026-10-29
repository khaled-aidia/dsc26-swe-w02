"""Parcel lifecycle rules for Tawseel.

Pure Python: do not import fastapi, starlette, pydantic or sqlalchemy here
(a hidden test checks). Keep the names below exactly as they are.
"""
from dataclasses import replace
from dataclasses import dataclass
from enum import StrEnum

MAX_ATTEMPTS = 3


class ParcelState(StrEnum):
    CREATED = "created"
    OUT_FOR_DELIVERY = "out_for_delivery"
    FAILED_ATTEMPT = "failed_attempt"
    DELIVERED = "delivered"
    RETURNED = "returned"


class EventType(StrEnum):
    DISPATCH = "dispatch"
    DELIVER = "deliver"
    FAIL = "fail"
    RETURN = "return"


class InvalidTransition(Exception): ...


@dataclass(frozen=True)
class Parcel:
    id: str
    merchant_ref: str
    cod_amount_piastres: int
    address_text: str
    state: ParcelState = ParcelState.CREATED
    attempts: int = 0


def apply_event(parcel: Parcel, event: EventType) -> Parcel:
    """Return a new Parcel. Raise InvalidTransition if the event is not allowed."""

    if parcel.state == ParcelState.CREATED and event == EventType.DISPATCH:
        return replace(parcel, state=ParcelState.OUT_FOR_DELIVERY, attempts=parcel.attempts + 1)
    
    elif parcel.state == ParcelState.OUT_FOR_DELIVERY and event == EventType.DELIVER:
        return replace(parcel, state=ParcelState.DELIVERED)
    
    elif parcel.state == ParcelState.OUT_FOR_DELIVERY and event == EventType.FAIL:
        return replace(parcel, state=ParcelState.FAILED_ATTEMPT)
    
    elif parcel.state == ParcelState.FAILED_ATTEMPT and event == EventType.DISPATCH:
        if parcel.attempts < MAX_ATTEMPTS:
            return replace(parcel, state=ParcelState.OUT_FOR_DELIVERY, attempts=parcel.attempts + 1)
        else:
            raise InvalidTransition() 
            
    elif parcel.state == ParcelState.FAILED_ATTEMPT and event == EventType.RETURN:
        return replace(parcel, state=ParcelState.RETURNED)
    
    else:
        raise InvalidTransition()
    
    
