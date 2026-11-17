import { copyFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const docs = path.resolve(frontend, '../docs');
const destination = path.join(frontend, 'public/user-guide');
const markdown = (await readFile(path.join(docs, 'USER_GUIDE.md'), 'utf8')).replaceAll(
  '\r\n',
  '\n',
);
const slug = (title) =>
  title
    .toLowerCase()
    .replace(/[^a-z0-9 -]/g, '')
    .replaceAll(' ', '-');
const sections = [...markdown.matchAll(/^## (.+)\r?\n([\s\S]*?)(?=^## |$(?![\s\S]))/gm)]
  .filter((match) => !['Contents', 'Detailed User Guide & SOP'].includes(match[1]))
  .map((match) => ({
    id: slug(match[1]),
    title: match[1],
    markdown: match[2].replaceAll('<!-- page -->', '').trim(),
  }));
if (sections.length < 25) throw new Error('The full user guide is missing sections.');

await mkdir(path.join(destination, 'images'), { recursive: true });
const images = new Set(
  [...markdown.matchAll(/!\[[^\]]*\]\((images\/[a-zA-Z0-9_.-]+)\)/g)].map((match) => match[1]),
);
for (const image of images) {
  await copyFile(path.join(docs, image), path.join(destination, image));
}
// These are separate operator/practice documents, not part of in-app user help.
// Remove only previously generated copies; the originals stay in docs/.
for (const name of ['SAMPLE_INPUT.txt', 'INPUT_AND_METRICS.txt', 'RUN_AND_CLOSE.txt']) {
  await rm(path.join(destination, name), { force: true });
}
await copyFile(path.join(docs, 'USER_GUIDE.md'), path.join(destination, 'USER_GUIDE.md'));
await copyFile(
  path.join(docs, 'user-guide/USER_GUIDE.pdf'),
  path.join(destination, 'USER_GUIDE.pdf'),
);
await writeFile(
  path.join(frontend, 'src/pages/help/userGuide.generated.json'),
  `${JSON.stringify({ sections }, null, 2)}\n`,
);
console.log(
  `User guide: ${sections.length} sections, ${images.size} screenshots, PDF and guide text.`,
);
