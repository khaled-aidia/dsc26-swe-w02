from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import base64

from app.domain import Parcel, ParcelState, EventType, InvalidTransition, apply_event

class CreateParcelRequest(BaseModel):
    merchant_ref: str = Field(min_length=1, max_length=64)
    cod_amount_piastres: int = Field(ge=0, le=5000000)
    address_text: str = Field(min_length=1, max_length=500)

class EventRequest(BaseModel):
    type: str

def problem_exception_handler(request: Request, exc: Exception, status_code: int, type_uri: str, title: str, extra_kwargs: dict = None):
    content = {
        "type": type_uri,
        "title": title,
        "status": status_code,
    }
    if extra_kwargs:
        content.update(extra_kwargs)
    return JSONResponse(status_code=status_code, content=content, media_type="application/problem+json")

def create_app() -> FastAPI:
    """Return a NEW FastAPI app with its own empty in-memory store."""
    
    app = FastAPI(title="Tawseel API")
    
    app.state.parcels = {}

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # تجميع الأخطاء لمنع التكرار (خطأ واحد فقط لكل حقل كما طلب المصحح)
        errors_dict = {}
        for error in exc.errors():
            loc_key = tuple(error["loc"])
            if loc_key not in errors_dict:
                errors_dict[loc_key] = {
                    "loc": list(error["loc"]),
                    "msg": error["msg"]
                }
                
        errors_list = list(errors_dict.values())
            
        return problem_exception_handler(
            request, exc, 
            status_code=422, 
            type_uri="about:blank", 
            title="Unprocessable Entity",
            extra_kwargs={"errors": errors_list}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return problem_exception_handler(
            request, exc,
            status_code=exc.status_code,
            type_uri="about:blank",
            title=exc.detail
        )

    @app.post(
        "/v1/parcels", 
        status_code=201, 
        response_model=Parcel,
        operation_id="createParcel",
        responses={
            409: {"description": "Duplicate merchant_ref"},
            422: {"description": "Invalid body"}
        }
    )
    async def create_parcel(payload: CreateParcelRequest, request: Request, response: Response):
        for existing_parcel in app.state.parcels.values():
            if existing_parcel.merchant_ref == payload.merchant_ref:
                return problem_exception_handler(
                    request, None,
                    status_code=409,
                    type_uri="about:blank",
                    title="Conflict"
                )
        
        new_id = f"pcl_{uuid.uuid4().hex}"
        
        new_parcel = Parcel(
            id=new_id,
            merchant_ref=payload.merchant_ref,
            cod_amount_piastres=payload.cod_amount_piastres,
            address_text=payload.address_text
        )
        
        app.state.parcels[new_id] = new_parcel
        response.headers["Location"] = f"/v1/parcels/{new_id}"
        
        return new_parcel

    @app.get(
        "/v1/parcels/{parcel_id}",
        status_code=200,
        response_model=Parcel,
        operation_id="getParcel",
        responses={
            404: {"description": "Not Found"}
        }
    )
    async def get_parcel(parcel_id: str):
        if parcel_id not in app.state.parcels:
            raise HTTPException(status_code=404, detail="Parcel not found")
        
        return app.state.parcels[parcel_id]

    @app.post(
        "/v1/parcels/{parcel_id}/events",
        status_code=200,
        response_model=Parcel,
        operation_id="recordParcelEvent",
        responses={
            404: {"description": "Not Found"},
            409: {"description": "Invalid transition"},
            422: {"description": "Unknown or missing event type"}
        }
    )
    async def record_parcel_event(parcel_id: str, payload: EventRequest, request: Request):
        if parcel_id not in app.state.parcels:
            raise HTTPException(status_code=404, detail="Parcel not found")
            
        parcel = app.state.parcels[parcel_id]
        
        try:
            event_enum = EventType(payload.type)
        except ValueError:
            return problem_exception_handler(
                request, None,
                status_code=422,
                type_uri="about:blank",
                title="Unprocessable Entity",
                extra_kwargs={"errors": [{"loc": ["body", "type"], "msg": "unknown event type"}]}
            )
            
        try:
            updated_parcel = apply_event(parcel, event_enum)
        except InvalidTransition:
            return problem_exception_handler(
                request, None,
                status_code=409,
                type_uri="about:blank",
                title="Conflict",
                extra_kwargs={"detail": "Invalid transition (parcel unchanged)"}
            )
            
        app.state.parcels[parcel_id] = updated_parcel
        return updated_parcel

    @app.get(
        "/v1/parcels",
        status_code=200,
        operation_id="listParcels",
        responses={
            400: {"description": "Bad cursor"},
            422: {"description": "Bad state or limit"}
        }
    )
    async def list_parcels(request: Request, state: Optional[str] = None, limit: int = 20, cursor: Optional[str] = None):
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            return problem_exception_handler(
                request, None, status_code=422, type_uri="about:blank", title="Unprocessable Entity",
                extra_kwargs={"errors": [{"loc": ["query", "limit"], "msg": "limit must be an integer between 1 and 100"}]}
            )
        
        state_enum = None
        if state is not None:
            try:
                state_enum = ParcelState(state)
            except ValueError:
                return problem_exception_handler(
                    request, None, status_code=422, type_uri="about:blank", title="Unprocessable Entity",
                    extra_kwargs={"errors": [{"loc": ["query", "state"], "msg": "unknown state"}]}
                )

        all_parcels = list(app.state.parcels.values())
        start_index = 0
        
        if cursor is not None:
            try:
                decoded_id = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
                found = False
                for i, p in enumerate(all_parcels):
                    if p.id == decoded_id:
                        start_index = i + 1
                        found = True
                        break
                if not found:
                    raise ValueError("Cursor item not found")
            except Exception:
                return problem_exception_handler(
                    request, None, status_code=400, type_uri="about:blank", title="Bad Request",
                    extra_kwargs={"detail": "bad cursor"}
                )

        items = []
        next_cursor = None
        
        for i in range(start_index, len(all_parcels)):
            p = all_parcels[i]
            if state_enum is None or p.state == state_enum:
                items.append(p)
                if len(items) == limit:
                    has_more = False
                    for j in range(i + 1, len(all_parcels)):
                        if state_enum is None or all_parcels[j].state == state_enum:
                            has_more = True
                            break
                    
                    if has_more:
                        next_cursor = base64.b64encode(p.id.encode("utf-8")).decode("utf-8")
                    break
                    
        return {"items": items, "next_cursor": next_cursor}

    return app

app = create_app()