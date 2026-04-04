import { useState } from 'react'
import { useAuth } from '@/features/auth/AuthContext'
import { TRANCHES_CLIENT } from '@/utils/forfaits'

// ─── Sections ─────────────────────────────────────────────────────────────────

type Section = {
  id: string
  titre: string
  roles: string[]  // quels rôles voient cette section
  contenu: React.ReactNode
}

// ─── Composants utilitaires ───────────────────────────────────────────────────

function Bloc({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 10px', color: 'var(--color-text)' }}>
        {titre}
      </h3>
      <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--color-text)' }}>{children}</div>
    </div>
  )
}

function Etape({ num, titre, children }: { num: number; titre: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 14, marginBottom: 14 }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', background: 'var(--color-primary)',
        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 13, fontWeight: 700, flexShrink: 0, marginTop: 1,
      }}>{num}</div>
      <div>
        <div style={{ fontWeight: 600, marginBottom: 2, fontSize: 13 }}>{titre}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.6 }}>{children}</div>
      </div>
    </div>
  )
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 'var(--radius)',
      padding: '10px 14px', fontSize: 12, color: '#1e40af', lineHeight: 1.6, marginTop: 10,
    }}>
      ℹ️ {children}
    </div>
  )
}

function Attention({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 'var(--radius)',
      padding: '10px 14px', fontSize: 12, color: '#9a3412', lineHeight: 1.6, marginTop: 10,
    }}>
      ⚠️ {children}
    </div>
  )
}

// ─── Contenu des sections ─────────────────────────────────────────────────────

const SECTION_WORKFLOW: React.ReactNode = (
  <>
    <Bloc titre="Cycle de vie d'un dossier">
      <p>La grande majorité des transitions de statut se font <strong>automatiquement</strong>. Vous n'avez presque rien à cliquer manuellement.</p>
      <div style={{ overflowX: 'auto', marginTop: 10 }}>
        <table style={{ fontSize: 12, borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr style={{ background: 'var(--color-bg-secondary)' }}>
              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>Étape</th>
              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>Déclencheur</th>
              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>Auto ?</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['Reçu → En retranscription', 'Création du dossier + affectation des 2 prestataires', '✅ Auto'],
              ['En retranscription → À corriger', 'Retranscripteur clique "J\'ai terminé"', '✅ Auto'],
              ['À corriger → En correction', 'Correcteur clique "J\'ai terminé" (commence)', '✅ Auto'],
              ['En correction → En mise en forme', 'Correcteur clique "J\'ai terminé" (livre)', '✅ Auto'],
              ['En mise en forme → Envoyé', 'Admin valide le calcul tarifaire', '✅ Auto'],
              ['Envoyé → Facturé', 'Admin génère la facture', '✅ Auto'],
              ['Facturé → Payé entrant', 'Admin marque la facture "Soldée"', '✅ Auto'],
              ['Payé entrant → Prestataires payés', 'Admin paye tous les prestataires', '✅ Auto'],
              ['Tout statut → Bloqué / Incomplet', 'Admin force manuellement via Workflow', '🖱 Manuel'],
            ].map(([e, s, q]) => (
              <tr key={e} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                <td style={{ padding: '5px 10px', fontWeight: 500 }}>{e}</td>
                <td style={{ padding: '5px 10px', color: 'var(--color-text-muted)' }}>{s}</td>
                <td style={{ padding: '5px 10px' }}>{q}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Bloc>

    <Bloc titre="Statuts spéciaux">
      <p><strong>Bloqué</strong> : le dossier est en pause (problème technique, litige...). Il peut être débloqué depuis n'importe quelle étape via la section Workflow.</p>
      <p><strong>Incomplet</strong> : des informations manquent (fichier son non reçu, prise de notes absente...). Retourne en qualification une fois complété.</p>
    </Bloc>
  </>
)

const SECTION_DOSSIER_COORD: React.ReactNode = (
  <>
    <Bloc titre="Créer et gérer un dossier">
      <Etape num={1} titre="Dossiers → Nouveau dossier">
        Renseigner le client, le type d'instance (CE, CMAS, CSSCT…), la date de séance, la durée audio et la date de réception.
      </Etape>
      <Etape num={2} titre="Saisir la qualification (optionnel)">
        Section <em>Qualification</em> : cocher urgent, SNP, prestation spéciale si applicable. Ces critères influencent le calcul tarifaire.
      </Etape>
      <Etape num={3} titre="Affecter les prestataires">
        Section <em>Affectations</em> : choisir un retranscripteur et un correcteur. Dès qu'ils sont affectés, le dossier passe automatiquement en <em>En retranscription</em> et <strong>chaque prestataire reçoit un email</strong> avec la date limite.
      </Etape>
      <Etape num={4} titre="Ajouter le fichier audio">
        Section <em>Fichiers</em> : coller l'URL de partage OneDrive du fichier audio pour que le retranscripteur puisse y accéder.
      </Etape>
      <Etape num={5} titre="Attendre — le reste est automatique">
        Le retranscripteur livre → le correcteur est notifié → le correcteur livre → le calcul tarifaire se lance automatiquement si le nombre de pages est connu.
      </Etape>
      <Etape num={6} titre="Valider le calcul et générer la facture">
        Si le calcul correspond au forfait standard A2C, il est déjà validé automatiquement. Sinon, ajuster et valider manuellement. Puis <em>Générer facture</em> — le dossier passe en <em>Facturé</em> et un email est envoyé au client.
      </Etape>
    </Bloc>

    <Note>
      La date limite de rendu est calculée automatiquement depuis la durée audio : ≤1h → 7 jours · 1h–4h → 18 jours · &gt;4h → 25 jours. Elle peut toujours être modifiée manuellement lors de l'affectation.
    </Note>

    <Bloc titre="Supprimer un dossier">
      <p>Un dossier peut être supprimé définitivement depuis sa fiche (bouton en bas à droite du header) <strong>uniquement si aucune facture n'a été générée</strong>. Cette action est irréversible.</p>
    </Bloc>
  </>
)

const SECTION_CALCUL: React.ReactNode = (
  <>
    <Bloc titre="Forfait client A2C">
      <p>Le montant facturé au client est un <strong>forfait fixe selon le nombre de pages</strong> de la retranscription finale (format standard : interligne simple, Times New Roman 12) :</p>
      <table style={{ fontSize: 12, borderCollapse: 'collapse', marginTop: 8, width: '100%', maxWidth: 320 }}>
        <thead>
          <tr style={{ background: 'var(--color-bg-secondary)' }}>
            <th style={{ padding: '5px 10px', textAlign: 'left' }}>Nombre de pages</th>
            <th style={{ padding: '5px 10px', textAlign: 'right' }}>Forfait</th>
          </tr>
        </thead>
        <tbody>
          {TRANCHES_CLIENT.map((t) => (
            <tr key={t.label} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
              <td style={{ padding: '4px 10px' }}>{t.label}</td>
              <td style={{ padding: '4px 10px', textAlign: 'right', fontWeight: 600 }}>{t.montant} €</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Note>Au-delà de 100 pages, contacter A2C pour un devis personnalisé.</Note>
    </Bloc>

    <Bloc titre="Calcul automatique vs manuel">
      <p>Quand le correcteur livre son travail, <strong>le calcul se lance automatiquement</strong> si le nombre de pages final est renseigné. S'il correspond exactement au forfait A2C standard, il est également <strong>validé automatiquement</strong> — aucune action requise.</p>
      <p>Si un ajustement est nécessaire (geste commercial, cas particulier) :</p>
      <Etape num={1} titre="Ouvrir le dossier → section Calcul tarifaire">
        Cliquer sur <em>Ajuster</em> pour modifier le montant, ou <em>Recalculer</em> si le nombre de pages a changé.
      </Etape>
      <Etape num={2} titre="Valider manuellement">
        Cliquer sur <em>Valider</em> pour figer le montant. Le dossier passe automatiquement en <em>Envoyé</em>.
      </Etape>
    </Bloc>

    <Bloc titre="Rémunération des prestataires">
      <p>Calculée automatiquement à la génération de la facture, depuis les grilles tarifaires :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>Retranscripteur</strong> : 0,25 €/page (base)</li>
        <li><strong>Correcteur</strong> : 0,12 €/page (base)</li>
        <li><strong>Urgence</strong> : +30% sur la base</li>
      </ul>
      <p>Les paiements sont créés automatiquement (statut <em>À payer</em>) mais restent à valider et payer manuellement.</p>
      <Note>Ces taux sont modifiables dans <em>Administration → Grilles tarifaires</em>.</Note>
    </Bloc>
  </>
)

const SECTION_FACTURATION: React.ReactNode = (
  <>
    <Bloc titre="Générer une facture">
      <p>La facture se génère <strong>dès que le calcul tarifaire est validé</strong>. Le dossier passe automatiquement en <em>Facturé</em> et un email est envoyé au client (si son email est renseigné dans sa fiche).</p>
      <Etape num={1} titre="Cliquer sur Générer facture">
        Section <em>Facturation</em> du dossier. Choisir si la TVA est applicable (la plupart des CE/CMAS ne le sont pas).
      </Etape>
      <Etape num={2} titre="Voir le PDF">
        Bouton <em>Voir la facture ↗</em> — le PDF s'ouvre dans un nouvel onglet.
      </Etape>
      <Etape num={3} titre="Suivre le paiement">
        Quand le client paie : <em>Non payée</em> → <em>Partiellement payée</em> → <em>Soldée</em>. En marquant <em>Soldée</em>, le dossier passe automatiquement en <em>Payé entrant</em>.
      </Etape>
    </Bloc>

    <Bloc titre="Supprimer une facture erronée">
      <p>Si la facture a été générée avec un montant incorrect (calcul à 0, pages erronées…), un bouton <em>Supprimer la facture</em> apparaît tant qu'elle n'est pas payée. Cela permet de recalculer puis régénérer.</p>
    </Bloc>

    <Bloc titre="Paiements prestataires">
      <p>Les paiements prestataires sont créés <strong>automatiquement</strong> à la génération de la facture (statut <em>À payer</em>). Les montants sont issus des grilles tarifaires.</p>
      <p>Le paiement réel reste <strong>manuel</strong> : section <em>Paiements prestataires</em> → marquer chaque paiement comme <em>Payé</em>. Quand tous sont payés, le dossier passe automatiquement en <em>Prestataires payés</em>.</p>
      <Attention>
        Ne pas marquer comme payé avant d'avoir effectivement viré le montant. Cette action sert de trace comptable.
      </Attention>
    </Bloc>

    <Note>
      Délais de paiement indicatifs : CE → 2 à 3 semaines après envoi · CHSCT → 2 mois maximum.
    </Note>
  </>
)

const SECTION_PRESTATAIRE: React.ReactNode = (
  <>
    <Bloc titre="Votre espace Mes missions">
      <p>La page <strong>Mes missions</strong> (accessible depuis le menu) affiche tous les dossiers qui vous ont été confiés :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>En cours</strong> : missions actives, avec date limite et bouton d'action</li>
        <li><strong>Terminées</strong> : missions livrées ou validées, à titre d'historique</li>
      </ul>
      <p>Vous pouvez aussi accéder au détail d'un dossier en cliquant dessus — vous y verrez les informations essentielles et les fichiers partagés.</p>
    </Bloc>

    <Bloc titre="Déclarer votre travail terminé">
      <Etape num={1} titre="Terminer votre travail">
        Réaliser la retranscription ou la correction. Déposer le fichier finalisé sur OneDrive dans le dossier partagé prévu.
      </Etape>
      <Etape num={2} titre="Ajouter le lien OneDrive dans le dossier (recommandé)">
        Dans la section <em>Fichiers</em> du dossier : <em>+ Ajouter</em> → coller l'URL de partage OneDrive du fichier rendu.
      </Etape>
      <Etape num={3} titre="Cliquer sur « J'ai terminé »">
        Depuis <em>Mes missions</em> ou directement en haut de la fiche dossier. Un message de confirmation s'affiche.
      </Etape>
      <Etape num={4} titre="C'est tout !">
        Le dossier avance automatiquement. Si vous êtes retranscripteur, le correcteur est notifié par email. Si vous êtes correcteur, la coordinatrice est notifiée et le calcul se lance automatiquement.
      </Etape>
    </Bloc>

    <Bloc titre="Notifications par email">
      <p>Vous recevez un email automatique à chaque nouvelle mission affectée, avec :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li>La référence du dossier</li>
        <li>Votre rôle (retranscription ou correction)</li>
        <li>La date limite de rendu</li>
      </ul>
      <Note>Si vous ne recevez pas d'email, vérifiez vos spams ou contactez l'administratrice pour que la configuration email soit activée.</Note>
    </Bloc>

    <Bloc titre="Ce que vous voyez (et ce que vous ne voyez pas)">
      <p>Par souci de confidentialité, votre accès est limité à ce qui est nécessaire à votre mission :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li>✅ Référence du dossier, type d'instance, dates, durée audio</li>
        <li>✅ Fichiers partagés (audio, retranscription…)</li>
        <li>✅ Historique du dossier</li>
        <li>❌ Nom du client, informations financières, calculs, factures</li>
        <li>❌ Notes internes, autres prestataires</li>
      </ul>
    </Bloc>

    <Attention>
      Votre compte doit avoir <strong>exactement le même email</strong> que votre fiche prestataire pour accéder à vos missions. Si vous ne voyez pas vos dossiers, contactez l'administratrice.
    </Attention>
  </>
)

const SECTION_FICHIERS: React.ReactNode = (
  <>
    <Bloc titre="Fonctionnement OneDrive">
      <p>Les fichiers ne sont <strong>pas stockés dans l'application</strong>. Ils restent sur votre espace OneDrive (Microsoft 365).</p>
      <p>L'application enregistre uniquement le <strong>lien de partage</strong> OneDrive, ce qui permet d'ouvrir le fichier directement depuis la fiche dossier.</p>
    </Bloc>

    <Bloc titre="Comment ajouter un fichier">
      <Etape num={1} titre="Déposer le fichier sur OneDrive">
        Mettre le fichier dans votre espace OneDrive ou SharePoint, dans le dossier prévu.
      </Etape>
      <Etape num={2} titre="Copier le lien de partage">
        Clic droit → <em>Partager</em> → <em>Copier le lien</em>. Le lien doit être accessible aux personnes concernées.
      </Etape>
      <Etape num={3} titre="Coller le lien dans l'application">
        Section <em>Fichiers</em> du dossier → <em>+ Ajouter</em> → coller l'URL OneDrive.
      </Etape>
    </Bloc>
    <Note>Types de fichiers : audio brut, retranscription v1, retranscription corrigée, facture, document client.</Note>
  </>
)

const SECTION_ADMIN: React.ReactNode = (
  <>
    <Bloc titre="Ce qui est automatique — récapitulatif">
      <p>Voici ce que le système fait sans intervention de votre part :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20, lineHeight: 2 }}>
        <li>✅ Transition dossier à chaque étape (retranscription → correction → envoi…)</li>
        <li>✅ Email au prestataire lors de l'affectation (avec date limite)</li>
        <li>✅ Email au correcteur quand la retranscription est livrée</li>
        <li>✅ Email à l'administratrice quand la correction est livrée</li>
        <li>✅ Calcul tarifaire déclenché à la livraison du correcteur</li>
        <li>✅ Auto-validation du calcul si montant = forfait A2C standard</li>
        <li>✅ Date limite de rendu calculée depuis la durée audio</li>
        <li>✅ Création des paiements prestataires à la génération de la facture</li>
        <li>✅ Email au client à la génération de la facture</li>
        <li>✅ Transitions dossier à chaque événement financier (soldée → payé entrant…)</li>
      </ul>
      <p>Vous n'intervenez manuellement que pour : valider le calcul (si ajustement), générer la facture, marquer le paiement client, payer les prestataires.</p>
    </Bloc>

    <Bloc titre="Ajouter un prestataire">
      <Etape num={1} titre="Prestataires → Nouveau prestataire">
        Renseigner nom, rôle (retranscripteur / correcteur / les deux), email, et IBAN si disponible.
      </Etape>
      <Etape num={2} titre="Utilisateurs → Nouveau compte">
        Créer le compte de connexion avec <strong>exactement le même email</strong> que la fiche prestataire. Rôle : Retranscripteur ou Correcteur selon le cas.
      </Etape>
      <Etape num={3} titre="Communiquer les identifiants">
        Transmettre email + mot de passe provisoire au prestataire par email ou SMS. Il pourra se connecter sur l'application et accéder à ses missions.
      </Etape>
      <Attention>
        L'email doit être identique dans les deux fiches (prestataire et compte utilisateur). C'est ce lien qui permet au système d'associer les missions au bon compte.
      </Attention>
    </Bloc>

    <Bloc titre="Gérer les comptes utilisateurs">
      <p><em>Administration → Utilisateurs</em> — rôles disponibles :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>Administratrice</strong> : accès complet, gestion des comptes et grilles</li>
        <li><strong>Coordinatrice</strong> : gestion dossiers, affectations, calculs</li>
        <li><strong>Retranscripteur / Correcteur</strong> : espace "Mes missions" uniquement</li>
        <li><strong>Comptabilité</strong> : factures et paiements uniquement</li>
        <li><strong>Lecture seule</strong> : consultation sans modification</li>
      </ul>
      <p>Un compte peut être désactivé (sans suppression) depuis la fiche utilisateur — le prestataire ne pourra plus se connecter.</p>
    </Bloc>

    <Bloc titre="Gérer les grilles tarifaires">
      <p><em>Administration → Grilles tarifaires</em> — taux de rémunération prestataires actuels :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>Retranscripteur</strong> : 0,25 €/page</li>
        <li><strong>Correcteur</strong> : 0,12 €/page</li>
        <li><strong>Urgence</strong> : +30%</li>
      </ul>
      <p>Une grille peut être désactivée et réactivée à tout moment. Pour modifier un taux, désactiver l'ancienne règle et en ajouter une nouvelle.</p>
      <Note>
        Le forfait client (50€–500€) est distinct des grilles — il est défini par les modalités A2C et s'applique automatiquement même sans grille client configurée.
      </Note>
    </Bloc>

    <Bloc titre="Activer les notifications email">
      <p>Les emails sont envoyés automatiquement si les variables SMTP sont configurées dans Railway :</p>
      <pre style={{ background: 'var(--color-bg-secondary)', padding: '8px 12px', borderRadius: 'var(--radius)', fontSize: 12, overflowX: 'auto', margin: '8px 0' }}>
{`SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre@email.com
SMTP_PASSWORD=mot-de-passe-application
EMAIL_FROM=A2C Retranscriptions <contact@a2c.fr>
ADMIN_EMAIL=admin@a2c.fr`}
      </pre>
      <p>Compatible Gmail (avec mot de passe d'application), Outlook, OVH, Brevo… Si ces variables sont absentes, les emails sont simplement ignorés — aucune erreur.</p>
    </Bloc>
  </>
)

// ─── Toutes les sections ──────────────────────────────────────────────────────

const SECTIONS: Section[] = [
  {
    id: 'workflow',
    titre: 'Cycle de vie d\'un dossier',
    roles: ['administratrice', 'coordinatrice', 'comptabilite', 'lecture_seule'],
    contenu: SECTION_WORKFLOW,
  },
  {
    id: 'dossier',
    titre: 'Gérer un dossier (coordinatrice)',
    roles: ['administratrice', 'coordinatrice'],
    contenu: SECTION_DOSSIER_COORD,
  },
  {
    id: 'calcul',
    titre: 'Calcul tarifaire',
    roles: ['administratrice', 'coordinatrice', 'comptabilite'],
    contenu: SECTION_CALCUL,
  },
  {
    id: 'facturation',
    titre: 'Facturation et paiements',
    roles: ['administratrice', 'coordinatrice', 'comptabilite'],
    contenu: SECTION_FACTURATION,
  },
  {
    id: 'fichiers',
    titre: 'Fichiers OneDrive',
    roles: ['administratrice', 'coordinatrice', 'retranscripteur', 'correcteur'],
    contenu: SECTION_FICHIERS,
  },
  {
    id: 'prestataire',
    titre: 'Espace prestataire',
    roles: ['retranscripteur', 'correcteur'],
    contenu: SECTION_PRESTATAIRE,
  },
  {
    id: 'admin',
    titre: 'Guide administrateur',
    roles: ['administratrice'],
    contenu: SECTION_ADMIN,
  },
]

// ─── Page ─────────────────────────────────────────────────────────────────────

export function AidePage() {
  const { user } = useAuth()
  const [activeId, setActiveId] = useState<string | null>(null)

  const sections = SECTIONS.filter(
    (s) => !user || s.roles.includes(user.role),
  )

  const active = sections.find((s) => s.id === activeId) ?? sections[0]

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Aide &amp; Guide d'utilisation</h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
            Documentation adaptée à votre rôle
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20, alignItems: 'start' }}>
        {/* Sidebar navigation */}
        <div className="card" style={{ padding: 8 }}>
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveId(s.id)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '8px 12px',
                fontSize: 13,
                background: active?.id === s.id ? 'var(--color-primary)' : 'none',
                color: active?.id === s.id ? '#fff' : 'var(--color-text)',
                border: 'none',
                borderRadius: 'var(--radius)',
                cursor: 'pointer',
                fontWeight: active?.id === s.id ? 600 : 400,
                marginBottom: 2,
              }}
            >
              {s.titre}
            </button>
          ))}
        </div>

        {/* Contenu */}
        {active && (
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">{active.titre}</h2>
            </div>
            <div className="card-body">
              {active.contenu}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
