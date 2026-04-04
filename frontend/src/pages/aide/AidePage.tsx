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
      <p>Chaque dossier suit un parcours étape par étape. L'avancement se fait via les boutons de transition dans la section <strong>Workflow</strong> de chaque dossier.</p>
      <div style={{ overflowX: 'auto', marginTop: 10 }}>
        <table style={{ fontSize: 12, borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr style={{ background: 'var(--color-bg-secondary)' }}>
              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>Étape</th>
              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>Signification</th>
              <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600 }}>Qui agit</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['Reçu', 'Le dossier vient d\'être créé', 'Admin / Coord'],
              ['En qualification', 'On saisit les critères (urgent, SNP, volume...)', 'Admin / Coord'],
              ['Estimé', 'Les critères sont saisis, prêt pour affectation', 'Admin / Coord'],
              ['À attribuer', 'En attente d\'affectation d\'un prestataire', 'Admin / Coord'],
              ['En retranscription', 'Le retranscripteur travaille', 'Retranscripteur'],
              ['À corriger', 'La retranscription est livrée, attente correcteur', 'Admin / Coord'],
              ['En correction', 'Le correcteur travaille', 'Correcteur'],
              ['En mise en forme', 'Finalisation du document', 'Admin / Coord'],
              ['Calcul en cours', 'Calcul tarifaire en attente de validation', 'Admin / Coord'],
              ['À valider', 'Le calcul est fait, à valider avant envoi', 'Admin / Coord'],
              ['Envoyé', 'Document envoyé au client', 'Admin / Coord'],
              ['Facturé', 'Facture générée', 'Admin / Compta'],
              ['Payé (entrant)', 'Le client a payé', 'Admin / Compta'],
              ['Prestataires payés', 'Les prestataires ont été rémunérés', 'Admin / Compta'],
              ['Archivé', 'Dossier terminé', 'Auto'],
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
      <p><strong>Bloqué</strong> : le dossier est en pause (problème technique, litige...). Il peut être débloqué depuis n'importe quelle étape.</p>
      <p><strong>Incomplet</strong> : des informations manquent (fichier son non reçu, prise de notes absente...). Retourne en qualification une fois complété.</p>
    </Bloc>
  </>
)

const SECTION_DOSSIER_COORD: React.ReactNode = (
  <>
    <Bloc titre="Créer un dossier">
      <Etape num={1} titre="Aller dans Dossiers → Nouveau dossier">
        Renseigner le client, le type d'instance (CE, CMAS, CSSCT...), la date de séance et la date de réception de l'audio.
      </Etape>
      <Etape num={2} titre="Saisir la qualification">
        Dans le dossier créé, section <em>Qualification</em> : cocher les cases pertinentes (urgent, SNP, prestation spéciale) et indiquer le volume estimé en pages.
      </Etape>
      <Etape num={3} titre="Affecter les prestataires">
        Section <em>Affectations</em> : choisir un retranscripteur et/ou un correcteur parmi les prestataires disponibles.
      </Etape>
      <Etape num={4} titre="Ajouter les fichiers OneDrive">
        Section <em>Fichiers</em> : coller l'URL de partage du fichier audio, puis de la retranscription une fois livrée.
      </Etape>
      <Etape num={5} titre="Suivre l'avancement via le Workflow">
        Faire avancer le statut au fil des étapes. Le retranscripteur et le correcteur déclarent leur livraison de leur côté.
      </Etape>
    </Bloc>
    <Note>
      La date limite est calculée automatiquement selon la durée audio : ≤1h → 7 jours, 2h–4h → 18 jours, &gt;4h → 25 jours.
    </Note>
  </>
)

const SECTION_CALCUL: React.ReactNode = (
  <>
    <Bloc titre="Comment est calculé le montant client ?">
      <p>Le montant facturé au client est un <strong>forfait fixe selon le nombre de pages</strong> de la retranscription finale :</p>
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
      <Note>Format standard : interligne simple, Times New Roman 12 points. Au-delà de 100 pages, contacter A2C pour un devis.</Note>
    </Bloc>

    <Bloc titre="Comment lancer le calcul ?">
      <Etape num={1} titre="Renseigner le nombre de pages final">
        Dans la section <em>Informations</em> du dossier, ou directement dans le formulaire de calcul.
      </Etape>
      <Etape num={2} titre="Cliquer sur Calculer">
        Section <em>Calcul tarifaire</em> → bouton <em>Calculer</em>. Le système applique le forfait client et les taux prestataires.
      </Etape>
      <Etape num={3} titre="Ajuster si besoin">
        Un ajustement manuel est possible (réduction, geste commercial...) avec un motif obligatoire.
      </Etape>
      <Etape num={4} titre="Valider le calcul">
        Cliquer sur <em>Valider</em> pour figer le montant avant génération de la facture.
      </Etape>
    </Bloc>

    <Bloc titre="Rémunération des prestataires">
      <p>Automatiquement calculée à partir des grilles tarifaires :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>Retranscripteur</strong> : 0,25 €/page (base)</li>
        <li><strong>Correcteur</strong> : 0,12 €/page (base)</li>
        <li><strong>Urgence</strong> : +30% sur la base</li>
      </ul>
      <p>Ces taux sont configurables dans <em>Administration → Grilles tarifaires</em>.</p>
    </Bloc>
  </>
)

const SECTION_FACTURATION: React.ReactNode = (
  <>
    <Bloc titre="Générer une facture">
      <Etape num={1} titre="S'assurer qu'un calcul validé existe">
        Le bouton <em>Générer facture</em> apparaît uniquement si un calcul tarifaire a été effectué.
      </Etape>
      <Etape num={2} titre="Choisir si la TVA est applicable">
        La plupart des CE/CMAS ne sont pas assujettis à la TVA. Cocher uniquement si nécessaire.
      </Etape>
      <Etape num={3} titre="Générer et télécharger le PDF">
        La facture est immédiatement disponible en PDF via le bouton <em>Voir la facture ↗</em>.
      </Etape>
      <Etape num={4} titre="Suivre le paiement">
        Mettre à jour le statut : <em>Non payée</em> → <em>Partiellement payée</em> → <em>Soldée</em>.
      </Etape>
    </Bloc>
    <Note>
      Délais de paiement indicatifs selon les modalités A2C : CE → 2 à 3 semaines après envoi. CHSCT → 2 mois maximum.
    </Note>
  </>
)

const SECTION_PRESTATAIRE: React.ReactNode = (
  <>
    <Bloc titre="Votre espace Mes missions">
      <p>Depuis la sidebar, <strong>Mes missions</strong> affiche tous les dossiers qui vous ont été affectés.</p>
      <p>Pour chaque dossier vous voyez : la référence, le type, le délai de rendu, et votre statut d'affectation.</p>
    </Bloc>

    <Bloc titre="Déclarer une livraison">
      <Etape num={1} titre="Terminer votre travail et déposer le fichier sur OneDrive">
        Le fichier doit être déposé dans le dossier partagé avant de déclarer la livraison.
      </Etape>
      <Etape num={2} titre="Cliquer sur Déclarer livraison">
        Dans votre liste de missions, bouton <em>Déclarer livraison</em> sur le dossier concerné.
      </Etape>
      <Etape num={3} titre="Attendre la validation par la coordinatrice">
        La coordinatrice fait avancer le dossier. Vous recevrez votre paiement une fois validé.
      </Etape>
    </Bloc>

    <Bloc titre="Confidentialité">
      <p>En tant que prestataire, vous vous engagez à respecter la confidentialité de tout ce qui est dit dans les réunions retranscrites.</p>
      <p>Vous n'avez accès qu'aux fichiers nécessaires à votre mission (audio brut, retranscription) — les informations financières et les notes internes vous sont invisibles.</p>
    </Bloc>

    <Attention>
      Votre compte de connexion doit avoir le même email que votre fiche prestataire pour accéder à vos missions. Si vous ne voyez pas vos dossiers, contactez l'administratrice.
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
    <Bloc titre="Gérer les comptes utilisateurs">
      <p><em>Administration → Utilisateurs</em> : vous pouvez créer des comptes pour chaque membre de l'équipe.</p>
      <p><strong>Rôles disponibles :</strong></p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>Administratrice</strong> : accès complet à tout</li>
        <li><strong>Coordinatrice</strong> : gestion des dossiers, affectations, calculs</li>
        <li><strong>Retranscripteur / Correcteur</strong> : accès à leurs dossiers uniquement via "Mes missions"</li>
        <li><strong>Comptabilité</strong> : accès aux factures et paiements</li>
        <li><strong>Lecture seule</strong> : consultation uniquement</li>
      </ul>
      <Attention>
        Pour qu'un retranscripteur ou correcteur voie ses dossiers, son email de connexion doit être identique à celui renseigné dans sa fiche prestataire.
      </Attention>
    </Bloc>

    <Bloc titre="Gérer les grilles tarifaires">
      <p><em>Administration → Grilles tarifaires</em> : les grilles définissent les taux de rémunération des prestataires.</p>
      <p>Les grilles existantes (seed A2C) sont :</p>
      <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
        <li><strong>Tarif client standard</strong> : 5 €/page (taux moyen de référence)</li>
        <li><strong>Tarif retranscripteur</strong> : 0,25 €/page</li>
        <li><strong>Tarif correcteur</strong> : 0,12 €/page</li>
        <li><strong>Majoration urgence</strong> : +30%</li>
      </ul>
      <Note>
        Le montant facturé au client est le <strong>forfait fixe par tranche de pages</strong> (50€ à 500€), pas le taux €/page. Ce forfait est hardcodé selon les modalités A2C et s'affiche automatiquement dans la section Calcul de chaque dossier.
      </Note>
    </Bloc>

    <Bloc titre="Initialiser les grilles tarifaires (première installation)">
      <p>Si les grilles tarifaires sont vides, lancer depuis le serveur :</p>
      <pre style={{ background: 'var(--color-bg-secondary)', padding: '8px 12px', borderRadius: 'var(--radius)', fontSize: 12, overflowX: 'auto' }}>
        python seed_grilles.py
      </pre>
      <p>Ce script est idempotent : il ne recrée pas les grilles si elles existent déjà.</p>
    </Bloc>

    <Bloc titre="Ajouter un prestataire">
      <Etape num={1} titre="Aller dans Prestataires → Nouveau prestataire">
        Renseigner le nom, le rôle (retranscripteur / correcteur / les deux), l'email, et l'IBAN (chiffré).
      </Etape>
      <Etape num={2} titre="Créer le compte utilisateur associé">
        Aller dans <em>Utilisateurs → Nouveau compte</em>. Utiliser <strong>exactement le même email</strong> que dans la fiche prestataire.
      </Etape>
      <Etape num={3} titre="Communiquer les identifiants">
        Transmettre l'email et le mot de passe au prestataire en dehors de l'application (email, SMS).
      </Etape>
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
