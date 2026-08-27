"""Le meter doit préférer le compte réel du fournisseur à son estimation.

Le défaut réparé ici est unilatéral : sous-estimer la taille du contexte fait
refuser le fournisseur et tomber la session au budget de repli. Les tests
vérifient donc autant la justesse que le sens dans lequel on se trompe.
"""

from __future__ import annotations

from app.services import token_meter
from app.services.token_meter import TokenMeter


def _message(taille: int = 100, role: str = "user") -> dict[str, object]:
    return {"role": role, "content": "a" * taille}


class TestEstimation:
    def test_les_arguments_d_outil_comptent(self):
        nu = {"role": "assistant", "content": None}
        charge = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "add_source", "arguments": "x" * 4_000},
                }
            ],
        }
        assert token_meter.estimer([charge]) > token_meter.estimer([nu]) + 900

    def test_un_message_non_serialisable_ne_leve_pas(self):
        class Opaque:
            pass

        assert token_meter.estimer_message({"role": "user", "content": Opaque()}) > 0

    def test_l_estimation_est_plus_haute_que_l_ancien_quart(self):
        # L'ancien ``len//4`` sous-comptait le français accentué, ce qui est le
        # sens coûteux de l'erreur. Le nouveau ratio doit compter plus haut.
        messages = [_message(1_000)]
        assert token_meter.estimer(messages) > 1_000 // 4 + 8


class TestAncre:
    def test_sans_ancre_le_meter_vaut_l_estimation(self):
        messages = [_message() for _ in range(5)]
        assert TokenMeter().mesurer(messages) == token_meter.estimer(messages)

    def test_l_ancre_remplace_l_estimation_du_prefixe(self):
        prefixe = [_message() for _ in range(3)]
        meter = TokenMeter()
        meter.ancrer(prefixe, 5_000)
        # 5 000 tokens réels pour trois messages courts : c'est le schéma des
        # outils, qui part à chaque appel et que l'estimation ignore.
        assert meter.mesurer(prefixe) == 5_000
        assert meter.mesurer(prefixe) > token_meter.estimer(prefixe)

    def test_le_suffixe_ajoute_s_estime(self):
        prefixe = [_message() for _ in range(3)]
        meter = TokenMeter()
        meter.ancrer(prefixe, 5_000)
        suite = [*prefixe, _message(4_000)]
        assert meter.mesurer(suite) > meter.mesurer(prefixe)

    def test_un_usage_absent_ou_nul_n_ancre_rien(self):
        meter = TokenMeter()
        meter.ancrer([_message()], 0)
        assert meter.ancre is None
        meter.ancrer([], 5_000)
        assert meter.ancre is None

    def test_oublier_rend_le_meter_a_l_estimation(self):
        messages = [_message() for _ in range(3)]
        meter = TokenMeter()
        meter.ancrer(messages, 5_000)
        meter.oublier()
        assert meter.mesurer(messages) == token_meter.estimer(messages)

    def test_une_liste_plus_courte_que_l_ancre_retombe_sur_l_estimation(self):
        # C'est l'état d'après compaction : le préfixe mesuré n'existe plus.
        messages = [_message() for _ in range(10)]
        meter = TokenMeter()
        meter.ancrer(messages, 5_000)
        coupe = messages[:2]
        assert meter.mesurer(coupe) < 5_000


class TestFacteur:
    def test_sans_ancre_le_facteur_est_neutre(self):
        assert TokenMeter().facteur == 1.0

    def test_un_fournisseur_qui_compte_bas_ne_baisse_pas_l_estimation(self):
        # Une ancre sous l'estimation ne doit pas rendre le budget optimiste :
        # l'estimation est déjà volontairement haute.
        messages = [_message(10_000)]
        meter = TokenMeter()
        meter.ancrer(messages, 1)
        assert meter.facteur == 1.0

    def test_le_facteur_est_plafonne(self):
        messages = [_message(10)]
        meter = TokenMeter()
        meter.ancrer(messages, 1_000_000)
        assert meter.facteur == token_meter.FACTEUR_MAX
