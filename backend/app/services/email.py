"""
Envoi d'emails transactionnels via l'API Brevo (v3).

- Non configuré (BREVO_API_KEY / BREVO_SENDER_EMAIL absents) : aucun envoi, et aucun
  succès simulé : l'appelant enregistre le statut "non_configure".
- Tout contenu dynamique est échappé (fix S10 : injection HTML dans les emails).
"""
import html
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
BRAND = "#4f46e5"


def render(titre: str, message: Optional[str], lien: Optional[str]) -> str:
    t = html.escape(titre)
    m = html.escape(message or "").replace("\n", "<br>")
    bouton = ""
    if lien and lien.startswith("/"):
        url = html.escape(settings.APP_PUBLIC_URL.rstrip("/") + lien, quote=True)
        bouton = (f'<p style="margin:24px 0"><a href="{url}" style="background:{BRAND};color:#fff;'
                  f'padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">'
                  f'Ouvrir dans la plateforme</a></p>')
    return (
        '<!DOCTYPE html><html><body style="margin:0;background:#f6f7fb;font-family:Arial,sans-serif;color:#1f2937">'
        '<div style="max-width:560px;margin:32px auto;background:#fff;border-radius:12px;padding:28px;'
        'border:1px solid #e5e7eb">'
        f'<div style="font-weight:700;color:{BRAND};margin-bottom:16px">{html.escape(settings.APP_NAME)}</div>'
        f'<h2 style="font-size:18px;margin:0 0 12px">{t}</h2>'
        f'<p style="line-height:1.6;margin:0">{m}</p>{bouton}'
        '<p style="font-size:12px;color:#6b7280;margin-top:24px">Message automatique — ne pas répondre.</p>'
        '</div></body></html>'
    )


def send(to_email: str, to_name: str, subject: str, html_body: str) -> str:
    """Retourne le statut : envoye | echec | non_configure."""
    if not settings.brevo_configured:
        return "non_configure"
    try:
        resp = httpx.post(
            BREVO_URL,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json",
                     "content-type": "application/json"},
            json={
                "sender": {"email": settings.BREVO_SENDER_EMAIL, "name": settings.BREVO_SENDER_NAME},
                "to": [{"email": to_email, "name": to_name[:100]}],
                "subject": subject[:200],
                "htmlContent": html_body,
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        logger.warning("[EMAIL] Brevo injoignable (%s)", type(exc).__name__)
        return "echec"
    if resp.status_code in (200, 201, 202):
        return "envoye"
    logger.warning("[EMAIL] Brevo a refusé l'envoi (HTTP %s)", resp.status_code)  # fix: ni destinataire ni clé en log
    return "echec"
