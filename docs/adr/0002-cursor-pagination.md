# 0002: Use Cursor Pagination for Listing Parcels

## Status
Accepted

## Context
The API needs to return lists of parcels (potentially filtered by state). Using traditional offset pagination (e.g., `LIMIT 20 OFFSET 40`) is problematic. Parcels frequently change states (e.g., from `created` to `out_for_delivery`). If a client is paginating through `created` parcels, and a parcel changes state before the client requests the next page, offset pagination will cause the client to either skip items or see duplicates.

## Decision
We decided to implement cursor-based pagination. The API issues an opaque string (`next_cursor`) which the client must pass to get the next page. Internally, the cursor encodes the ID of the last seen parcel, allowing the server to resume exactly after that parcel, regardless of how many other parcels have changed state or been added in the meantime.

## Consequences
- **Positive:** Clients receive a stable view of the data without duplicates or skipped items, even in a highly concurrent environment where states change rapidly.
- **Negative:** Clients cannot jump directly to a specific page (e.g., "Page 5"); they must navigate sequentially. It also adds complexity to the backend implementation compared to simple offset queries.