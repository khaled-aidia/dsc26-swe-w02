## Tools
I used Gemini (AI assistant) to help me structure the project, understand the requirements step-by-step, set up the virtual environment, and write the boilerplate code for the FastAPI endpoints and error handlers.

## What AI got wrong
Initially, when organizing the API endpoints in `app/api.py`, there was a slight mix-up with the decorators' order, which caused the `POST /v1/parcels` endpoint to expect a `parcel_id` path parameter intended for the `GET` endpoint. We fixed this by correctly reordering the route functions and ensuring each decorator was directly above its corresponding function.

## In my own words
Offset pagination skips a fixed number of items. If parcels are changing states while a user is paginating, the list's order shifts, causing offset pagination to miss items or show duplicates. A cursor acts like a bookmark (pointing to a specific item ID), ensuring we always resume from the exact right place regardless of state changes.

Renaming a field would break the `POST /v1/parcels` (createParcel) or `GET /v1/parcels` (listParcels) operations, as the courier app expects a strict JSON contract. Such a breaking change to the API contract would have to be approved by Dina El-Sherbiny (Head of Fraud & Risk) and likely the merchant integration team before deployment.

