# 0001: Extract Lifecycle to Pure Module

## Status
Accepted

## Context
The rules governing a parcel's lifecycle (dispatch, deliver, fail, return) are complex and expected to change frequently as the business learns more. We need a way to implement and test these rules reliably without tangling them with the HTTP layer (FastAPI) or database logic.

## Decision
We decided to extract all lifecycle rules into a pure Python module (`app/domain.py`). This module uses an immutable `dataclass` for the `Parcel` and a single `apply_event` function that returns a new instance of the parcel upon a valid transition, raising an `InvalidTransition` exception otherwise. It imports no web frameworks or ORMs.

## Consequences
- **Positive:** Business rules are isolated and can be unit-tested instantly without mocking HTTP requests or databases. The HTTP layer becomes very thin, acting only as an interface.
- **Negative:** We have to explicitly handle mapping between HTTP exceptions and domain exceptions (e.g., mapping `InvalidTransition` to a 409 Conflict).