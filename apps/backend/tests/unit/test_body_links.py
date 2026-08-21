"""Tests du repli « liens cites dans le corps ».

Mesure du 2026-08-07 : sur un article ProPublica et un essai Gwern, le
pipeline rendait zero source. Ces deux pages n'ont pas de section
References — leur bibliographie est faite de liens poses dans le texte.
Sans ce repli, un journaliste et un essayiste voient un ecran vide.
"""

from __future__ import annotations

from app.extractors.body_links import _INTERNAL_LINKS_MAX, extract_body_links

PAGE = """
<html><body>
  <nav><a href="https://example.org/nav">Accueil</a></nav>
  <header><a href="https://example.org/logo">Logo</a></header>
  <main>
    <p>Le fisc a perdu
      <a href="https://www.treasury.gov/tigta/press/press_tigta-2017-27.htm">au moins 3 milliards</a>,
      d'apres <a href="https://www.documentcloud.org/documents/5219189-noncompliance">une etude</a>.
    </p>
    <p>Voir aussi <a href="/interne/autre-article">notre enquete</a> et
      <a href="https://www.propublica.org/article/autre">celle-ci</a>.</p>
    <p><a href="https://twitter.com/intent/tweet?url=x">Partager sur Twitter</a>
       <a href="https://www.linkedin.com/shareArticle?url=x">Partager</a>
       <a href="https://www.facebook.com/sharer/sharer.php?u=x">Partager</a></p>
    <p>Il l'a dit dans <a href="https://x.com/unauteur/status/12345">ce message</a>.</p>
    <p><a href="https://ads.example.net/promo">   </a></p>
  </main>
  <footer><a href="https://example.org/mentions">Mentions</a></footer>
</body></html>
"""


def test_garde_les_liens_externes_du_corps():
    refs = extract_body_links(PAGE, "https://www.propublica.org/article/how-the-irs-was-gutted")
    urls = {r.url for r in refs}
    assert "https://www.treasury.gov/tigta/press/press_tigta-2017-27.htm" in urls
    assert "https://www.documentcloud.org/documents/5219189-noncompliance" in urls


def test_le_texte_du_lien_est_du_contexte_pas_un_titre():
    """« au moins 3 milliards » ne nomme pas le rapport vise. Renseigner `title`
    avec ce texte bloquerait le backfill, qui ne visite que les refs sans titre :
    la fiche afficherait alors les mots du lien au lieu du titre du document."""
    refs = extract_body_links(PAGE, "https://www.propublica.org/article/how-the-irs-was-gutted")
    par_url = {r.url: r for r in refs}
    ref = par_url["https://www.documentcloud.org/documents/5219189-noncompliance"]
    assert ref.title is None
    assert ref.raw_text == "une etude"


def test_ecarte_la_navigation_et_le_pied_de_page():
    """Un lien de menu n'est pas une source citee, meme s'il est externe."""
    refs = extract_body_links(PAGE, "https://www.propublica.org/article/how-the-irs-was-gutted")
    urls = {r.url for r in refs}
    assert "https://example.org/nav" not in urls
    assert "https://example.org/logo" not in urls
    assert "https://example.org/mentions" not in urls


def test_ecarte_les_boutons_de_partage_mais_garde_un_message_cite():
    """Les URLs de partage sont des actions, pas des citations. Un lien vers un
    message precis reste une source legitime : on filtre le chemin, pas le
    domaine, sinon on perdrait toute citation de reseau social."""
    refs = extract_body_links(PAGE, "https://www.propublica.org/article/how-the-irs-was-gutted")
    urls = {r.url for r in refs}
    assert not any("intent/tweet" in u for u in urls)
    assert not any("shareArticle" in u for u in urls)
    assert not any("sharer.php" in u for u in urls)
    assert "https://x.com/unauteur/status/12345" in urls


def test_ecarte_un_renvoi_interne_pose_hors_phrase():
    """« notre enquete », dans un paragraphe trop court pour etre du texte
    courant, est un renvoi editorial et non une citation."""
    refs = extract_body_links(PAGE, "https://www.propublica.org/article/how-the-irs-was-gutted")
    urls = {r.url for r in refs}
    assert "https://www.propublica.org/article/autre" not in urls


PAGE_INSTITUTION = """
<html><body><main>
  <p>L'organisation publie un
    <a href="/publications/i/item/9789240031029">plan d'action 2013-2030</a>
    qui detaille les etapes necessaires pour offrir des interventions adaptees
    aux personnes souffrant de troubles mentaux, dont la depression.</p>
  <p>Le <a href="/publications/i/item/WHO-MSD-MER-18.5">manuel Problem Management Plus</a>
    est l'un des outils diffuses dans ce cadre, aux cotes de plusieurs autres
    guides destines aux personnels non specialises et largement traduits.</p>
</main></body></html>
"""


def test_garde_un_document_de_la_meme_institution_cite_dans_une_phrase():
    """Mesure du 2026-08-07 sur la fiche depression de l'OMS : elle citait cinq
    publications de l'OMS, toutes ecartees comme « liens internes ». Une
    institution qui renvoie a ses propres rapports cite bel et bien ses
    sources ; l'ecran n'en montrait qu'une, externe."""
    refs = extract_body_links(PAGE_INSTITUTION, "https://www.who.int/news-room/fact-sheets/x")
    urls = {r.url for r in refs}
    assert "https://www.who.int/publications/i/item/9789240031029" in urls
    assert "https://www.who.int/publications/i/item/WHO-MSD-MER-18.5" in urls


def test_renonce_aux_liens_internes_quand_le_site_en_fait_un_dispositif():
    """Mesure du 2026-08-07 : l'essai Gwern porte 238 liens internes poses dans
    ses phrases — c'est son systeme de renvois, pas une bibliographie. Les
    reprendre ferait passer la fiche de 78 a 316 sources. Au-dela du plafond on
    n'en garde aucun, plutot que d'en trier arbitrairement."""
    phrase = "Un paragraphe assez long pour ressembler a du texte courant reel. "
    corps = "".join(
        f"<p>{phrase}<a href='/note-{i}'>note {i}</a> {phrase}</p>"
        for i in range(_INTERNAL_LINKS_MAX + 1)
    )
    refs = extract_body_links(
        f"<html><body><main>{corps}</main></body></html>", "https://blog.ex/a"
    )
    assert refs == []


def test_ecarte_les_liens_sans_texte():
    """Une ancre vide donne une source sans titre ni contexte : inutilisable."""
    refs = extract_body_links(PAGE, "https://www.propublica.org/article/how-the-irs-was-gutted")
    assert not any("ads.example.net" in r.url for r in refs)


def test_dedoublonne_les_repetitions():
    html = """
    <html><body><main>
      <p><a href="https://ex.org/a">Premier appel</a></p>
      <p><a href="https://ex.org/a">Second appel</a></p>
    </main></body></html>
    """
    refs = extract_body_links(html, "https://site.example/x")
    assert len([r for r in refs if r.url == "https://ex.org/a"]) == 1


def test_page_sans_corps_exploitable():
    assert extract_body_links("<html></html>", "https://site.example/x") == []
