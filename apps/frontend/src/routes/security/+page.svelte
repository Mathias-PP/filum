<svelte:head>
  <title>Sécurité — Filum</title>
  <meta
    name="description"
    content="Comment Filum garantit l'intégrité et l'authenticité de vos fiches de lecture : signature Ed25519, hash SHA-256, gestion des clés."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <h1 class="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">Sécurité et cryptographie</h1>
  <p class="text-xl text-slate-600 mb-12">
    Filum est conçu pour que vos fiches de lecture soient <strong>vérifiables</strong> et
    <strong>immuables</strong> une fois publiées. Voici comment.
  </p>

  <section class="prose prose-slate max-w-none">
    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">
      Signature Ed25519
    </h2>
    <p class="text-slate-600 leading-relaxed">
      Chaque fiche publiée est signée avec une clé cryptographique Ed25519. Cette signature prouve
      que le contenu provient bien du créateur ou de la créatrice qui l'a publié, et qu'il n'a pas
      été modifié depuis.
    </p>
    <p class="text-slate-600 leading-relaxed">
      Ed25519 est un standard moderne de signature numérique, reconnu pour sa sécurité et sa
      rapidité. Il est utilisé notamment par
      <strong>SSH, Tor, OpenBSD et les blockchains</strong>.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Comment ça fonctionne</h2>
    <ol class="list-decimal pl-6 space-y-4 text-slate-600">
      <li>
        <strong class="text-slate-900">Canonicalisation</strong> — Le contenu de la fiche (titre,
        sources, métadonnées) est sérialisé selon la norme RFC 8785 (JSON Canonicalization Scheme).
        Cela garantit que deux sérialisations du même contenu produisent exactement le même résultat.
      </li>
      <li>
        <strong class="text-slate-900">Hachage</strong> — Le contenu canonicalisé est passé dans
        SHA-256, produisant une empreinte unique de 32 octets. La moindre modification du contenu
        changerait complètement cette empreinte.
      </li>
      <li>
        <strong class="text-slate-900">Signature</strong> — L'empreinte est signée avec la clé
        privée Ed25519 du créateur, produisant une signature de 64 octets. La clé privée est
        chiffrée sur le serveur avec AES-256-GCM.
      </li>
      <li>
        <strong class="text-slate-900">Publication</strong> — La signature et l'empreinte sont
        stockées avec la fiche. La date de publication est horodatée.
      </li>
    </ol>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Vérification</h2>
    <p class="text-slate-600 leading-relaxed">
      N'importe qui peut vérifier l'authenticité d'une fiche publiée sans avoir besoin de compte :
    </p>
    <ol class="list-decimal pl-6 space-y-2 text-slate-600">
      <li>
        Récupérer la clé publique du créateur (affichée sur sa page de profil)
      </li>
      <li>
        Récupérer le contenu de la fiche, sa signature et son empreinte via l'API
      </li>
      <li>
        Re-calculer l'empreinte à partir du contenu et vérifier qu'elle correspond
      </li>
      <li>
        Vérifier la signature avec la clé publique
      </li>
    </ol>
    <p class="text-slate-600 leading-relaxed mt-4">
      Si l'empreinte ou la signature ne correspondent pas, c'est que le contenu a été modifié
      <em>après</em> la publication.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">
      Gestion des clés
    </h2>
    <p class="text-slate-600 leading-relaxed">
      Lors de la création d'un compte, une paire de clés Ed25519 est générée côté serveur. La clé
      privée est immédiatement chiffrée avec AES-256-GCM en utilisant une clé maîtresse qui n'est
      jamais exposée. Seule la clé publique est stockée en clair — c'est celle qui permet à
      n'importe qui de vérifier vos signatures.
    </p>
    <p class="text-slate-600 leading-relaxed">
      Ce modèle signifie que Filum lui-même ne peut pas signer à votre place sans votre session.
      La signature est déclenchée uniquement lorsque vous publiez, après authentification.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">
      Archivage des sources
    </h2>
    <p class="text-slate-600 leading-relaxed">
      Chaque source ajoutée à une fiche est soumise à la Wayback Machine de l'Internet Archive.
      Si la page originale disparaît (lien mort, censure, modification), la copie archivée reste
      accessible. Cela garantit que vos sources sont <strong>pérennes</strong> et
      <strong>vérifiables</strong> dans le temps.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">FAQ sécurité</h2>
    <div class="space-y-4 not-prose">
      <div class="bg-slate-50 rounded-xl p-5">
        <h3 class="font-semibold text-slate-900 mb-1">
          Que se passe-t-il si Filum ferme ?
        </h3>
        <p class="text-sm text-slate-600">
          Les clés publiques des créateur·ice·s sont exportables. Les fiches publiées sont des
          données structurées que vous pouvez récupérer à tout moment via l'API. La signature
          reste vérifiable en dehors de Filum.
        </p>
      </div>
      <div class="bg-slate-50 rounded-xl p-5">
        <h3 class="font-semibold text-slate-900 mb-1">
          Puis-je modifier une fiche publiée ?
        </h3>
        <p class="text-sm text-slate-600">
          Non. Une fois publiée, une fiche est immuable. Toute modification nécessiterait de la
          dé-publier et de la re-publier, ce qui invaliderait la signature précédente. C'est un
          choix de conception : l'intégrité prime sur la flexibilité.
        </p>
      </div>
      <div class="bg-slate-50 rounded-xl p-5">
        <h3 class="font-semibold text-slate-900 mb-1">
          Mes données sont-elles chiffrées sur le serveur ?
        </h3>
        <p class="text-sm text-slate-600">
          Les clés privées sont chiffrées (AES-256-GCM). Les fiches et sources sont stockées en
          clair dans la base de données — elles sont publiques par conception une fois publiées.
          Les fiches en brouillon ne sont visibles que par leur créateur·ice.
        </p>
      </div>
    </div>
  </section>
</div>
