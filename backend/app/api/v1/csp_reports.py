"""Réception des rapports de violation CSP (#1168).

Cible des directives `report-to` et `report-uri` posées par `frontend/proxy.ts`.
Le corps est lu par morceaux et refusé dès qu'il dépasse la borne : un client
ne peut pas faire charger en mémoire plus que `MAX_REPORT_BYTES`.
"""
from fastapi import APIRouter, Depends, Request

from app.api.deps import csp_report_rate_limit
from app.core.exceptions import CspReportTooLargeError
from app.services import csp_report

router = APIRouter(tags=["csp-reports"])


@router.post("/csp-reports", status_code=204, dependencies=[Depends(csp_report_rate_limit)])
async def receive_reports(request: Request) -> None:
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > csp_report.MAX_REPORT_BYTES:
            raise CspReportTooLargeError()
    csp_report.log_reports(bytes(body))
