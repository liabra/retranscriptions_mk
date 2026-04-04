"""
Service d'envoi d'emails — smtplib natif, aucune dépendance externe.
Si SMTP_HOST est absent, les emails sont loggés sans être envoyés (mode dégradé silencieux).
"""
import logging
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)

APP_NAME = "A2C Retranscriptions"
BRAND_COLOR = "#2563eb"


def _send(to: str, subject: str, body_html: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info(f"[EMAIL SKIPPED — no SMTP config] To={to} | Subject={subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{APP_NAME} <{settings.EMAIL_FROM or settings.SMTP_USER}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
            srv.sendmail(msg["From"], to, msg.as_string())
        logger.info(f"[EMAIL SENT] To={to} | Subject={subject}")
    except Exception as exc:
        logger.warning(f"[EMAIL FAILED] To={to} | {exc}")


def _async(to: str, subject: str, body_html: str) -> None:
    """Envoie en arrière-plan (non bloquant)."""
    threading.Thread(target=_send, args=(to, subject, body_html), daemon=True).start()


def _wrap(content: str) -> str:
    return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#111;margin:0;padding:0">
<div style="max-width:600px;margin:32px auto;padding:24px;border:1px solid #e5e7eb;border-radius:8px">
  <div style="border-bottom:3px solid {BRAND_COLOR};padding-bottom:12px;margin-bottom:20px">
    <strong style="color:{BRAND_COLOR};font-size:16px">{APP_NAME}</strong>
  </div>
  {content}
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:11px;color:#999">
    Message automatique — ne pas répondre directement à cet email.
  </div>
</div></body></html>"""


# ── Templates ──────────────────────────────────────────────────────────────

def send_affectation_prestataire(to: str, presta_nom: str, dossier_ref: str,
                                  role: str, date_limite: str) -> None:
    role_label = "retranscription" if role == "retranscripteur" else "correction"
    body = _wrap(f"""
      <h2 style="margin:0 0 16px">Nouvelle mission — {dossier_ref}</h2>
      <p>Bonjour {presta_nom},</p>
      <p>Une nouvelle mission de <strong>{role_label}</strong> vous a été attribuée.</p>
      <table style="width:100%;font-size:14px;margin:16px 0">
        <tr><td style="color:#666;padding:4px 0">Dossier</td><td><strong>{dossier_ref}</strong></td></tr>
        <tr><td style="color:#666;padding:4px 0">Mission</td><td>{role_label.capitalize()}</td></tr>
        <tr><td style="color:#666;padding:4px 0">Date limite</td><td><strong>{date_limite}</strong></td></tr>
      </table>
      <p>Connectez-vous à l'application pour consulter le dossier et marquer votre travail comme terminé une fois livré.</p>
    """)
    _async(to, f"[{APP_NAME}] Nouvelle mission — {dossier_ref}", body)


def send_retranscription_livree(to: str, correcteur_nom: str, dossier_ref: str) -> None:
    body = _wrap(f"""
      <h2 style="margin:0 0 16px">Retranscription livrée — {dossier_ref}</h2>
      <p>Bonjour {correcteur_nom},</p>
      <p>La retranscription du dossier <strong>{dossier_ref}</strong> a été livrée.
         Ce dossier est maintenant disponible pour la correction.</p>
      <p>Connectez-vous à l'application pour accéder au dossier.</p>
    """)
    _async(to, f"[{APP_NAME}] Retranscription prête — {dossier_ref}", body)


def send_correction_livree(to: str, dossier_ref: str) -> None:
    body = _wrap(f"""
      <h2 style="margin:0 0 16px">Correction livrée — {dossier_ref}</h2>
      <p>La correction du dossier <strong>{dossier_ref}</strong> a été livrée par le correcteur.</p>
      <p>Le dossier est prêt pour relecture et envoi au client. Connectez-vous pour valider et générer la facture.</p>
    """)
    _async(to, f"[{APP_NAME}] Dossier prêt à envoyer — {dossier_ref}", body)


def send_facture_client(to: str, client_nom: str, dossier_ref: str,
                         numero_facture: str, montant_ttc: str, date_echeance: str) -> None:
    body = _wrap(f"""
      <h2 style="margin:0 0 16px">Facture {numero_facture}</h2>
      <p>Bonjour {client_nom},</p>
      <p>Votre facture pour le dossier <strong>{dossier_ref}</strong> est disponible.</p>
      <table style="width:100%;font-size:14px;margin:16px 0">
        <tr><td style="color:#666;padding:4px 0">Numéro</td><td><strong>{numero_facture}</strong></td></tr>
        <tr><td style="color:#666;padding:4px 0">Montant TTC</td><td><strong>{montant_ttc} €</strong></td></tr>
        <tr><td style="color:#666;padding:4px 0">Échéance</td><td>{date_echeance}</td></tr>
      </table>
    """)
    _async(to, f"[{APP_NAME}] Facture {numero_facture} — {dossier_ref}", body)
