# 08 — Glossaire

> ⚠️ **Pivot ADR-019 (2026-05-14)** : les définitions de « signature de fiche », « canonical_hash de fiche », « fiche immuable » sont obsolètes. Nouveau terme à formaliser : **attestation de contenu** = triplet signé `(creator_id, content_url, attested_at)` prouvant la revendication d'un contenu original par son créateur·ice à une date précise. Voir `DECISIONS.md` ADR-019.

> Termes techniques, juridiques et institutionnels utilisés dans le projet. Conçu pour servir à la fois de rappel et de briefing initial pour un agent IA.

---

| Terme | Définition |
|---|---|
| **AI Act** | Règlement européen sur l'intelligence artificielle adopté en 2024, entré en application progressivement en 2025-2027. Impose des obligations de transparence sur les contenus générés par IA. Cadre favorable à Filum. |
| **Alembic** | Outil de migrations de schéma pour SQLAlchemy. Permet de versionner les changements de structure de base de données. |
| **Ancrage blockchain** | Technique consistant à publier périodiquement un hash d'un état de système sur une blockchain publique pour garantir l'immuabilité historique. Voir OpenTimestamps. Prévu pour Filum en phase 3, optionnel. |
| **Arcom** | Autorité de régulation française issue de la fusion CSA + Hadopi. Régulateur du DSA en France. |
| **BPI France** | Banque publique d'investissement française. Programme "Communs Numériques" pertinent pour Filum. |
| **C2PA** | Coalition for Content Provenance and Authenticity. Standard international de provenance lancé en 2021 (Adobe, Microsoft, BBC, etc.). Filum s'aligne en compatibilité. |
| **CAI** | Content Authenticity Initiative. Initiative d'Adobe qui porte le standard C2PA. |
| **Canonicalisation** | Processus de normalisation déterministe d'un contenu structuré (JSON, XML) avant hashing. Filum utilise RFC 8785 (JCS). |
| **Content-addressed storage** | Stockage où chaque fichier est identifié par son hash. Permet la déduplication automatique. |
| **dbt** | Data Build Tool. Standard moderne pour transformer des données en SQL versionné et testé. Utilisé sur DuckDB dans Filum. |
| **DID** | Decentralized Identifier (W3C). Identifiant numérique décentralisé, alternative aux certificats traditionnels. |
| **DSA** | Digital Services Act. Règlement européen sur les services numériques (2024). Impose obligations de transparence et modération aux grandes plateformes. |
| **DuckDB** | Base de données analytique embeddée, OLAP, ultra-performante. Utilisée dans Filum pour les analytics et dbt. |
| **Ed25519** | Algorithme de signature cryptographique moderne, basé sur la courbe Curve25519. Rapide, sûr, taille de clé compacte. Choix par défaut pour les signatures Filum. |
| **eIDAS 2.0** | Règlement européen sur l'identification électronique et services de confiance (2024). Cadre des signatures électroniques et horodatages qualifiés. |
| **European Media Freedom Act** | Règlement européen entré en vigueur en 2025, transparence éditoriale. |
| **Fact-checking** | Vérification de faits diffusés publiquement. Acteurs : Les Surligneurs, AFP Factuel, CheckNews. |
| **FastAPI** | Framework Python moderne pour APIs REST, async natif, validation Pydantic. Standard 2024+. |
| **Fédération** | Architecture où plusieurs serveurs autonomes interopèrent via un protocole commun (DNS, SMTP, Mastodon). Modèle visé long terme pour Filum. |
| **Fernet** | Algorithme de chiffrement symétrique de la lib `cryptography`. Utilisé pour chiffrer les clés privées des utilisateurs au repos. |
| **Hash perceptuel** | Hash dont la valeur reste similaire pour des contenus visuellement ou auditivement proches. Pas utilisé en MVP, prévu phase 3. |
| **HSM** | Hardware Security Module. Boîtier matériel sécurisé pour stockage de clés. Prévu phase 3. |
| **Internet Archive** | Organisation à but non lucratif (USA) qui archive le web. Service Wayback Machine. Partenaire technique de Filum en MVP. |
| **JSON-LD** | JSON for Linked Data. Format de structuration sémantique du web. Utilisé pour les pages publiques Filum (Schema.org). |
| **KYC** | Know Your Customer. Procédure de vérification d'identité. Prévu phase 3 pour Filum (créateurs notoires). |
| **LCEN** | Loi pour la Confiance dans l'Économie Numérique (France, 2004). Statut juridique d'hébergeur. |
| **Lineage / Filiation** | Graphe orienté qui relie un contenu à ses sources (parents) et à ses dérivés (enfants). Cœur conceptuel de Filum. |
| **Manifeste C2PA** | Structure de données signée cryptographiquement attachée à un fichier média, décrivant origine, auteur, transformations, sources. Extensible. |
| **MCP** | Model Context Protocol (Anthropic, 2024). Protocole pour agents IA. Filum publiera un serveur MCP en phase 3. |
| **NGI** | Next Generation Internet. Programme de la Commission européenne (NGI Trust, NGI Sargasso, NGI Zero). Cible de financement Filum. |
| **NLnet Foundation** | Fondation néerlandaise qui finance des projets d'infrastructure ouverte. ~50k€ par cycle. Cible prioritaire phase 0-2. |
| **OAuth** | Protocole standard d'authentification déléguée. Filum utilise OAuth Google en MVP. |
| **Open core** | Modèle économique mixte : cœur open-source gratuit, fonctionnalités avancées propriétaires payantes. |
| **OpenTimestamps** | Service open-source d'horodatage cryptographique sur Bitcoin. Permet l'ancrage blockchain sans dépendance crypto. Optionnel pour Filum. |
| **ORCID** | Open Researcher and Contributor ID. Identifiant standard pour les chercheurs. À intégrer en phase 2-3. |
| **PKI** | Public Key Infrastructure. Infrastructure cryptographique classique fondée sur cryptographie asymétrique et certificats X.509. Base technique de Filum. |
| **Provenance** | Origine et historique d'un contenu. Vocabulaire central de C2PA et de Filum. |
| **Pydantic** | Lib Python de validation de données par les types. Version 2 utilisée dans Filum. |
| **RFC 3161** | Standard d'horodatage cryptographique. Format des time-stamps eIDAS. |
| **RFC 8785** | JSON Canonicalization Scheme (JCS). Norme de canonicalisation déterministe du JSON. Utilisée par Filum avant hashing. |
| **RGPD** | Règlement général sur la protection des données (UE, 2018). Applicable à Filum (métadonnées créateurs). |
| **Schema.org** | Vocabulaire de structuration sémantique du web, soutenu par Google, Microsoft, Yahoo. À utiliser pour les pages Filum. |
| **SHA-256** | Algorithme de hash cryptographique standard (256 bits, 64 caractères hex). Utilisé par Filum pour l'empreinte des fiches. |
| **SLA** | Service Level Agreement. Engagement contractuel de disponibilité. |
| **SQLAlchemy** | ORM Python standard. Filum utilise la version 2.x en mode async. |
| **SSR** | Server-Side Rendering. Génération HTML côté serveur. Utilisé par SvelteKit pour les pages publiques Filum. |
| **Stemma** | Terme philologique : arbre généalogique des manuscrits. Alternative au nom Filum. |
| **SvelteKit** | Framework web meta sur Svelte. Choix frontend de Filum. |
| **Tailwind CSS** | Framework CSS utilitaire. Choix styling de Filum. |
| **TSA** | Time Stamping Authority. Autorité d'horodatage qualifiée eIDAS. Exemples français : Universign, Certinomis. |
| **TypeScript** | JavaScript typé. Utilisé côté frontend Filum. |
| **uv** | Package manager Python ultra rapide (Astral). Remplace pip. |
| **Verifiable Credentials** | Standard W3C de certifications numériques vérifiables. Alternative moderne aux certificats. |
| **W3C** | World Wide Web Consortium. Organisme de standardisation. Cible long terme pour Filum (Credentials WG). |
| **Wayback Machine** | Service d'archivage web d'Internet Archive. API gratuite utilisée par Filum en MVP. |
| **WebExtension API** | Standard d'extensions navigateur. Compatible Chrome, Firefox, Edge, Safari. Prévu pour Filum en phase 2. |

---

*Tous les termes définis ici peuvent être utilisés sans explication dans les autres documents `.docs/`.*
