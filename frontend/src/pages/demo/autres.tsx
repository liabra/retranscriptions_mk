import {
  Ban, CalendarClock, CheckCircle2, Copy, FileWarning, KeyRound, Lock, Percent, Receipt, ShieldCheck, Unlock, UserMinus, Wallet,
} from 'lucide-react'
import { Pill } from '@/components/ui'
import { Action, Ecran, type Etape, type Parcours } from './moteur'

/* Parcours simulés — chaque donnée est fictive, rien n'est enregistré. */

const Ligne = ({ a, b, fort }: { a: string; b: string; fort?: boolean }) => (
  <div className="row" style={{ justifyContent: 'space-between', borderBottom: '1px dashed var(--line)', padding: '6px 0' }}>
    <span className="muted">{a}</span><strong className={fort ? 'mono' : undefined}>{b}</strong>
  </div>
)

/* ── 1. Barème annuel et majorations ─────────────────────────────────────── */
const TARIFS: Etape[] = [
  {
    cle: 'bareme', titre: 'Partir du barème en vigueur', acteur: 'Administratrice',
    resume: "Dans « Tarifs & paramètres », le barème actuel est affiché avec son historique. Pour l'année suivante, on ne modifie pas l'ancien : on prépare une nouvelle version.",
    tips: ["L'ancienne version reste consultable à vie dans « Historique »."],
    ecran: (next) => (
      <Ecran url="/tarifs · Tarifs clients">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div><strong>Tarif client A2C</strong> <Pill tone="green" dot>En vigueur</Pill><div className="small muted">v2026.1 · depuis le 1 janv. 2026</div></div>
          <Action onClick={next} icon={<CalendarClock size={16} />}>Barème 2027</Action>
        </div>
        <Ligne a="1 à 9 pages" b="50,00 €" /><Ligne a="10 à 20 pages" b="100,00 €" /><Ligne a="21 à 30 pages" b="150,00 €" />
      </Ecran>
    ),
  },
  {
    cle: 'tranches', titre: 'Saisir les nouvelles tranches', acteur: 'Administratrice',
    resume: "Vous modifiez les tranches de pages et leurs montants. Un aperçu lisible s'affiche au fur et à mesure.",
    tips: ["Une tranche peut être un forfait ou un prix par page.", "Vous pouvez aussi créer des grilles par type d'instance ou par client négocié."],
    ecran: (next, etat, maj) => (
      <Ecran url="/tarifs · Nouveau barème">
        {(['1 à 9 pages', '10 à 20 pages', '21 à 30 pages'] as const).map((l, n) => (
          <div key={l} className="row" style={{ justifyContent: 'space-between' }}>
            <span>{l}</span><div className={`input ${etat.hausse ? 'demo-flash' : ''}`} style={{ maxWidth: 120 }}>{[50, 100, 150][n] * (etat.hausse ? 1.05 : 1)} €</div>
          </div>
        ))}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.hausse ? <Action onClick={next}>Continuer</Action>
            : <Action onClick={() => maj({ hausse: true })} icon={<Percent size={16} />}>Appliquer +5 % aux montants</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'date', titre: "Choisir la date d'entrée en vigueur", acteur: 'Administratrice',
    resume: "Vous pouvez enregistrer un brouillon sans effet, ou appliquer le barème à partir d'une date. Une date passée est refusée : aucune modification rétroactive.",
    tips: ["Choisissez le 1er janvier : la version actuelle est automatiquement clôturée la veille.", "Un brouillon peut être repris, publié ou supprimé plus tard."],
    ecran: (next, etat, maj) => (
      <Ecran url="/tarifs · Mise en application">
        <div className="chips">
          <button className={`chip${!etat.publier ? ' active' : ''}`} onClick={() => maj({ publier: false })}>Enregistrer comme brouillon</button>
          <button className={`chip${etat.publier ? ' active' : ''}`} onClick={() => maj({ publier: true })}>Appliquer à partir du</button>
        </div>
        {etat.publier && <div className="input" style={{ maxWidth: 220 }}>01/01/2027</div>}
        <p className="hint">{etat.publier ? "Les audios reçus à partir du 1er janvier 2027 utiliseront ce barème." : "Aucun effet tant que le brouillon n'est pas publié."}</p>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Action onClick={() => { maj({ publier: true }); next() }}>Enregistrer et appliquer</Action>
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'effet', titre: "Ce qui change… et ce qui ne change pas", acteur: 'Plateforme',
    resume: "Le tarif appliqué à un dossier dépend de la date de réception de son audio. Les dossiers et factures déjà engagés ne bougent jamais.",
    tips: ["Chaque calcul garde une copie complète des tarifs utilisés.", "Une facture validée n'est jamais recalculée, même si le barème change ensuite."],
    ecran: (next) => (
      <Ecran url="/dossiers">
        <div className="card list-item"><div className="list-main"><div className="list-title">2026-CE-0012 · audio reçu le 12/12/2026</div><div className="small muted">15 pages · barème 2026</div></div>
          <span className="mono">100,00 €</span><Pill tone="gray">inchangé</Pill></div>
        <div className="card list-item demo-flash"><div className="list-main"><div className="list-title">2027-CE-0001 · audio reçu le 05/01/2027</div><div className="small muted">15 pages · barème 2027</div></div>
          <span className="mono">105,00 €</span><Pill tone="green">nouveau barème</Pill></div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next}>Compris</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'majoration', titre: "Activer une majoration d'urgence", acteur: 'Administratrice',
    resume: "La majoration d'urgence est désactivée tant que la règle n'est pas confirmée. Vous choisissez le taux, à qui elle s'applique et quand elle se déclenche.",
    tips: ["Client et retranscripteur se règlent indépendamment : vous pouvez majorer l'un sans l'autre.", "Le simulateur permet de vérifier le résultat avant de l'appliquer à un vrai dossier."],
    ecran: (next, etat, maj) => (
      <Ecran url="/tarifs · Majorations">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div className="row"><strong>Majoration urgence</strong><Pill tone={etat.active ? 'green' : 'red'} dot>{etat.active ? 'En vigueur' : 'Désactivée'}</Pill></div>
          <span className="mono" style={{ fontSize: 24, color: etat.active ? undefined : 'var(--faint)' }}>+20 %</span>
        </div>
        <div className="row"><Pill tone="green">✓ Tarif client</Pill><Pill tone="gray">✕ Rémunération retranscripteur</Pill></div>
        <p className="small">Se déclenche : case « Urgence » cochée ou délai inférieur à 5 jours.</p>
        {etat.active && <div className="callout small demo-flash"><strong>Simulation :</strong> 15 pages, urgent → client 100 € + 20 € = <strong>120,00 €</strong> · retranscripteur 100,00 € (inchangé)</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.active ? <Action onClick={next}>Terminer</Action> : <Action onClick={() => maj({ active: true })}>Configurer et activer</Action>}
        </div>
      </Ecran>
    ),
  },
]

export const PARCOURS_TARIFS: Parcours = {
  id: 'tarifs', titre: 'Préparer le barème de l’année et les majorations', duree: '4 min', audience: 'interne', etapes: TARIFS,
  resume: 'Publier un nouveau barème au 1er janvier, sans toucher aux dossiers existants, et paramétrer la majoration d’urgence.',
  intro: 'Les barèmes évoluent chaque année : voici comment publier le suivant en toute sécurité.',
  fin: { texte: 'Vous savez publier un barème daté et régler une majoration sans jamais modifier le passé.', lien: { to: '/tarifs', label: 'Ouvrir les tarifs' } },
}

/* ── 2. Délais et échéances ──────────────────────────────────────────────── */
const DELAIS: Etape[] = [
  {
    cle: 'regles', titre: 'Les règles de délai', acteur: 'Administratrice',
    resume: "Les délais ne sont pas figés dans l'outil : vous les paramétrez. La première règle qui correspond au dossier (dans l'ordre) donne le délai.",
    tips: ["Une règle peut dépendre de l'instance, de la durée de l'audio, de l'urgence ou du type de prestation.", "Jours calendaires ou ouvrés, au choix."],
    ecran: (next) => (
      <Ecran url="/tarifs · Délais de réalisation">
        <Ligne a="10 · Audio jusqu'à 1 h" b="7 jours" /><Ligne a="20 · Audio de plus de 1 h à 4 h" b="18 jours" /><Ligne a="30 · Audio de plus de 4 h" b="25 jours" />
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next}>Voir un dossier reçu</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'calcul', titre: "L'échéance calculée à réception", acteur: 'Plateforme',
    resume: "À la création du dossier, l'échéance prévisionnelle est calculée : date de réception de l'audio + délai de la règle applicable.",
    tips: ["La date de réception de l'audio est la référence unique.", "Vous pouvez aussi saisir l'échéance à la main : elle reste prioritaire."],
    ecran: (next) => (
      <Ecran url="/dossiers/nouveau">
        <Ligne a="Audio reçu le" b="17 nov. 2026" /><Ligne a="Durée" b="1 h 15" /><Ligne a="Règle appliquée" b="Audio de plus de 1 h à 4 h · 18 jours" />
        <div className="callout small demo-flash"><strong>Échéance client : 5 déc. 2026</strong> · prévisionnelle, suit les règles jusqu'à l'attribution</div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next}>Créer le dossier</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'recalcul', titre: 'Les règles changent avant attribution', acteur: 'Administratrice',
    resume: "Tant que le dossier n'est pas attribué, son échéance suit les règles : si vous les modifiez, elle est recalculée, et chaque recalcul est tracé.",
    tips: ["L'historique du dossier garde l'ancienne et la nouvelle date, avec la date et l'auteur du changement."],
    ecran: (next, etat, maj) => (
      <Ecran url="/tarifs · Délais de réalisation">
        <Ligne a="20 · Audio de plus de 1 h à 4 h" b={etat.modifie ? '15 jours' : '18 jours'} />
        {etat.modifie && <div className="callout small demo-flash"><strong>2026-CE-0014 :</strong> échéance recalculée du 5 déc. au <strong>2 déc. 2026</strong> · tracé dans l'historique</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.modifie ? <Action onClick={next}>Attribuer le dossier</Action> : <Action onClick={() => maj({ modifie: true })}>Passer le délai à 15 jours</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'gel', titre: "L'attribution fige l'échéance", acteur: 'Responsable',
    resume: "Au moment de l'attribution, l'échéance client est figée. Le retranscripteur reçoit une date plus tôt : on réserve du temps de relecture.",
    tips: ["Le temps de relecture se règle dans « Autres paramètres de délais » (ici 3 jours).", "L'échéance promise au client ne change pas."],
    ecran: (next) => (
      <Ecran url="/dossiers/2026-CE-0014 · Attribution">
        <Ligne a="Échéance client" b="2 déc. 2026 · figée" /><Ligne a="Temps de relecture réservé" b="3 jours" /><Ligne a="Rendu attendu du retranscripteur" b="29 nov. 2026" />
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next} icon={<Lock size={16} />}>Confirmer l'attribution</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'apres', titre: 'Après le gel : seule une modification manuelle', acteur: 'Responsable',
    resume: "Modifier les règles n'a plus aucun effet sur ce dossier. Une personne autorisée peut encore changer l'échéance à la main : l'ancienne valeur est conservée.",
    tips: ["Même si la mission est retirée puis réattribuée, l'échéance reste figée."],
    ecran: (next, etat, maj) => (
      <Ecran url="/dossiers/2026-CE-0014 · Historique">
        <p className="small muted">Le délai passe ensuite à 25 jours dans les paramètres… le dossier garde le <strong>2 déc. 2026</strong>.</p>
        {etat.manuel && <div className="callout small demo-flash"><strong>Échéance modifiée</strong> · 2 déc. → <strong>9 déc. 2026</strong> · par Sophie · 17 nov. 15:42 · motif « report demandé par le client »</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.manuel ? <Action onClick={next}>Terminer</Action> : <Action onClick={() => maj({ manuel: true })} icon={<CalendarClock size={16} />}>Modifier l'échéance à la main</Action>}
        </div>
      </Ecran>
    ),
  },
]

export const PARCOURS_DELAIS: Parcours = {
  id: 'delais', titre: 'Délais et échéances, de la réception au gel', duree: '4 min', audience: 'interne', etapes: DELAIS,
  resume: 'Comprendre comment l’échéance est calculée, recalculée, puis figée à l’attribution.',
  intro: 'Les délais sont paramétrables : suivez la vie d’une échéance du calcul au gel.',
  fin: { texte: 'Vous maîtrisez le cycle de l’échéance : calculée, recalculée tant que le dossier n’est pas attribué, puis figée.', lien: { to: '/tarifs?onglet=delais', label: 'Ouvrir les délais' } },
}

/* ── 3. Cas particuliers ─────────────────────────────────────────────────── */
const CAS: Etape[] = [
  {
    cle: 'derogation', titre: 'Valider un PV non conforme', acteur: 'Responsable',
    resume: "Un PV dont la mise en forme n'est pas conforme peut quand même être validé, mais il faut en donner la raison, conservée dans l'historique.",
    tips: ["Le document n'est jamais modifié automatiquement."],
    ecran: (next, etat, maj) => (
      <Ecran url="/dossiers/2026-CE-0008 · Valider le PV">
        <div className="row"><Pill tone="red" dot>Non conforme</Pill><span className="small muted">Version 2 · police « Calibri » sur 8 % du texte</span></div>
        <div className="field"><span className="label">Motif de dérogation</span>
          <div className="input">{etat.motif ? 'Mise en forme refaite par nos soins avant envoi au client' : <span className="muted">À renseigner…</span>}</div></div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.motif ? <Action onClick={next} icon={<CheckCircle2 size={16} />}>Valider définitivement</Action>
            : <Action onClick={() => maj({ motif: true })} icon={<FileWarning size={16} />}>Saisir le motif</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'retrait', titre: "Un retranscripteur n'est plus disponible", acteur: 'Responsable',
    resume: "Vous retirez la mission : le dossier repasse « à attribuer », l'accès à l'audio est coupé immédiatement et le retranscripteur est prévenu.",
    tips: ["Un motif est obligatoire et tracé.", "L'échéance client reste figée : vous réattribuez avec les mêmes contraintes."],
    ecran: (next, etat, maj) => (
      <Ecran url="/dossiers/2026-CE-0015">
        <div className="card list-item"><div className="list-main"><div className="list-title">Karim Benali</div><div className="small muted">Attribuée le 14 nov. · rendu le 29 nov.</div></div>
          <Pill tone={etat.retire ? 'gray' : 'blue'}>{etat.retire ? 'Retirée' : 'En cours'}</Pill></div>
        {etat.retire && <div className="callout small demo-flash">Dossier <strong>à attribuer</strong> · Karim n'a plus accès à l'audio · notification envoyée · motif « indisponibilité »</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.retire ? <Action onClick={next}>Continuer</Action> : <Action onClick={() => maj({ retire: true })} icon={<UserMinus size={16} />}>Retirer la mission</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'blocage', titre: 'Bloquer un dossier', acteur: 'Responsable',
    resume: "Audio inaudible, client injoignable… Vous bloquez le dossier avec un motif. Débloquer le remet exactement à l'étape précédente.",
    tips: ["Un dossier bloqué n'accepte plus de dépôt de PV."],
    ecran: (next, etat, maj) => (
      <Ecran url="/dossiers/2026-CE-0016">
        <div className="row"><strong>2026-CE-0016</strong><Pill tone={etat.bloque ? 'red' : 'blue'} dot>{etat.bloque ? 'Bloqué' : 'En cours'}</Pill></div>
        {etat.bloque && <div className="callout callout-amber small demo-flash">Bloqué : « audio inaudible entre 20 et 35 min ». À débloquer dès réception d'un nouvel enregistrement.</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.bloque ? <Action onClick={next} icon={<Unlock size={16} />}>Débloquer</Action> : <Action onClick={() => maj({ bloque: true })} icon={<Ban size={16} />}>Bloquer le dossier</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'partiel', titre: 'Un règlement en deux fois', acteur: 'Comptabilité',
    resume: "Le client règle une partie de la facture : vous enregistrez chaque encaissement. La facture passe « partiellement réglée » puis « réglée ».",
    tips: ["Un montant supérieur au reste à encaisser est refusé."],
    ecran: (next, etat, maj) => (
      <Ecran url="/finance · FAC-2026-0003">
        <Ligne a="Montant TTC" b="100,00 €" fort /><Ligne a="Encaissé" b={etat.premier ? (etat.second ? '100,00 €' : '40,00 €') : '0,00 €'} fort />
        <Pill tone={etat.second ? 'green' : etat.premier ? 'violet' : 'blue'} dot>{etat.second ? 'Réglée' : etat.premier ? 'Partiellement réglée' : 'Facture émise'}</Pill>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {!etat.premier && <Action onClick={() => maj({ premier: true })} icon={<Wallet size={16} />}>Enregistrer 40 €</Action>}
          {etat.premier && !etat.second && <Action onClick={() => maj({ second: true })} icon={<Wallet size={16} />}>Enregistrer les 60 € restants</Action>}
          {etat.second && <Action onClick={next}>Continuer</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'annulation', titre: 'Corriger une erreur de facture', acteur: 'Comptabilité',
    resume: "Une facture n'est jamais supprimée : on l'annule avec un motif et son numéro est conservé. Le dossier redevient « à facturer ».",
    tips: ["Une facture déjà réglée en partie ne s'annule pas : il faut un avoir comptable."],
    ecran: (next, etat, maj) => (
      <Ecran url="/finance · FAC-2026-0004">
        <div className="row"><strong>FAC-2026-0004</strong><Pill tone={etat.annulee ? 'gray' : 'blue'}>{etat.annulee ? 'Annulée' : 'Émise'}</Pill></div>
        <p className="small muted">Payeur erroné : la facture était au nom du mauvais CSE.</p>
        {etat.annulee && <div className="callout small demo-flash">Facture annulée (motif « payeur erroné »), numéro conservé · dossier de nouveau <strong>à facturer</strong> → nouvelle facture <strong>FAC-2026-0005</strong></div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.annulee ? <Action onClick={next}>Continuer</Action> : <Action onClick={() => maj({ annulee: true })} icon={<Receipt size={16} />}>Annuler la facture</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'paiement', titre: 'Payer le retranscripteur', acteur: 'Comptabilité',
    resume: "Le paiement suit son propre cycle, indépendant de l'encaissement : à payer, validé, puis payé avec la date du virement. Un paiement effectué est figé.",
    tips: ["Un ajustement de montant exige un motif.", "L'IBAN est chiffré et visible uniquement par l'administratrice."],
    ecran: (next, etat, maj) => (
      <Ecran url="/finance · Paiements à effectuer">
        <div className="card list-item"><div className="list-main"><div className="list-title">Léa Durand · 2026-CE-0001</div>
          <div className="small muted">{etat.paye ? 'Virement du 17 nov. 2026 · figé' : 'Montant : 100,00 €'}</div></div>
          <Pill tone={etat.paye ? 'green' : etat.valide ? 'blue' : 'amber'} dot>{etat.paye ? 'Payé' : etat.valide ? 'Validé' : 'À payer'}</Pill></div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {!etat.valide && <Action onClick={() => maj({ valide: true })}>Valider le paiement</Action>}
          {etat.valide && !etat.paye && <Action onClick={() => maj({ paye: true })} icon={<Wallet size={16} />}>Marquer payé (date du virement)</Action>}
          {etat.paye && <Action onClick={next}>Terminer</Action>}
        </div>
      </Ecran>
    ),
  },
]

export const PARCOURS_CAS: Parcours = {
  id: 'cas', titre: 'Quand ça se complique : les cas particuliers', duree: '6 min', audience: 'interne', etapes: CAS,
  resume: 'Dérogation, retrait de mission, blocage, règlement en deux fois, facture annulée, paiement du retranscripteur.',
  intro: 'Les situations hors parcours idéal, et comment la plateforme les gère sans rien perdre.',
  fin: { texte: 'Vous savez gérer les imprévus : chaque correction est tracée et rien n’est jamais supprimé.', lien: { to: '/dossiers', label: 'Voir les dossiers' } },
}

/* ── 4. Équipe et accès ──────────────────────────────────────────────────── */
const EQUIPE: Etape[] = [
  {
    cle: 'acces', titre: "Créer l'accès d'un retranscripteur", acteur: 'Administratrice',
    resume: "Après avoir créé la fiche, « Créer l'accès » génère un mot de passe temporaire, affiché une seule fois.",
    tips: ["Transmettez-le par téléphone ou SMS, pas par le même canal que l'identifiant.", "Il n'est plus consultable ensuite : en cas de perte, on le réinitialise."],
    ecran: (next, etat, maj) => (
      <Ecran url="/retranscripteurs">
        <div className="card list-item"><div className="list-main"><div className="list-title">Inès Moreau</div><div className="small muted">ines.moreau@exemple.fr · spécialités : CSSCT</div></div>
          {!etat.cree && <Action onClick={() => maj({ cree: true })} icon={<KeyRound size={16} />}>Créer l'accès</Action>}</div>
        {etat.cree && (
          <div className="callout callout-amber stack demo-flash" style={{ gap: 6 }}>
            <strong>Identifiants à transmettre — affichés une seule fois</strong>
            <div className="secret">Xk9-demo-fictif-72</div>
            <span className="small muted row"><Copy size={14} />Mot de passe temporaire fictif : changement exigé à la première connexion</span>
            <div><Action onClick={next}>J'ai noté ces informations</Action></div>
          </div>
        )}
      </Ecran>
    ),
  },
  {
    cle: 'connexion', titre: 'Première connexion', acteur: 'Retranscripteur·rice',
    resume: "À sa première connexion, la personne doit choisir son propre mot de passe avant d'accéder à quoi que ce soit.",
    tips: ["12 caractères minimum et 3 types de caractères.", "Les anciennes sessions sont fermées après un changement de mot de passe."],
    ecran: (next) => (
      <Ecran url="/mot-de-passe">
        <div className="field"><span className="label">Mot de passe temporaire</span><div className="input">••••••••••••••••</div></div>
        <div className="field"><span className="label">Nouveau mot de passe</span><div className="input">••••••••••••••</div></div>
        <ul className="small" style={{ margin: 0, paddingLeft: 18, color: 'var(--green)' }}><li>12 caractères minimum</li><li>3 types de caractères</li></ul>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next} icon={<ShieldCheck size={16} />}>Enregistrer le mot de passe</Action></div>
      </Ecran>
    ),
  },
  {
    cle: 'droits', titre: 'Régler les droits de la coordinatrice', acteur: 'Administratrice',
    resume: "Les droits de la coordinatrice sont pré-cochés selon son rôle et ajustables. Ici, vous lui donnez accès à la facturation.",
    tips: ["Seule l'administratrice gère les utilisateurs et voit les IBAN : ces droits ne se délèguent pas."],
    ecran: (next, etat, maj) => (
      <Ecran url="/utilisateurs · Gérer Nadia">
        <label className="checkbox"><input type="checkbox" checked readOnly />Relire les PV et demander des corrections</label>
        <label className="checkbox"><input type="checkbox" checked readOnly />Attribuer les missions</label>
        <label className="checkbox"><input type="checkbox" checked={!!etat.finance} readOnly />Consulter les factures et règlements</label>
        {etat.finance && <div className="callout small demo-flash">Nadia voit désormais l'entrée « Facturation » dans son menu et les montants des dossiers.</div>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.finance ? <Action onClick={next}>Enregistrer</Action> : <Action onClick={() => maj({ finance: true })}>Cocher « factures et règlements »</Action>}
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'adresse', titre: 'Remplacer une adresse de connexion', acteur: 'Administratrice',
    resume: "Les comptes initiaux ont des adresses provisoires. Vous les remplacez par les vraies adresses : le mot de passe ne change pas.",
    tips: ["Faites-le avant d'activer les emails : les notifications partent à l'adresse du compte."],
    ecran: (next, etat, maj) => (
      <Ecran url="/utilisateurs · Gérer">
        <div className="field"><span className="label">Email de connexion</span>
          <div className={`input ${etat.adresse ? 'demo-flash' : ''}`}>{etat.adresse ? 'nadia.martin@exemple.fr' : 'coordinatrice@a2c.example'}</div></div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          {etat.adresse ? <Action onClick={next}>Enregistrer</Action> : <Action onClick={() => maj({ adresse: true })}>Saisir la vraie adresse</Action>}
        </div>
      </Ecran>
    ),
  },
]

export const PARCOURS_EQUIPE: Parcours = {
  id: 'equipe', titre: 'Accès et droits de l’équipe', duree: '3 min', audience: 'interne', etapes: EQUIPE,
  resume: 'Créer un accès, première connexion, droits de la coordinatrice, vraies adresses de connexion.',
  intro: 'Mettre l’équipe en place : comptes, mots de passe et droits.',
  fin: { texte: 'Votre équipe est prête : comptes sécurisés, droits ajustés, vraies adresses.', lien: { to: '/utilisateurs', label: 'Ouvrir les utilisateurs' } },
}

/* ── 5. Ma première mission (retranscripteur) ───────────────────────────── */
const MISSION: Etape[] = [
  {
    cle: 'recevoir', titre: 'Recevoir une mission', acteur: 'Retranscripteur·rice',
    resume: "Une notification vous prévient. Votre mission apparaît sous forme de carte, avec l'échéance et les consignes de la responsable.",
    tips: ["Vous ne voyez que vos propres missions."],
    ecran: (next) => (
      <Ecran url="/mes-missions">
        <div className="callout small"><strong>🔔 Nouvelle mission : 2026-CE-0021</strong> · À rendre au plus tard le 29 nov.</div>
        <div className="card mission" style={{ padding: 16 }}>
          <div className="mission-top"><div><div className="mission-ref">2026-CE-0021 · CE</div><div className="mission-title">Plénière de novembre</div></div><Pill tone="blue" dot>À commencer</Pill></div>
          <div className="callout small"><strong>Consignes :</strong> noms des intervenants dans le fichier joint à l'audio.</div>
          <Action onClick={next}>Ouvrir ma mission</Action>
        </div>
      </Ecran>
    ),
  },
  {
    cle: 'audio', titre: "Télécharger l'audio", acteur: 'Retranscripteur·rice',
    resume: "L'audio vous est transmis par la plateforme : aucun accès OneDrive ni lien n'est nécessaire.",
    tips: ["Le téléchargement n'est possible que pendant votre mission : il est coupé si elle vous est retirée ou une fois validée."],
    ecran: (next) => (
      <Ecran url="/mes-missions">
        <div className="section-title">1. L'audio</div>
        <Action onClick={next}>Télécharger l'audio</Action>
        <span className="hint">Plénière_novembre.mp3 · 71 Mo</span>
      </Ecran>
    ),
  },
  {
    cle: 'depot', titre: 'Déposer votre PV', acteur: 'Retranscripteur·rice',
    resume: "Le PV doit être un fichier Word (.docx), en Comic Sans MS taille 12. Un contrôle automatique vous répond tout de suite.",
    tips: ["Les fichiers PDF, .doc ou renommés en .docx sont refusés.", "Le rapport indique les paragraphes concernés : vous corrigez vous-même."],
    ecran: (next, etat, maj) => (
      <Ecran url="/mes-missions · 2. Mon PV">
        {!etat.depose && <Action onClick={() => maj({ depose: true })}>Envoyer mon PV (PV_novembre.docx)</Action>}
        {etat.depose && !etat.corrige && (
          <>
            <div className="row" style={{ justifyContent: 'space-between' }}><strong>Version 1</strong><Pill tone="red" dot>Non conforme</Pill></div>
            <div className="small" style={{ color: 'var(--red)', fontWeight: 600 }}>12 % du texte ne respecte pas « Comic Sans MS 12 pt » (paragraphes 8 à 10 en Arial)</div>
            <Action onClick={() => maj({ corrige: true })}>Redéposer une version corrigée</Action>
          </>
        )}
        {etat.corrige && (
          <>
            <div className="row" style={{ justifyContent: 'space-between' }}><strong>Version 2</strong><Pill tone="green" dot>Conforme</Pill></div>
            <div className="small" style={{ color: 'var(--green)', fontWeight: 600 }}>Document conforme (Comic Sans MS, 12 pt)</div>
            <Action onClick={next}>Continuer</Action>
          </>
        )}
      </Ecran>
    ),
  },
  {
    cle: 'correction', titre: 'Une correction est demandée', acteur: 'Responsable',
    resume: "Après relecture, la responsable peut demander une correction. Son message apparaît sur votre carte et vous êtes notifié(e).",
    tips: ["Vos versions précédentes sont conservées : rien n'est écrasé."],
    ecran: (next, etat, maj) => (
      <Ecran url="/mes-missions">
        <div className="callout callout-amber"><strong>Correction demandée le 20 nov.</strong>
          <p style={{ marginTop: 6 }}>Merci de compléter l'intervention de M. Martin en page 4.</p></div>
        {etat.v3 ? <div className="row demo-flash"><strong>Version 3</strong><Pill tone="green" dot>Conforme</Pill><span className="small muted">En relecture</span></div> : null}
        {etat.v3 ? <Action onClick={next}>Continuer</Action> : <Action onClick={() => maj({ v3: true })}>Déposer la version corrigée</Action>}
      </Ecran>
    ),
  },
  {
    cle: 'valide', titre: 'Mission validée', acteur: 'Responsable',
    resume: "Une fois le PV validé, la mission passe dans l'onglet « Terminées ». Le paiement est géré par l'administration.",
    tips: ["Supprimez vos copies locales de l'audio et du PV : ils sont confidentiels."],
    ecran: (next) => (
      <Ecran url="/mes-missions · Terminées">
        <div className="card list-item"><div className="list-main"><div className="list-title">2026-CE-0021 · Plénière de novembre</div><div className="small muted">Validée le 24 nov. 2026</div></div>
          <Pill tone="green" dot>Validé</Pill></div>
        <div className="row" style={{ color: 'var(--green)', fontWeight: 600 }}><CheckCircle2 size={18} />Mission validée — merci pour votre travail.</div>
        <div className="row" style={{ justifyContent: 'flex-end' }}><Action onClick={next}>Terminer</Action></div>
      </Ecran>
    ),
  },
]

export const PARCOURS_MISSION: Parcours = {
  id: 'mission', titre: 'Ma première mission', duree: '3 min', audience: 'prestataire', etapes: MISSION,
  resume: 'De la notification au PV validé : télécharger l’audio, déposer son PV, corriger.',
  intro: 'Un exemple fictif pour savoir quoi faire dès votre première mission.',
  fin: { texte: 'Vous savez recevoir une mission, déposer un PV conforme et traiter une correction.', lien: { to: '/mes-missions', label: 'Voir mes missions' } },
}
