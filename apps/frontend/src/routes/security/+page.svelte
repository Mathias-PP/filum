<svelte:head>
  <title>Sécurité — Philum</title>
  <meta
    name="description"
    content="Comment Philum garantit l'identité des créateur·ice·s et l'authenticité de leurs revendications de contenu : signature Ed25519, hash SHA-256, gestion des clés."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <h1 class="text-3xl sm:text-4xl font-bold text-ink-primary mb-4">Sécurité et cryptographie</h1>
  <p class="text-xl text-ink-secondary mb-12">
    Philum est conçu pour que vos revendications de contenu soient
    <strong>vérifiables</strong> par n'importe qui. Voici comment.
  </p>

  <section class="prose prose-slate dark:prose-invert max-w-none">
    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Ce qui est signé</h2>
    <p class="text-ink-secondary leading-relaxed">
      Les fiches bibliographiques sont des documents vivants : vous pouvez les compléter, corriger
      une coquille, ajouter une source au fil du temps.
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Ce qui est signé, ce sont vos <strong>liens créateur·ice ↔ contenu</strong> : à chaque fois
      que vous revendiquez un contenu original (vidéo, article, podcast, post…), un triplet (votre
      identité Philum, l'URL du contenu, la date d'attestation) est signé avec votre clé Ed25519.
      Cela prouve que <em>vous</em> revendiquez <em>ce contenu</em> à <em>cette date précise</em>.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Signature Ed25519</h2>
    <p class="text-ink-secondary leading-relaxed">
      Philum utilise Ed25519, un standard moderne de signature numérique reconnu pour sa sécurité et
      sa rapidité, utilisé notamment par <strong>SSH, Tor, OpenBSD et les blockchains</strong>.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Comment ça fonctionne</h2>
    <ol class="list-decimal pl-6 space-y-4 text-ink-secondary">
      <li>
        <strong class="text-ink-primary">Canonicalisation</strong> : le triplet à signer (votre id, URL
        du contenu, date d'attestation) est sérialisé selon la norme RFC 8785 (JSON Canonicalization Scheme).
        Cela garantit que deux sérialisations du même triplet produisent exactement le même résultat.
      </li>
      <li>
        <strong class="text-ink-primary">Hachage</strong> : le contenu canonicalisé est passé dans SHA-256,
        produisant une empreinte unique de 32 octets.
      </li>
      <li>
        <strong class="text-ink-primary">Signature</strong> : l'empreinte est signée avec votre clé privée
        Ed25519, produisant une signature de 64 octets. La clé privée est chiffrée sur le serveur avec
        AES-256-GCM.
      </li>
      <li>
        <strong class="text-ink-primary">Stockage</strong> : la signature et l'empreinte sont stockées
        avec l'attestation de contenu.
      </li>
    </ol>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Vérification</h2>
    <p class="text-ink-secondary leading-relaxed mb-4">
      N'importe qui peut vérifier l'authenticité d'une attestation de contenu sans avoir besoin de
      compte :
    </p>
    <ol class="list-decimal pl-6 space-y-2 text-ink-secondary">
      <li>Récupérer la clé publique du créateur (affichée sur sa page de profil)</li>
      <li>Récupérer le triplet attesté, sa signature et son empreinte via l'API</li>
      <li>Re-calculer l'empreinte à partir du triplet et vérifier qu'elle correspond</li>
      <li>Vérifier la signature avec la clé publique</li>
    </ol>
    <p class="text-ink-secondary leading-relaxed mt-4">
      Si l'empreinte ou la signature ne correspondent pas, c'est que l'attestation a été modifiée
      <em>après</em> sa signature.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">
      Et les fiches bibliographiques ?
    </h2>
    <p class="text-ink-secondary leading-relaxed">
      Les fiches sont des documents vivants : vous gardez la liberté de les modifier après
      publication. Pour autant, leur traçabilité est assurée par d'autres mécanismes : horodatage
      des modifications, journal d'audit, archivage des sources via la Wayback Machine.
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Ce qui est garanti cryptographiquement, c'est la <strong>revendication</strong> du contenu original
      par son créateur·ice à une date précise, pas l'immuabilité de la bibliographie qui l'accompagne.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Gestion des clés</h2>
    <p class="text-ink-secondary leading-relaxed">
      Lors de la création d'un compte, une paire de clés Ed25519 est générée côté serveur. La clé
      privée est immédiatement chiffrée avec AES-256-GCM en utilisant une clé maîtresse qui n'est
      jamais exposée. Seule la clé publique est stockée en clair : c'est celle qui permet à
      n'importe qui de vérifier vos signatures.
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Ce modèle signifie que Philum lui-même ne peut pas signer à votre place sans votre session. La
      signature est déclenchée uniquement après authentification.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Archivage des sources</h2>
    <p class="text-ink-secondary leading-relaxed">
      Chaque source ajoutée à une fiche est soumise à la Wayback Machine de l'Internet Archive. Si
      la page originale disparaît (lien mort, censure, modification), la copie archivée reste
      accessible. Cela garantit que vos sources sont <strong>pérennes</strong> et
      <strong>vérifiables</strong> dans le temps.
    </p>
  </section>
</div>
