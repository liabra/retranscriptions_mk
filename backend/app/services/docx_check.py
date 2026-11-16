"""
Contrôle de conformité des PV (DOCX).

Exigences A2C : police Comic Sans MS, corps du texte en 12 pt.

Le contrôle ne modifie jamais le document. Il produit un rapport :
- `invalide`      : le fichier n'est pas un DOCX exploitable (refusé au dépôt) ;
- `non_conforme`  : police ou taille du corps non conformes (dépôt accepté, alerte) ;
- `avertissements`: points secondaires (titres, en-têtes, éléments embarqués…) ;
- `conforme`.

Sécurité : l'archive est inspectée avant lecture (taille décompressée, nombre d'entrées,
ratio de compression), les macros sont refusées, le XML est analysé sans résolution
d'entités ni accès réseau.
"""
import io
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from lxml import etree

FONT_REQUISE = "Comic Sans MS"
TAILLE_REQUISE_DEMI_POINTS = 24  # 12 pt

MAX_ENTRIES = 3000
MAX_UNCOMPRESSED = 250 * 1024 * 1024
MAX_RATIO = 200
MAX_ANOMALIES = 40

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
EP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
NS = {"w": W, "a": A}

MAIN_CT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
MAIN_CT_DOCM = "application/vnd.ms-word.document.macroEnabled.main+xml"

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False,
                          remove_blank_text=False, load_dtd=False)


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


class DocxInvalide(Exception):
    pass


@dataclass
class RunProps:
    font: Optional[str] = None
    font_theme: Optional[str] = None
    size: Optional[int] = None  # demi-points

    def merge(self, other: "RunProps") -> "RunProps":
        return RunProps(
            font=other.font if (other.font or other.font_theme) else self.font,
            font_theme=other.font_theme if (other.font or other.font_theme) else self.font_theme,
            size=other.size if other.size is not None else self.size,
        )


@dataclass
class Rapport:
    statut: str = "conforme"
    resume: str = ""
    caracteres_total: int = 0
    caracteres_conformes: int = 0
    polices: Dict[str, int] = field(default_factory=dict)
    tailles: Dict[str, int] = field(default_factory=dict)
    anomalies: List[dict] = field(default_factory=list)
    avertissements: List[str] = field(default_factory=list)
    pages_declarees: Optional[int] = None
    mots: int = 0
    paragraphes: int = 0

    def to_dict(self) -> dict:
        taux = round(100 * self.caracteres_conformes / self.caracteres_total, 1) if self.caracteres_total else 0
        return {
            "statut": self.statut, "resume": self.resume,
            "exigences": {"police": FONT_REQUISE, "taille_pt": TAILLE_REQUISE_DEMI_POINTS / 2},
            "caracteres_total": self.caracteres_total, "taux_conformite": taux,
            "polices": self.polices, "tailles": self.tailles,
            "anomalies": self.anomalies, "avertissements": self.avertissements,
            "pages_declarees": self.pages_declarees, "mots": self.mots, "paragraphes": self.paragraphes,
        }


# ── Lecture sûre de l'archive ────────────────────────────────────────────────

def _open_zip(content: bytes) -> zipfile.ZipFile:
    if not content.startswith(b"PK\x03\x04"):
        raise DocxInvalide("Le fichier n'est pas un document Word .docx (signature invalide)")
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise DocxInvalide("Archive DOCX corrompue")
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise DocxInvalide("Archive DOCX anormale (trop d'éléments)")
    total = sum(i.file_size for i in infos)
    if total > MAX_UNCOMPRESSED:
        raise DocxInvalide("Archive DOCX anormale (taille décompressée excessive)")
    for i in infos:
        if i.compress_size and i.file_size / max(i.compress_size, 1) > MAX_RATIO and i.file_size > 10 * 1024 * 1024:
            raise DocxInvalide("Archive DOCX anormale (compression suspecte)")
        if i.filename.startswith("/") or ".." in i.filename.split("/"):
            raise DocxInvalide("Archive DOCX anormale (chemin interne invalide)")
    return zf


def _xml(zf: zipfile.ZipFile, name: str) -> Optional[etree._Element]:
    try:
        data = zf.read(name)
    except KeyError:
        return None
    try:
        return etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError:
        raise DocxInvalide(f"Partie XML illisible : {name}")


# ── Résolution des propriétés de caractère ───────────────────────────────────

def _rpr(rpr: Optional[etree._Element]) -> RunProps:
    p = RunProps()
    if rpr is None:
        return p
    fonts = rpr.find("w:rFonts", NS)
    if fonts is not None:
        p.font = fonts.get(_w("ascii")) or fonts.get(_w("hAnsi"))
        if not p.font:
            p.font_theme = fonts.get(_w("asciiTheme")) or fonts.get(_w("hAnsiTheme"))
    sz = rpr.find("w:sz", NS)
    if sz is not None and sz.get(_w("val")):
        try:
            p.size = int(float(sz.get(_w("val"))))
        except ValueError:
            pass
    return p


class Styles:
    def __init__(self, styles_root, theme_root):
        self.by_id: Dict[str, etree._Element] = {}
        self.default_para: Optional[str] = None
        self.defaults = RunProps()
        self.theme: Dict[str, str] = {}
        if theme_root is not None:
            for kind, key in (("minorFont", "minor"), ("majorFont", "major")):
                latin = theme_root.find(f".//a:{kind}/a:latin", NS)
                if latin is not None and latin.get("typeface"):
                    self.theme[key] = latin.get("typeface")
        if styles_root is None:
            return
        dd = styles_root.find("w:docDefaults/w:rPrDefault/w:rPr", NS)
        self.defaults = _rpr(dd)
        for st in styles_root.findall("w:style", NS):
            sid = st.get(_w("styleId"))
            if sid:
                self.by_id[sid] = st
                if st.get(_w("type")) == "paragraph" and st.get(_w("default")) in ("1", "true"):
                    self.default_para = sid

    def chain(self, style_id: Optional[str]) -> RunProps:
        props_chain: List[RunProps] = []
        seen = set()
        while style_id and style_id in self.by_id and style_id not in seen:
            seen.add(style_id)
            st = self.by_id[style_id]
            props_chain.append(_rpr(st.find("w:rPr", NS)))
            based = st.find("w:basedOn", NS)
            style_id = based.get(_w("val")) if based is not None else None
        result = RunProps()
        for p in reversed(props_chain):
            result = result.merge(p)
        return result

    def name(self, style_id: Optional[str]) -> str:
        st = self.by_id.get(style_id or "")
        if st is None:
            return ""
        n = st.find("w:name", NS)
        return (n.get(_w("val")) if n is not None else style_id) or ""

    def resolve_font(self, p: RunProps) -> Optional[str]:
        if p.font:
            return p.font
        if p.font_theme:
            return self.theme.get("major" if "major" in p.font_theme.lower() else "minor")
        return None


def _est_titre(style_name: str) -> bool:
    n = style_name.lower()
    return n.startswith(("heading", "titre", "title", "subtitle", "sous-titre", "toc", "tm "))


def _texte_run(r) -> str:
    return "".join(t.text or "" for t in r.iter(_w("t")))


def _analyser_partie(root, styles: Styles, rapport: Rapport, zone: str, polices: Counter,
                     tailles: Counter) -> Tuple[int, int]:
    """Retourne (caractères corps, caractères corps conformes)."""
    total = ok = 0
    for idx, para in enumerate(root.iter(_w("p")), start=1):
        ppr = para.find("w:pPr", NS)
        pstyle_el = ppr.find("w:pStyle", NS) if ppr is not None else None
        pstyle = pstyle_el.get(_w("val")) if pstyle_el is not None else styles.default_para
        titre = _est_titre(styles.name(pstyle))
        base = styles.defaults.merge(styles.chain(pstyle))
        texte_para = ""
        problemes = set()
        for r in para.iter(_w("r")):
            txt = _texte_run(r)
            if not txt.strip():
                continue
            texte_para += txt
            rpr = r.find("w:rPr", NS)
            rstyle_el = rpr.find("w:rStyle", NS) if rpr is not None else None
            props = base
            if rstyle_el is not None:
                props = props.merge(styles.chain(rstyle_el.get(_w("val"))))
            props = props.merge(_rpr(rpr))
            font = styles.resolve_font(props) or "Police par défaut (non définie)"
            size = props.size if props.size is not None else 20  # défaut OOXML : 10 pt
            n = len(txt)
            polices[font] += n
            tailles[f"{size / 2:g} pt"] += n
            font_ok = font.strip().lower() == FONT_REQUISE.lower()
            size_ok = size == TAILLE_REQUISE_DEMI_POINTS
            if zone == "corps" and not titre:
                total += n
                if font_ok and size_ok:
                    ok += n
                if not font_ok:
                    problemes.add(f"police « {font} »")
                if not size_ok:
                    problemes.add(f"taille {size / 2:g} pt")
            elif not font_ok:
                problemes.add(f"police « {font} »")
        if texte_para.strip():
            if zone == "corps":
                rapport.paragraphes += 1
                rapport.mots += len(texte_para.split())
        if problemes and len(rapport.anomalies) < MAX_ANOMALIES:
            rapport.anomalies.append({
                "zone": zone if not titre else f"{zone} (titre)",
                "paragraphe": idx,
                "extrait": texte_para.strip()[:80],
                "problemes": sorted(problemes),
                "bloquant": zone == "corps" and not titre,
            })
    return total, ok


def controler_docx(content: bytes, filename: str = "") -> Rapport:
    """Lève DocxInvalide si le fichier n'est pas un DOCX exploitable."""
    if filename and not filename.lower().endswith(".docx"):
        raise DocxInvalide("Seul le format .docx est accepté")
    zf = _open_zip(content)
    names = set(zf.namelist())
    ct = _xml(zf, "[Content_Types].xml")
    if ct is None or "word/document.xml" not in names:
        raise DocxInvalide("Structure Word absente (ce n'est pas un document .docx)")
    main_ct = None
    for o in ct.findall(f"{{{CT}}}Override"):
        if o.get("PartName") == "/word/document.xml":
            main_ct = o.get("ContentType")
    if main_ct == MAIN_CT_DOCM or any(n.lower().endswith("vbaproject.bin") for n in names):
        raise DocxInvalide("Document contenant des macros refusé (.docm)")
    if main_ct != MAIN_CT_DOCX:
        raise DocxInvalide("Type de document Word non reconnu (modèle ou format non .docx)")

    # Ouverture réelle par python-docx (même moteur de lecture que Word côté OOXML)
    try:
        import docx  # python-docx
        docx.Document(io.BytesIO(content))
    except Exception:
        raise DocxInvalide("Le document Word ne peut pas être ouvert (fichier endommagé)")

    rapport = Rapport()
    document = _xml(zf, "word/document.xml")
    styles = Styles(_xml(zf, "word/styles.xml"), _xml(zf, "word/theme/theme1.xml"))
    body = document.find("w:body", NS)
    if body is None:
        raise DocxInvalide("Corps du document absent")

    polices: Counter = Counter()
    tailles: Counter = Counter()
    total, ok = _analyser_partie(body, styles, rapport, "corps", polices, tailles)
    rapport.caracteres_total, rapport.caracteres_conformes = total, ok

    for name in sorted(names):
        if name.startswith("word/header") or name.startswith("word/footer"):
            part = _xml(zf, name)
            if part is not None:
                zone = "en-tête" if "header" in name else "pied de page"
                _analyser_partie(part, styles, rapport, zone, Counter(), Counter())

    rapport.polices = dict(polices.most_common(10))
    rapport.tailles = dict(tailles.most_common(10))

    # Éléments embarqués et relations externes (signalés, jamais modifiés)
    if any(n.startswith("word/embeddings/") for n in names):
        rapport.avertissements.append("Le document contient des objets embarqués (OLE)")
    rels = _xml(zf, "word/_rels/document.xml.rels")
    if rels is not None:
        for rel in rels.findall(f"{{{REL}}}Relationship"):
            if rel.get("TargetMode") == "External" and not rel.get("Type", "").endswith("/hyperlink"):
                rapport.avertissements.append("Le document référence une ressource externe")
                break
    if body.find(".//w:ins", NS) is not None or body.find(".//w:del", NS) is not None:
        rapport.avertissements.append("Le document contient des modifications suivies non acceptées")
    if body.find(".//w:commentReference", NS) is not None:
        rapport.avertissements.append("Le document contient des commentaires")

    app = _xml(zf, "docProps/app.xml")
    if app is not None:
        pages = app.find(f"{{{EP}}}Pages")
        if pages is not None and (pages.text or "").strip().isdigit():
            rapport.pages_declarees = int(pages.text.strip())

    # Verdict
    if total == 0:
        rapport.statut = "non_conforme"
        rapport.resume = "Aucun texte détecté dans le corps du document"
        rapport.anomalies.insert(0, {"zone": "corps", "paragraphe": 0, "extrait": "",
                                     "problemes": ["document vide"], "bloquant": True})
    elif ok < total:
        rapport.statut = "non_conforme"
        pct = round(100 * (total - ok) / total, 1)
        pct_fr = f"{pct:g}".replace(".", ",")
        rapport.resume = (f"{pct_fr} % du texte ne respecte pas « {FONT_REQUISE} 12 pt » "
                          f"({len([a for a in rapport.anomalies if a['bloquant']])} paragraphe(s) signalé(s))")
    elif rapport.anomalies or rapport.avertissements:
        rapport.statut = "avertissements"
        rapport.resume = "Corps du texte conforme ; points secondaires à vérifier"
    else:
        rapport.statut = "conforme"
        rapport.resume = f"Document conforme ({FONT_REQUISE}, 12 pt)"
    return rapport


def extraire_paragraphes(content: bytes) -> List[str]:
    """Texte brut par paragraphe (comparaison de versions). Le fichier doit avoir été contrôlé."""
    zf = _open_zip(content)
    document = _xml(zf, "word/document.xml")
    if document is None:
        return []
    out = []
    for para in document.iter(_w("p")):
        txt = "".join(_texte_run(r) for r in para.iter(_w("r")))
        if txt.strip():
            out.append(txt.strip())
    return out
