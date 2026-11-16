import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, require_permission
from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum, CibleGrilleEnum
from app.models.pricing.regle import RegleTarifaire, TypeRegleEnum, ConditionTypeEnum, ModeCalculEnum
from app.models.user import User
from app.models.journal import TypeActionEnum
from app.schemas.grille import (
    GrilleCreate, GrilleUpdate, GrilleOut, GrilleWithReglesOut,
    RegleCreate, RegleUpdate, RegleOut,
)
from app.services.journal import log_action

router = APIRouter()


def _grille_utilisee(db, grille_id) -> bool:
    """Vrai si la version a servi à un calcul (ses règles sont alors figées)."""
    from app.services.tarifs import grille_utilisee
    return grille_utilisee(db, grille_id)


def _proteger(db, grille_id) -> None:
    if _grille_utilisee(db, grille_id):
        raise HTTPException(
            status_code=409,
            detail="Cette grille a déjà servi à des calculs : créez une nouvelle version plutôt que de la modifier",
        )


def _get_grille_or_404(grille_id: uuid.UUID, db) -> GrilleTarifaire:
    g = db.query(GrilleTarifaire).filter(GrilleTarifaire.id == grille_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    return g


@router.get("/grilles", response_model=List[GrilleOut])
def list_grilles(
    db: DbDep,
    current_user: User = Depends(require_permission("tarifs.gerer", "finance.voir")),
    actif_only: bool = False,
):
    q = db.query(GrilleTarifaire)
    if actif_only:
        q = q.filter(GrilleTarifaire.active == True)  # noqa: E712
    return q.order_by(GrilleTarifaire.type, GrilleTarifaire.nom).all()


@router.post("/grilles", response_model=GrilleOut, status_code=201)
def create_grille(
    payload: GrilleCreate,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    try:
        type_grille = TypeGrilleEnum(payload.type)
        cible_grille = CibleGrilleEnum(payload.cible)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    grille = GrilleTarifaire(
        nom=payload.nom,
        type=type_grille,
        cible=cible_grille,
        cible_id=payload.cible_id,
        version=payload.version,
        date_debut=payload.date_debut,
        date_fin=payload.date_fin,
        description=payload.description,
        creee_par_id=admin.id,
        active=True,
    )
    db.add(grille)
    db.flush()
    grille.famille_id = grille.id
    log_action(
        db, TypeActionEnum.CONFIG_GRILLE,
        utilisateur_id=admin.id,
        detail={"action": "creation_grille", "nom": payload.nom, "type": payload.type},
    )
    db.commit()
    db.refresh(grille)
    return grille


@router.get("/grilles/{grille_id}", response_model=GrilleWithReglesOut)
def get_grille(grille_id: uuid.UUID, db: DbDep, current_user: User = Depends(require_permission("tarifs.gerer", "finance.voir"))):
    grille = _get_grille_or_404(grille_id, db)
    regles = (
        db.query(RegleTarifaire)
        .filter(RegleTarifaire.grille_id == grille_id)
        .order_by(RegleTarifaire.priorite)
        .all()
    )
    result = GrilleWithReglesOut.model_validate(grille)
    result.regles = [RegleOut.model_validate(r) for r in regles]
    return result


@router.patch("/grilles/{grille_id}", response_model=GrilleOut)
def update_grille(
    grille_id: uuid.UUID,
    payload: GrilleUpdate,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    grille = _get_grille_or_404(grille_id, db)
    sensibles = set(payload.model_dump(exclude_unset=True)) - {"active", "date_fin", "description", "nom"}
    if payload.date_fin is not None and payload.date_fin < date.today():
        sensibles.add("date_fin")  # fix : pas de clôture rétroactive d'une grille déjà utilisée
    if sensibles:
        _proteger(db, grille_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(grille, field, value)
    log_action(
        db, TypeActionEnum.CONFIG_GRILLE,
        utilisateur_id=admin.id,
        detail={
            "action": "modif_grille",
            "grille_id": str(grille_id),
            "changements": payload.model_dump(exclude_unset=True, mode="json"),
        },
    )
    db.commit()
    db.refresh(grille)
    return grille


@router.delete("/grilles/{grille_id}", status_code=204)
def deactivate_grille(
    grille_id: uuid.UUID,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    grille = _get_grille_or_404(grille_id, db)
    grille.active = False
    log_action(
        db, TypeActionEnum.CONFIG_GRILLE,
        utilisateur_id=admin.id,
        detail={"action": "desactivation_grille", "grille_id": str(grille_id)},
    )
    db.commit()


@router.get("/grilles/{grille_id}/regles", response_model=List[RegleOut])
def list_regles(grille_id: uuid.UUID, db: DbDep, current_user: User = Depends(require_permission("tarifs.gerer", "finance.voir"))):
    _get_grille_or_404(grille_id, db)
    return (
        db.query(RegleTarifaire)
        .filter(RegleTarifaire.grille_id == grille_id)
        .order_by(RegleTarifaire.priorite)
        .all()
    )


@router.post("/grilles/{grille_id}/regles", response_model=RegleOut, status_code=201)
def create_regle(
    grille_id: uuid.UUID,
    payload: RegleCreate,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    _get_grille_or_404(grille_id, db)
    _proteger(db, grille_id)
    try:
        type_r = TypeRegleEnum(payload.type_regle)
        cond_t = ConditionTypeEnum(payload.condition_type)
        mode_c = ModeCalculEnum(payload.mode_calcul)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    regle = RegleTarifaire(
        grille_id=grille_id,
        libelle=payload.libelle,
        type_regle=type_r,
        condition_type=cond_t,
        condition_valeur=payload.condition_valeur,
        mode_calcul=mode_c,
        valeur=payload.valeur,
        unite=payload.unite,
        priorite=payload.priorite,
        cumulable=payload.cumulable,
        plafond_montant=payload.plafond_montant,
        actif=payload.actif,
    )
    db.add(regle)
    db.flush()
    log_action(
        db, TypeActionEnum.CONFIG_GRILLE,
        utilisateur_id=admin.id,
        detail={"action": "creation_regle", "grille_id": str(grille_id), "libelle": payload.libelle},
    )
    db.commit()
    db.refresh(regle)
    return regle


@router.patch("/regles/{regle_id}", response_model=RegleOut)
def update_regle(
    regle_id: uuid.UUID,
    payload: RegleUpdate,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    regle = db.query(RegleTarifaire).filter(RegleTarifaire.id == regle_id).first()
    if not regle:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    _proteger(db, regle.grille_id)
    changes = payload.model_dump(exclude_unset=True)
    if "type_regle" in changes:
        changes["type_regle"] = TypeRegleEnum(changes["type_regle"])
    if "condition_type" in changes:
        changes["condition_type"] = ConditionTypeEnum(changes["condition_type"])
    if "mode_calcul" in changes:
        changes["mode_calcul"] = ModeCalculEnum(changes["mode_calcul"])
    for field, value in changes.items():
        setattr(regle, field, value)
    log_action(
        db, TypeActionEnum.CONFIG_GRILLE,
        utilisateur_id=admin.id,
        detail={
            "action": "modif_regle",
            "regle_id": str(regle_id),
            "changements": payload.model_dump(exclude_unset=True, mode="json"),
        },
    )
    db.commit()
    db.refresh(regle)
    return regle


@router.delete("/regles/{regle_id}", status_code=204)
def delete_regle(
    regle_id: uuid.UUID,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    regle = db.query(RegleTarifaire).filter(RegleTarifaire.id == regle_id).first()
    if not regle:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    _proteger(db, regle.grille_id)
    regle.actif = False
    log_action(
        db, TypeActionEnum.CONFIG_GRILLE,
        utilisateur_id=admin.id,
        detail={"action": "desactivation_regle", "regle_id": str(regle_id)},
    )
    db.commit()


@router.post("/grilles/{grille_id}/nouvelle-version", response_model=GrilleOut, status_code=201)
def nouvelle_version(
    grille_id: uuid.UUID,
    db: DbDep,
    admin: User = Depends(require_permission("tarifs.gerer")),
):
    """Duplique la grille et ses règles actives en brouillon ; l'ancienne version reste intacte."""
    from app.services.tarifs import nouvelle_version as _nv
    source = _get_grille_or_404(grille_id, db)
    copie = _nv(db, source, admin.id)
    log_action(db, TypeActionEnum.CONFIG_GRILLE, utilisateur_id=admin.id,
               detail={"action": "nouvelle_version_grille", "source": str(source.id), "copie": str(copie.id),
                       "version": copie.version})
    db.commit()
    db.refresh(copie)
    return copie
