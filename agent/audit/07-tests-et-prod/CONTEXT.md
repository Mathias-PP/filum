# 07 — Tests, scripts, workspace seed, workspaces ICM

> Fiches du lot 7 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G7** (`check_lot.sh 7`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt).

## Rôle du domaine

La couche de validation et d'outillage : 23 fichiers de tests (12 unitaires + 7 intégration + 4 MCP), 2 scripts utilitaires (seed workspace, export OpenAPI), le template du workspace ICM (27 fichiers : agents YAML, shared docs, stages, templates, audit_fiche.py), et le workspace ICM de production (51 fichiers, miroir du seed + runs d'exemple).

Total : 103 fichiers, ~12 000 LOC, ~500 symboles.

## Les fichiers

| Fiche | Contenu | Fichiers | LOC approx | Fichier |
|---|---|---|---|---|
| [01-scripts.md](01-scripts.md) | build_workspace_seed, export_openapi | 2 | 115 | `apps/backend/app/scripts/` |
| [02-workspace-seed.md](02-workspace-seed.md) | Template ICM : agents YAML, shared, stages, templates, audit | 27 | 1 200 | `apps/backend/app/agent_workspace_seed/` |
| [03-tests-unitaires.md](03-tests-unitaires.md) | Tests unitaires : boucle, providers, sessions, discovery, fiche, workspace, MCP | 14 | 6 400 | `apps/backend/tests/unit/` |
| [04-tests-integration.md](04-tests-integration.md) | Tests intégration API : chat, sessions, providers, gratuit, defs, fiche, workspace | 7 | 1 400 | `apps/backend/tests/integration/` |
| [05-workspaces-icm.md](05-workspaces-icm.md) | Workspace ICM production : miroir seed + runs d'exemple | 51 | 3 000 | `workspaces/createur-de-fiches/` |

## Invariants du lot

- **Seed vs workspace** : `build_workspace_seed.py` (`apps/backend/app/scripts/build_workspace_seed.py:1`) copie `workspaces/createur-de-fiches/` → `agent_workspace_seed/`, en excluant `.gitkeep`, `CLAUDE.md`, `setup/`, `runs/`.
- **audit_fiche.py** : script standalone ( pas de dépendances internes ) — alertes uniquement, jamais de blocage (`apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:1`).
- **Tests MCP** : `test_mcp_tools_write.py` (1 371 LOC, 81 symboles) est le plus gros fichier de test — couvre tous les outils d'écriture MCP.
- **Tests boucle** : `test_agent_loop.py` (1 502 LOC, 14 symboles) couvre la boucle complète : text, tool_call, approval, 429, retry, Gemini, compaction.
- **Tests intégration** : tous les fichiers utilisent `httpx.AsyncClient` + fixtures `db_session`, `test_user`, `session_token`.

## Dettes et pièges constatés à la lecture

- **Duplication seed/workspace** : les 27 fichiers de `agent_workspace_seed/` sont des copies de `workspaces/createur-de-fiches/` — toute modification du workspace doit être suivie d'un `build_workspace_seed.py`.
- **test_agent_loop.py 1 502 LOC** : gros fichier avec 9 classes et 15 définitions top-level — pourrait bénéficier d'une décomposition par domaine (approval, retry, Gemini, compaction).
- **test_mcp_tools_write.py 1 371 LOC** : 81 symboles, tous module-level (pas de classes) — pytest natif, pas de structure de groupe.
- **Workspaces ICM** : les fichiers sous `runs/` sont des données d'exemple (JSON, markdown) — pas de code à vérifier, mais les sha256 doivent correspondre.

## Annexe A — Symboles complets par fichier

### Scripts
`_included`, `main` (build_workspace_seed), `main` (export_openapi)

### audit_fiche.py
`out`, `alert`, `fetch_json`, `crossref_title`, `parse_brief_frontmatter`, `main`, `finish`

### test_agent_loop.py
`_provider`, `_mock_texte`, `_mock_tool_call`, `_collect`, `_registre_fake`, `TestSensibilite`, `test_outils_destructeurs_sensibles`, `test_verify_excerpts_non_sensible`, `test_lecture_non_sensible`, `test_update_card_public_est_sensible`, `test_pas_de_sensible_mort`, `test_tout_outil_irreversible_est_sensible`, `TestRegistre`, `test_registre_contient_les_domaines`, `test_web_search_absent_sans_configuration`, `test_web_search_present_quand_configure`, `test_tous_les_outils_ont_un_schema_valide`, `test_executer_outil_inconnu`, `test_executer_refuse_le_sensible_sans_approbation`, `test_executer_sensible_approuve_atteint_loutil`, `test_executer_exception_devenue_resultat`, `TestBoucle`, `test_reponse_texte_directe`, `test_outil_puis_texte`, `test_reponse_vide_remonte_diagnostic`, `test_reponse_vide_stop_dit_reformuler`, `test_429_avec_retry_delay_attend_et_reprend`, `test_429_sans_retry_delay_rend_message_lisible`, `test_gemini_thought_signature_preserve_vers_gemini`, `test_thought_signature_retiree_vers_provider_strict`, `test_historique_avec_tool_call_orphelin_filtre_avant_envoi`, `test_gemini_streaming_tool_calls_sans_index_ne_fusionnent_pas`, `test_message_tool_porte_tool_call_id`, `test_historique_pollue_gemini_assaini_avant_envoi`, `test_approval_request_contient_resume_lisible`, `test_resume_de_publication_dit_l_etat_reel`, `test_action_sensible_refusee_sans_execution`, `test_action_sensible_approuvee_execute`, `test_borne_max_tours`, `test_erreur_provider_http`, `test_retry_backoff_sur_503`, `test_pas_de_retry_sur_401`, `test_appel_anthropic_va_direct_v1_messages`, `_refuse`, `TestUsagePersistance`, `test_ajouter_message_persiste_usage`, `test_usage_agrege_par_session`, `test_done_event_inclut_usage`, `TestPrimingWorkspace`, `test_vide_si_pas_de_fichiers`, `test_injecte_les_shared`, `test_respecte_la_limite`, `test_boucle_injecte_workspace_dans_systeme`, `TestSystemeAgent`, `test_regles_absolues_dans_systeme`, `test_web_search_non_configure_interdit_fabrication`, `TestAgentNomme`, `_definition`, `_corps_envoye`, `test_seuls_les_outils_de_l_agent_sont_envoyes`, `test_le_prompt_systeme_porte_le_role`, `test_le_contexte_se_limite_aux_fichiers_nommes`, `test_agent_sans_contexte_n_injecte_rien`, `TestCompactionContexte`, `_refus_contexte`, `test_rejeu_unique_apres_un_refus_du_fournisseur`, `test_un_second_refus_remonte_l_erreur`, `test_une_erreur_ordinaire_ne_declenche_rien`, `test_compaction_preventive_avant_le_premier_appel`, `test_la_passe_preventive_ne_consomme_pas_le_rejeu`

### test_agent_providers.py
`TestMasquage`, `test_masque_longue`, `test_masque_courte`, `test_masque_ne_renvoie_jamais_la_cle`, `TestResolutionEndpoint`, `test_racine_nue_prefixe_v1`, `test_chemin_present_suffixe_direct`, `test_slash_final_ignore`, `TestValidationSchema`, `test_custom_sans_base_url_passe_au_schema`, `test_base_url_non_http_refusee`, `test_base_url_sans_hote_refusee`, `test_champ_inconnu_refuse`, `test_api_key_vide_apres_strip_refusee`, `test_base_url_private_ip_valide_au_schema`, `TestResolutionBaseUrl`, `test_defaut_provider_integre`, `test_custom_sans_base_url_refuse`, `test_adresse_privee_refusee`, `test_surcharge_d_un_integre_vers_du_prive_refusee`, `test_custom_valide_resolu`, `_mk_provider`, `TestTester`, `test_cle_valide`, `test_cle_invalide`, `test_quota_epuise`, `test_modele_inconnu`, `test_erreur_reseau`, `test_anthropic_va_direct_en_messages`, `test_provider_d_un_autre_createur_invisible`, `TestServiceCrud`, `test_creer_et_lister_chiffre`, `test_un_seul_defaut`, `test_doublon_refuse`, `TestDetailProvider`, `test_forme_openai`, `test_forme_liste_gemini`, `test_corps_non_json_ne_plante_pas`, `test_corps_vide_rend_none`, `test_forme_mistral_detail`, `test_forme_cerebras_message_racine`, `TestClassifyParCodeErreur`, `test_insufficient_quota_dit_credit_epuise`, `test_rate_limit_exceeded_dit_reessayer`, `test_invalid_api_key_dit_cle_revoquee`, `test_model_not_found`, `test_context_length_exceeded`, `test_code_cerebras_racine`, `test_code_inconnu_retombe_sur_le_status`, `TestClassifyRemonteLeProvider`, `test_le_404_gemini_cite_le_modele_de_remplacement`, `test_le_429_openai_dit_le_credit`, `test_succes_inchange`, `TestListerModeles`, `test_rend_la_liste_du_provider`, `test_replie_sur_la_liste_curee_si_le_provider_refuse`, `test_ne_leve_pas_sur_une_panne_reseau`, `TestCacheModeles`, `test_deuxieme_appel_ne_touche_pas_le_reseau`, `test_refresh_force_le_rafraichissement`, `test_echec_n_est_pas_mis_en_cache`, `test_patch_invalide_le_cache`, `TestTesterRemonteLesModeles`, `test_succes_inclut_les_modeles_du_compte`, `test_echec_ne_lance_pas_l_appel_modeles`, `test_latency_ms_present_sur_succes`, `TestListerModelesMetadonnees`, `test_openrouter_garde_context_et_prix`, `test_ids_nus_restent_liste_str`

### test_agent_sessions.py
`TestTitre`, `TestSessions`, `TestApprobations`, `_systeme`, `_user`, `_paire_outil`, `TestCompaction`

### test_agent_discovery.py
`_settings`, `test_discovery_actif_si_enabled_et_cle`, `test_discovery_inactif_si_disabled`, `test_discovery_inactif_si_cle_vide`, `test_nom_public_deepseek`, `test_nom_public_groq`, `test_nom_public_inconnu_retourne_kind`, `test_provider_decouverte_est_transient`, `session_vide`, `test_quota_disponible_sans_ligne`, `test_quota_diminue_apres_consommation`, `test_quota_bloque_apres_N_messages`, `test_quota_isole_par_creator`, `test_consommer_idempotent_par_appels_successifs`

### test_agent_fiche.py
`_provider`, `_texte`, `_transport_texte`, `_registre_vide`, `_seeder_stages`, `_lancer`, `TestEtapes`, `TestLancer`, `TestEtat`

### test_agent_definitions.py
`test_parser_accepte_une_definition_complete`, `test_parser_dedoublonne_outils_et_contexte`, `test_parser_rejette`, `test_parser_exige_que_le_slug_corresponde_au_fichier`, `test_parser_accepte_les_agents_livres`, `test_lister_marque_les_agents_livres_et_signale_les_rejets`, `test_lister_ignore_les_fichiers_non_yaml`, `test_obtenir_rend_none_sur_slug_absent`, `test_chemin_de`

### test_agent_workspace.py
`test_normaliser_chemin_accepte_relatifs`, `test_normaliser_chemin_backslashes_windows`, `test_normaliser_chemin_nettoie_points_et_slashes`, `test_normaliser_chemin_refuse_remontee_hors_racine`, `test_normaliser_chemin_refuse_absolus`, `test_normaliser_chemin_refuse_racine_inconnue`, `test_sha256_stable`, `test_ecrire_lire_supprimer`, `test_ecrire_upsert_recalcule_sha`, `test_lister_arborescence`, `test_seed_cree_tous_les_fichiers_template`, `test_seed_idempotent_preserve_les_modifs`, `test_ecrire_chemin_invalide_leve_erreur`, `test_seed_insertmany_ne_viole_pas_not_null`, `TestFrontmatterParser`

### test_agent_tools.py
`autre_user`, `_ctx`, `TestIsolationWorkspace`, `TestIsolationFiches`

### test_agent_gratuit.py
`settings_actives`, `lane_zai`, `test_mode_indisponible_par_defaut`, `test_disponible_si_active_avec_cle`, `test_inactive_sans_cle`, `TestConsentement`, `TestChoisirLane`, `TestQuotas`, `TestTesterLane`, `TestModeles`

### test_agent_philum_catalogue.py
`TestCatalogueCompletude`, `TestDescriptions`, `TestSchemaJson`, `TestEnumsDansSchemas`

### test_mcp_auth.py
`_forger_token`, `test_un_token_valide_identifie_l_utilisateur`, `test_un_token_absent_ne_donne_personne`, `test_un_token_expire_ne_donne_personne`, `test_un_token_signe_avec_le_mauvais_secret_ne_donne_personne`, `test_un_sujet_qui_ne_pointe_personne_ne_donne_personne`, `test_un_utilisateur_supprime_n_est_plus_reconnu`, `test_un_token_du_flow_oauth_identifie_l_utilisateur`, `test_utilisateur_courant_hors_contexte_http_renvoie_none`, `test_exiger_utilisateur_leve_une_toolerror_avec_le_chemin_du_token`

### test_mcp_mount.py
`test_mcp_route_is_mounted`, `test_mcp_tools_registered`, `test_mcp_rate_limit_triggers_429`, `_client`, `_token_valide`, `test_porte_compte_repond_401_sans_token`, `test_porte_publique_reste_ouverte_sans_token`, `test_un_token_invalide_vaut_401_meme_sur_la_porte_publique`, `test_un_token_valide_passe_la_porte_compte`, `test_les_deux_documents_well_known_annoncent_leur_propre_ressource`, `test_mcp_rate_limit_ignores_other_paths`

### test_mcp_schema_compat.py
`TestAplatirNullable`, `test_aucun_outil_mcp_ne_publie_any_of`

### test_mcp_tools.py
`published_card`, `test_search_cards_finds_by_title`, `test_search_cards_ignores_drafts`, `test_get_card_returns_compact_sources`, `test_get_card_unknown_returns_none`, `test_get_source_detail`, `test_get_source_of_draft_card_returns_none`, `private_published_card`, `test_search_cards_ignores_private_cards`, `test_get_card_private_returns_none`, `test_get_source_of_private_card_returns_none`, `test_find_cards_citing_ignores_private_cards`, `test_search_cards_escapes_like_wildcards`, `fiche_decrite`, `test_search_cards_cherche_dans_la_description`, `test_search_cards_cherche_l_auteur_du_contenu`, `test_search_cards_cherche_le_nom_affiche_du_createur`, `test_search_cards_cherche_dans_la_bibliographie`, `test_search_cards_cherche_l_auteur_d_une_source`, `test_une_fiche_qui_cite_deux_fois_reste_une_fiche`, `source_complete`, `test_get_source_porte_le_verbatim`, `test_get_source_dit_la_retractation`, `test_get_source_porte_position_doi_et_acces_ouvert`, `test_find_cards_citing_same_url`, `fiche_citant_nature`, `test_find_cards_citing_ignore_l_ecriture_de_l_url`, `test_find_cards_citing_reconnait_le_doi`, `test_find_cards_citing_ne_confond_pas_deux_articles`, `test_find_cards_citing_url_vide_ne_ramene_rien`, `fiche_citant_une_fiche`, `test_get_card_dit_qu_une_source_mene_a_une_fiche`, `test_get_card_ne_ment_pas_sur_une_source_sans_lien`, `test_get_source_dit_la_fiche_qu_elle_mene`, `test_le_lien_ne_revele_pas_une_fiche_non_publique`, `test_le_lien_ne_revele_pas_un_brouillon`, `deux_ecritures_du_meme_travail`, `test_find_cards_citing_suit_le_lien_resolu`, `test_find_cards_citing_ne_rend_pas_la_fiche_citee_elle_meme`, `test_le_lien_resolu_ne_passe_pas_par_une_fiche_privee`

### test_mcp_tools_write.py
`_source_lisible`, `test_creer_une_fiche_donne_un_brouillon`, `test_deux_fiches_avec_le_meme_slug_est_refuse`, `test_un_slug_invalide_leve_un_message_lisible`, `fiche_brouillon`, `test_ajouter_une_source_la_lie_a_la_fiche`, `test_ajouter_deux_fois_la_meme_source_est_refuse`, `test_meme_source_ecrite_differemment_est_refusee`, `test_ajouter_une_source_a_la_fiche_d_autrui_est_refuse`, `test_ajouter_un_extrait_le_marque_comme_ia`, `UUID_from_str`, `test_un_extrait_vide_est_refuse`, `test_extrait_court_referentiel_sans_contexte_est_refuse`, `test_extrait_court_referentiel_avec_contexte_passe`, `test_extrait_long_autonome_passe_sans_contexte`, `test_ajouter_un_extrait_a_une_source_d_autrui_est_refuse`, `test_publier_rend_la_fiche_visible`, `test_publier_la_fiche_d_autrui_est_refuse`, `test_le_parcours_complet_produit_une_fiche_qu_un_agent_peut_relire`, `test_set_content_text_sans_confirmation_est_refuse`, `test_set_content_text_pose_le_texte_sur_la_fiche`, `test_set_content_text_chaine_vide_efface_le_texte`, `test_set_content_text_trop_long_est_refuse`, `test_set_content_text_fiche_d_autrui_est_refuse`, `autre_utilisateur`, `test_update_card_corrige_titre_et_description`, `test_update_card_champ_none_laisse_inchange`, `test_update_card_refuse_non_proprietaire`, `test_update_source_pose_stance_et_annotation`, `test_add_source_pose_published_at`, `test_add_source_deduit_l_url_du_doi`, `test_add_source_url_explicite_prime_sur_le_doi`, `test_add_source_pose_les_extraits_fournis`, `test_add_source_dit_quels_extraits_ont_ete_refuses`, `test_add_source_published_at_formats_souples`, `test_add_source_published_at_illisible_refuse`, `test_update_source_efface_published_at_par_chaine_vide`, `test_update_source_refuse_non_proprietaire`, `test_delete_source_marque_deleted_at`, `test_delete_source_refuse_non_proprietaire`, `test_delete_excerpt_retire_l_extrait`, `test_delete_excerpt_refuse_non_proprietaire`, `test_verify_excerpts_avec_texte_fourni_marque_verified`, `test_verify_excerpts_refuse_non_proprietaire`, `test_list_connections_rend_les_deux_sens`, `test_list_connections_refuse_non_proprietaire`, `test_confirm_connection_refuse_source_sans_lien`, `test_confirm_connection_refuse_source_autre_fiche`, `test_remove_connection_efface_le_lien`, `test_remove_connection_refuse_non_proprietaire`, `test_list_my_cards_rend_les_fiches_du_user`, `test_list_my_cards_isole_par_user`, `test_get_my_card_lit_un_brouillon`, `test_get_my_card_tronque_un_transcript_long`, `test_get_my_card_refuse_non_proprietaire`, `test_list_sources_rend_les_sources_de_la_fiche`, `test_list_sources_refuse_non_proprietaire`, `test_search_my_excerpts_trouve_par_texte`, `test_search_my_excerpts_isole_par_user`, `test_delete_card_puis_restore_est_reversible`, `test_delete_card_refuse_non_proprietaire`, `test_archive_sources_accepte_les_sources_du_user`, `test_archive_sources_refuse_les_sources_d_autrui`, `test_add_sources_batch_pose_plusieurs_sources_en_un_appel`, `test_add_sources_batch_dedup_dans_le_meme_lot`, `test_add_sources_batch_refuse_non_proprietaire`, `test_list_incoming_citations_rend_zero_par_defaut`, `test_mark_citations_seen_pose_un_timestamp`, `test_list_deleted_cards_rend_les_fiches_de_la_corbeille`, `test_parse_biblio_extrait_des_references_d_un_texte`, `test_parse_biblio_texte_vide_rend_liste_vide`, `test_create_claim_request_refuse_fiche_non_seed`, `test_create_content_attestation_refuse_fiche_sans_url`, `test_create_content_attestation_refuse_non_proprietaire`, `test_get_attestation_refuse_id_invalide`, `test_add_source_refuse_une_valeur_hors_vocabulaire`, `test_add_source_message_d_erreur_cite_le_vocabulaire`, `test_add_source_stance_vide_vaut_silence`, `test_update_source_refuse_une_valeur_hors_vocabulaire`, `test_update_source_stance_vide_efface_la_position`, `test_add_sources_batch_rejette_dans_failed_sans_bloquer_le_lot`

### test_workspace_seed_sync.py
`_fichiers_attendus`, `test_le_seed_contient_exactement_les_fichiers_du_workspace`, `test_chaque_fichier_du_seed_est_identique_a_sa_source`

### Tests intégration — symboles par fichier

**test_agent_chat_api.py** : `_reset_limiter`, `client`, `_cle_chiffree`, `_inserer_provider_defaut`, `_lire_evenements`, `_mock_texte`, `_mock_tool_call`, `_post_chat`, `test_chat_requiert_auth`, `test_chat_sans_provider_defaut`, `test_chat_flux_complet`, `test_chat_action_sensible_refusee`, `test_chat_nemprunte_pas_le_provider_dun_autre`

**test_agent_definitions_api.py** : `_reset_limiter`, `client`, `test_requires_auth`, `test_liste_seed_au_premier_acces`, `test_obtenir_un_agent`, `test_agent_inconnu_404`, `test_fichier_casse_apparait_en_rejet`

**test_agent_fiche_api.py** : `_reset_limiter`, `client`, `_refuse`, `_provider_defaut`, `_stages`, `_transport_texte`, `_evenements`, `_corps`, `test_lancement_requiert_auth`, `test_lancement_sans_provider_defaut`, `test_slug_invalide_refuse`, `test_run_complet_trace_les_etages`, `test_regles_absentes_rendent_une_erreur_lisible`, `test_etat_du_run`

**test_agent_mode_gratuit_api.py** : `_reset_limiter`, `settings_actives`, `lane_zai`, `client`, `_lire_evenements`, `test_etat_indisponible_sans_config`, `test_consentement_aller_retour`, `test_testeur_renvoie_ok_ou_echec`, `test_modeles_catalogue_et_bascule_manuelle`, `_mock_reponse_glm`, `test_chat_mode_gratuit_emet_la_banniere`, `test_chat_echec_fournisseur_gratuit_reecrit_lerreur_et_pose_le_cooldown`, `test_chat_sans_consentement_nutilise_pas_la_lane`

**test_agent_providers_api.py** : `_reset_limiter`, `client`, `_cle_chiffree`, `_inserer_provider`, `test_requires_auth`, `test_meta_public`, `test_create_list_masque`, `test_doublon_refuse_400`, `test_extra_forbid_422`, `test_custom_exige_base_url_400`, `test_custom_url_non_http_422`, `test_custom_base_url_privee_400`, `test_un_seul_defaut`, `test_patch_cle_et_defaut`, `test_patch_inconnu_404`, `test_delete`, `test_isolation_entre_createurs`, `test_test_cle_route_ok`, `test_test_cle_route_invalide`, `test_test_cle_inconnu_404`

**test_agent_sessions_api.py** : `_reset_limiter`, `client`, `_autre_createur`, `_inserer_provider_defaut`, `_lire_evenements`, `_mock_texte`, `test_sessions_requiert_auth`, `test_creer_lister_supprimer`, `test_session_dun_autre_createur_est_404`, `test_le_tour_est_persiste_et_repris`, `test_chat_sur_session_inconnue_est_404`, `test_approve_debloque_la_boucle`, `test_approve_dun_autre_createur_est_404`, `test_approve_identifiant_inconnu_est_404`

**test_agent_workspace_api.py** : `_reset_limiter`, `client`, `test_requires_auth`, `test_tree_seed_au_premier_acces`, `test_ecrire_lire_fichier`, `test_ecrire_chemin_invalide_400`, `test_ecrire_extra_forbid_422`, `test_lire_inconnu_404`, `test_supprimer_fichier`, `test_seed_explicite_idempotent`, `test_isolation_entre_createurs`

## Annexe B — Fichiers workspaces/createur-de-fiches/ (non dans le seed)

`workspaces/createur-de-fiches/AGENTS.md`, `workspaces/createur-de-fiches/CLAUDE.md`, `workspaces/createur-de-fiches/CONTEXT.md`, `workspaces/createur-de-fiches/_core/audit/audit_fiche.py`, `workspaces/createur-de-fiches/_core/templates/brief.md`, `workspaces/createur-de-fiches/_core/templates/extrait.md`, `workspaces/createur-de-fiches/_core/templates/source.md`, `workspaces/createur-de-fiches/agents/CONTEXT.md`, `workspaces/createur-de-fiches/agents/assistant.yaml`, `workspaces/createur-de-fiches/agents/bibliographe.yaml`, `workspaces/createur-de-fiches/agents/extracteur.yaml`, `workspaces/createur-de-fiches/agents/publicateur.yaml`, `workspaces/createur-de-fiches/agents/rechercheur.yaml`, `workspaces/createur-de-fiches/agents/redacteur.yaml`, `workspaces/createur-de-fiches/agents/relecteur.yaml`, `workspaces/createur-de-fiches/runs/_example/00-brief.md`, `workspaces/createur-de-fiches/runs/_example/README.md`, `workspaces/createur-de-fiches/shared/garde-fous.md`, `workspaces/createur-de-fiches/shared/philum-mcp.md`, `workspaces/createur-de-fiches/shared/pieges-vecus.md`, `workspaces/createur-de-fiches/shared/principes-editoriaux.md`, `workspaces/createur-de-fiches/shared/style-redactionnel.md`, `workspaces/createur-de-fiches/setup/questionnaire.md`, `workspaces/createur-de-fiches/stages/01-brief/CONTEXT.md`, `workspaces/createur-de-fiches/stages/02-sources-collectees/CONTEXT.md`, `workspaces/createur-de-fiches/stages/03-annotations/CONTEXT.md`, `workspaces/createur-de-fiches/stages/04-extraits/CONTEXT.md`, `workspaces/createur-de-fiches/stages/04-extraits/references/verification-doi.md`, `workspaces/createur-de-fiches/stages/05-connexions/CONTEXT.md`, `workspaces/createur-de-fiches/stages/06-relecture/CONTEXT.md`, `workspaces/createur-de-fiches/stages/07-publication/CONTEXT.md`

**Fichiers runs/ avec sha256 :**
workspaces/createur-de-fiches/runs/_example/stages/02-sources-collectees/output/exemple-memoire-sommeil-ids.json sha256: ecac9e4d8b4d3ea53bbeee2ca92b3b85fe746ddc36fa91542017ce702021e104
workspaces/createur-de-fiches/runs/_example/stages/02-sources-collectees/output/exemple-memoire-sommeil-sources.md sha256: 3d2b8109edcc5b3853bd65af0edc305fdfa0184a9d9143dce52f617c81f1a84a
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/00-brief.md sha256: 1e4c4c6be54612208280941ce946b2b1359acde87254032ced5187aa9432396f
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/01-brief/output/stellaris-stellarator-centrale-fusion-brief.md sha256: 338f1d4e218ebbb9fb680283b58ec9a4cd1186e340b9ffd7845c7aea53d7a896
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/01-brief/output/stellaris-stellarator-centrale-fusion-card.json sha256: da47bea8557d4bdf9b3bc23ea7038c7c757923709a60bf4e74504f0b6df6c33f
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/02-sources-collectees/output/stellaris-stellarator-centrale-fusion-ids.json sha256: e427a0cff2d0f56ad80e51ea22fc632a2e7fdca9554558215fe6a1a5011906f4
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/02-sources-collectees/output/stellaris-stellarator-centrale-fusion-rejetees.md sha256: 4d26a52081e6c277761e2fdda439017f0595bc81f99156e812f9bb089ff72ecf
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/02-sources-collectees/output/stellaris-stellarator-centrale-fusion-sources.md sha256: d675fbb31d5d187e7e0cbc58fda008730f6ecd07a8370ef492029d9d2a9da4e2
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/03-annotations/output/stellaris-stellarator-centrale-fusion-annotations.md sha256: f017eefc3e87e79cc7d4c0939ab802b1378134f4a29928b16de473bf78261ffa
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/04-extraits/output/stellaris-stellarator-centrale-fusion-extraits.md sha256: 6a6701cf9bc20908942862959b12a6f6b78a02485f4ec1ddea7b0f8a6bc25dc0
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/05-connexions/output/stellaris-stellarator-centrale-fusion-connexions.md sha256: 8b844d1f11a08faf1175219299796f182edccad6383e828e1f37d83ffc588297
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/06-relecture/output/stellaris-stellarator-centrale-fusion-verdict.md sha256: eecc2597556edacaba0b609a846bd32c537b50f64874d278c026d15c4605c7e7
workspaces/createur-de-fiches/runs/stellaris-stellarator-centrale-fusion/stages/07-publication/output/stellaris-stellarator-centrale-fusion-publication.md sha256: ca154b1c6155b15773767a0dc8f8abc866117f0096ebd78d06350bf5c5d10c81

## Annexe C — SHA256 des scripts (mis à jour)

`apps/backend/app/scripts/build_workspace_seed.py` sha256: 7cf2dbb7ec61b0f1df27f52ca16f3d7f163e1b25f9bc116503ad3858cf2efc6b
`apps/backend/app/scripts/export_openapi.py` sha256: d5e60b64817d2b028010a945fdd6b0ce216d6cd2d5ab35e8a4466589b15bb1d8
