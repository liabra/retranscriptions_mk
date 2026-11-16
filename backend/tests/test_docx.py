import io
import zipfile

import pytest

from app.services.docx_check import controler_docx, DocxInvalide, extraire_paragraphes
from tests.conftest import make_docx


def _rezip(content: bytes, modify) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(content))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            data = modify(item.filename, src.read(item.filename))
            if data is not None:
                z.writestr(item, data)
    return out.getvalue()


def test_conforme_via_style():
    r = controler_docx(make_docx(), "pv.docx")
    assert r.statut == "conforme", r.to_dict()
    assert r.to_dict()["taux_conformite"] == 100
    assert r.paragraphes == 3


def test_conforme_via_mise_en_forme_directe():
    assert controler_docx(make_docx(style_level=False), "pv.docx").statut == "conforme"


def test_police_non_conforme():
    r = controler_docx(make_docx(font="Arial"), "pv.docx")
    assert r.statut == "non_conforme"
    assert "Arial" in r.polices
    assert any("police « Arial »" in p for a in r.anomalies for p in a["problemes"])


def test_taille_non_conforme():
    r = controler_docx(make_docx(size=11), "pv.docx")
    assert r.statut == "non_conforme"
    assert "11 pt" in r.tailles


def test_melange_partiel_localise():
    import docx
    from docx.shared import Pt
    d = docx.Document()
    d.styles["Normal"].font.name = "Comic Sans MS"
    d.styles["Normal"].font.size = Pt(12)
    d.add_paragraph("Texte conforme.")
    d.add_paragraph().add_run("Texte en Calibri.").font.name = "Calibri"
    buf = io.BytesIO()
    d.save(buf)
    r = controler_docx(buf.getvalue(), "pv.docx")
    assert r.statut == "non_conforme"
    assert r.anomalies[0]["paragraphe"] == 2 and r.anomalies[0]["extrait"] == "Texte en Calibri."
    assert 0 < r.to_dict()["taux_conformite"] < 100


def test_titre_tolere_en_taille():
    import docx
    from docx.shared import Pt
    d = docx.Document()
    for name in ("Normal", "Heading 1"):
        d.styles[name].font.name = "Comic Sans MS"
    d.styles["Normal"].font.size = Pt(12)
    d.add_heading("PROCÈS-VERBAL", level=1)
    d.add_paragraph("Corps du texte.")
    buf = io.BytesIO()
    d.save(buf)
    assert controler_docx(buf.getvalue(), "pv.docx").statut in ("conforme", "avertissements")


def test_document_vide():
    import docx
    buf = io.BytesIO()
    docx.Document().save(buf)
    r = controler_docx(buf.getvalue(), "pv.docx")
    assert r.statut == "non_conforme" and "Aucun texte" in r.resume


@pytest.mark.parametrize("content", [b"", b"texte simple renomme en docx", b"%PDF-1.7 ...", b"PK\x03\x04garbage"])
def test_faux_docx_refuse(content):
    with pytest.raises(DocxInvalide):
        controler_docx(content, "pv.docx")


def test_extension_doc_refusee():
    with pytest.raises(DocxInvalide):
        controler_docx(make_docx(), "pv.doc")


def test_macro_refusee():
    content = _rezip(make_docx(), lambda n, d: d)
    buf = io.BytesIO(content)
    with zipfile.ZipFile(buf, "a") as z:
        z.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(DocxInvalide, match="macros"):
        controler_docx(buf.getvalue(), "pv.docx")


def test_structure_word_absente():
    content = _rezip(make_docx(), lambda n, d: None if n == "word/document.xml" else d)
    with pytest.raises(DocxInvalide):
        controler_docx(content, "pv.docx")


def test_entite_xml_externe_non_resolue():
    """XXE : une entité externe ne doit jamais être résolue."""
    def inject(name, data):
        if name == "word/document.xml":
            return data.replace(b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>",
                                b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>', 1)
        return data
    content = _rezip(make_docx(), inject)
    try:
        r = controler_docx(content, "pv.docx")
        assert "root:" not in str(r.to_dict())
    except DocxInvalide:
        pass


def test_extraction_paragraphes():
    assert len(extraire_paragraphes(make_docx(paragraphs=5))) == 5
