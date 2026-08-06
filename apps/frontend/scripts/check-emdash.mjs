/* eslint-env node */
/**
 * Refuse les em-dashes dans le texte visible du frontend.
 *
 * Le tiret cadratin est devenu un marqueur stylistique de texte généré. La
 * seule exception tolérée est le glyphe de valeur absente, isolé, qui n'est
 * pas de la prose.
 */
import { readFileSync } from 'node:fs';
import { globSync } from 'node:fs';

const files = globSync('src/{routes,lib}/**/*.svelte', {
  cwd: new URL('..', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1'),
  exclude: (p) => p.includes('sandbox'),
});
const offenders = [];

for (const file of files) {
  const fullPath = new URL(`../${file}`, import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
  const lines = readFileSync(fullPath, 'utf8').split('\n');
  let inBlockComment = false;

  lines.forEach((line, i) => {
    if (!line.includes('—')) {
      // Suivi de l'état des commentaires bloc même sur les lignes sans em-dash
      if (line.includes('<!--') || line.includes('/*')) inBlockComment = true;
      if (line.includes('-->') || line.includes('*/')) inBlockComment = false;
      return;
    }

    const trimmed = line.trim();

    // Commentaires de ligne
    if (
      trimmed.startsWith('//') ||
      trimmed.startsWith('*') ||
      trimmed.startsWith('/**') ||
      trimmed.startsWith('/*') ||
      trimmed.startsWith('<!--')
    )
      return;

    // Commentaires bloc multi-lignes
    if (inBlockComment) return;
    if (line.includes('/*') || line.includes('<!--')) {
      inBlockComment = true;
      return;
    }

    // Glyphe de valeur absente : `—` isolé entre balises ou après `??`
    if (/(\?\?\s*['"]—['"])|([>]\s*—\s*[<])/.test(line)) return;

    offenders.push(`${file}:${i + 1}: ${trimmed}`);

    // Fermeture du bloc après la ligne
    if (line.includes('-->') || line.includes('*/')) inBlockComment = false;
  });
}

if (offenders.length > 0) {
  console.error('Em-dashes interdits dans le texte visible :\n' + offenders.join('\n'));
  process.exit(1);
}
console.log('Aucun em-dash dans le texte visible.');
