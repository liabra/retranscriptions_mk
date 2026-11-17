import { Download, FileText, MessageSquareWarning, Receipt, RotateCcw, Upload, UserCheck, Wallet, AudioLines, BadgeCheck, CheckCircle2 } from 'lucide-react'
import { Pill } from '@/components/ui'
import { Action, Ecran, type Etape, type Parcours } from './moteur'

/* Parcours simulé : toutes les données sont inventées et rien n'est enregistré. */

const ETAPES: Etape[] = [
  {
    cle: 'audio', titre: "Réception de l'audio", acteur: 'Responsable',
    resume: "Le client vous envoie l'enregistrement de sa réunion. Vous le déposez dans « Audios reçus », par lien OneDrive ou en fichier.",
    tips: ["Le lien OneDrive est chiffré : personne d'autre que la plateforme ne peut l'utiliser.", "Si OneDrive est relié, les nouveaux audios apparaissent d'eux-mêmes dans cette liste."],
    ecran: (next, etat, maj) => (
      <Ecran url="/audios">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <strong>Audios reçus</strong>
          <button className="btn btn-secondary btn-sm" onClick={() => maj({ lienOk: true })}>Ajouter un lien OneDrive</button>
        </div>
        {etat.lienOk ? (
          <div className="card list-item demo-flash">
            <span className="kpi-icon tone-primary"><AudioLines size={18} /></span>
            <div className="list-main"><div className="list-title">Plénière_novembre.mp3</div>
              <div className="small muted">Lien OneDrive · CSE EDF Guyane · 1 h 15</div></div>
            <Pill tone="green" dot>Vérifié</Pill>
            <Action onClick={next} icon={<CheckCircle2 size={16} />}>Créer la mission</Action>
          </div>
        ) : <div className="empty small">Aucun audio à traiter. Cliquez sur « Ajouter un lien OneDrive » pour simuler la réception.</div>}
      </Ecran>
    ),
  },
  {
    cle: 'qualification', titre: 'Création et qualification du dossier', acteur: 'Responsable',
    resume: "La plateforme pré-remplit le dossier depuis l'audio. Vous choisissez l'instance et les options de tarification ; l'échéance est calculée toute seule.",
    tips: ["L'échéance client = date de réception de l'audio + délai paramétré (ici 18 jours pour 1 h 15).", "Cochez « Urgence » seulement si une majoration d'urgence est activée dans les paramètres."],
    ecran: (next) => (
      <Ecran url="/dossiers/nouveau">
        <div className="form-grid">
          <div className="field"><span className="label">Client</span><div className="input">CSE EDF Guyane</div></div>
          <div className="field"><span className="label">Type d'instance</span><div className="input">CE</div></div>
          <div className="field"><span className="label">Titre</span><div className="input">Plénière de novembre</div></div>
          <div className="field"><span className="label">Échéance client</span>
            <div className="input" style={{ background: 'var(--primary-soft)' }}>Calculée automatiquement · 18 jours après réception</div></div>
        </div>
        <label className="checkbox"><input type="checkbox" checked readOnly />Qualifier maintenant : le dossier passe « à attribuer »</label>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next}>Créer et passer à l'attribution</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'attribution', titre: 'Attribution à un retranscripteur', acteur: 'Responsable',
    resume: 'La plateforme classe les retranscripteurs selon leurs spécialités, leur charge et leur historique. Vous seule décidez.',
    tips: ["Sans historique suffisant, la mention « Historique insuffisant » s'affiche : aucun score n'est inventé.", "Le retranscripteur reçoit une notification et accède à l'audio uniquement par la plateforme."],
    ecran: (next) => (
      <Ecran url="/dossiers/2026-CE-0001 · Attribution">
        {[['Léa Durand', 78, 'Expérience des instances CE · 1 mission en cours', true], ['Karim Benali', 64, 'Aucune mission en cours · historique insuffisant', false]].map(([n, s, t, premier]) => (
          <div key={String(n)} className="card list-item">
            <div className="kpi-icon tone-primary mono" style={{ width: 44, height: 44, fontWeight: 650 }}>{s as number}</div>
            <div className="list-main"><div className="list-title">{n as string}</div><div className="small muted">{t as string}</div></div>
            {premier ? <Action onClick={next} icon={<UserCheck size={16} />}>Choisir</Action> : <button className="btn btn-secondary btn-sm" disabled>Choisir</button>}
          </div>
        ))}
        <p className="hint">Classement indicatif, jamais visible des retranscripteurs.</p>
      </Ecran>
    ),
  },
  {
    cle: 'depot', titre: 'Retranscription et dépôt du PV', acteur: 'Retranscripteur·rice',
    resume: "Léa voit sa mission sous forme de carte : elle télécharge l'audio, rédige le PV, puis le dépose en .docx.",
    tips: ["Le retranscripteur ne voit ni tarifs, ni notes internes, ni lien OneDrive.", "Le dépôt est refusé si le fichier n'est pas un vrai document Word."],
    ecran: (next) => (
      <Ecran url="/mes-missions">
        <div className="card mission" style={{ padding: 18 }}>
          <div className="mission-top"><div><div className="mission-ref">2026-CE-0001 · CE</div><div className="mission-title">Plénière de novembre</div></div>
            <Pill tone="blue" dot>En cours</Pill></div>
          <div className="mission-facts"><span className="deadline tone-green">À rendre dans 18 jours</span><span>1 h 15 d'audio</span></div>
          <div className="grid-2">
            <button className="btn btn-secondary" style={{ height: 48 }}><Download size={17} />Télécharger l'audio</button>
            <Action onClick={next} icon={<Upload size={17} />}>Envoyer mon PV (PV_novembre.docx)</Action>
          </div>
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'controle', titre: 'Contrôle automatique de conformité', acteur: 'Plateforme',
    resume: "À chaque dépôt, la plateforme vérifie le vrai format Word, la police Comic Sans MS et la taille 12. Le document n'est jamais modifié.",
    tips: ["Un document non conforme est conservé et signalé : la responsable décide.", "Le retranscripteur voit le rapport immédiatement et peut redéposer une version corrigée."],
    ecran: (next, etat, maj) => (
      <Ecran url="/mes-missions · Version 1">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <strong className="row"><FileText size={17} />Version 1</strong>
          <Pill tone={etat.corrige ? 'green' : 'red'} dot>{etat.corrige ? 'Conforme' : 'Non conforme'}</Pill>
        </div>
        <div className="small" style={{ color: etat.corrige ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
          {etat.corrige ? 'Document conforme (Comic Sans MS, 12 pt)' : '23 % du texte ne respecte pas « Comic Sans MS 12 pt » (3 paragraphes signalés)'}
        </div>
        <div className="meter"><span style={{ width: etat.corrige ? '100%' : '77%', background: etat.corrige ? 'var(--green)' : 'var(--red)' }} /></div>
        {!etat.corrige && <div className="anomaly"><Pill tone="red">§ 14</Pill><div className="small">« Intervention de M. Martin… » · police « Calibri »</div></div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.corrige ? <Action onClick={next}>Voir côté responsable</Action>
            : <Action onClick={() => maj({ corrige: true })} icon={<RotateCcw size={16} />}>Déposer une version corrigée</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'relecture', titre: 'Relecture et corrections', acteur: 'Responsable',
    resume: "La responsable est notifiée, prend en charge la relecture, compare les versions et peut demander une correction ou déposer sa propre version.",
    tips: ["Toutes les versions sont conservées avec leur auteur et leur date.", "« Comparer » montre paragraphe par paragraphe ce qui a changé entre deux versions."],
    ecran: (next) => (
      <Ecran url="/dossiers/2026-CE-0001 · Versions du PV">
        <div className="card card-pad stack" style={{ gap: 8 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong>Version 2 <Pill tone="primary">Dernière</Pill></strong><Pill tone="green" dot>Conforme</Pill></div>
          <div className="small muted">Dépôt retranscripteur · Léa Durand · 36 Ko</div>
          <div className="row"><button className="btn btn-secondary btn-sm">Comparer à v1</button>
            <button className="btn btn-secondary btn-sm"><MessageSquareWarning size={15} />Demander une correction</button></div>
        </div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next}>Terminer la relecture</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'validation', titre: 'Validation du PV', acteur: 'Responsable',
    resume: "Au contrôle final, vous validez la version retenue et indiquez le nombre de pages du PV final : il sert de base au calcul tarifaire.",
    tips: ["Valider une version non conforme demande un motif de dérogation, conservé dans l'historique.", "La validation avertit le retranscripteur et rend la facture « à établir »."],
    ecran: (next) => (
      <Ecran url="/dossiers/2026-CE-0001 · Valider le PV">
        <div className="form-grid">
          <div className="field"><span className="label">Version validée</span><div className="input">Version 2 — conforme</div></div>
          <div className="field"><span className="label">Nombre de pages du PV final</span><div className="input">15</div></div>
        </div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next} icon={<BadgeCheck size={17} />}>Valider définitivement</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'facture', titre: 'Calcul et facturation', acteur: 'Comptabilité',
    resume: "La plateforme calcule le prix à partir du barème en vigueur à la date de réception de l'audio. Vous validez le montant, puis établissez la facture.",
    tips: ["« Comment ce montant est calculé » détaille chaque règle appliquée.", "Une copie des tarifs utilisés est conservée : un changement de barème ne modifie jamais cette facture.", "Une facture ne se supprime pas : elle s'annule, son numéro est conservé."],
    ecran: (next) => (
      <Ecran url="/dossiers/2026-CE-0001 · Facturation">
        <div className="grid-2">
          <div className="card card-pad stack" style={{ gap: 6 }}>
            <strong>Calcul tarifaire</strong>
            <dl className="dl"><dt>15 pages</dt><dd className="mono">Barème 10 à 20 pages</dd><dt>Montant client</dt><dd className="mono" style={{ fontSize: 18 }}>100,00 €</dd>
              <dt>Rémunération</dt><dd className="mono">100,00 €</dd></dl>
            <Pill tone="green">Validé</Pill>
          </div>
          <div className="card card-pad stack" style={{ gap: 6 }}>
            <strong>Facture</strong><div className="small muted">Aucune facture pour l'instant.</div>
            <Action onClick={next} icon={<Receipt size={16} />}>Établir la facture</Action>
          </div>
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'reglement', titre: 'Encaissement et paiement du retranscripteur', acteur: 'Comptabilité',
    resume: "Quand le client règle, vous saisissez l'encaissement (partiel ou total). Le paiement de Léa est suivi à part : à payer, validé, puis payé avec la date du virement.",
    tips: ["Les trois suivis sont indépendants : production, facturation et paiement du retranscripteur.", "Un paiement effectué n'est plus modifiable."],
    ecran: (next, etat) => (
      <Ecran url="/finance">
        <div className="card list-item"><div className="list-main"><div className="list-title">FAC-2026-0001 · CSE EDF Guyane</div>
          <div className="small muted">100,00 € TTC · échéance dans 30 jours</div></div><Pill tone="blue" dot>Facture émise</Pill>
          <Action onClick={next} icon={<Wallet size={16} />}>Règlement reçu</Action></div>
        <div className="card list-item"><div className="list-main"><div className="list-title">Léa Durand</div><div className="small muted">Paiement du retranscripteur</div></div>
          <span className="mono">100,00 €</span><Pill tone="amber" dot>À payer</Pill></div>
        {etat.corrige && <p className="hint">Étape finale du parcours.</p>}
      </Ecran>
    ),
  },
]

export const PARCOURS_PV: Parcours = {
  id: 'pv', titre: "Parcours d'un PV, de l'audio à la facture", duree: '5 min', audience: 'interne', etapes: ETAPES,
  resume: "Un exemple fictif complet : de la réception de l'audio au règlement de la facture.",
  intro: "Un exemple complet en 9 étapes : « Plénière de novembre » du CSE EDF Guyane.",
  fin: { texte: "Vous avez suivi un PV de la réception de l'audio jusqu'au règlement.", lien: { to: '/audios', label: "Aller aux audios reçus" } },
}
