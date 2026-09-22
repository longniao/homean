import sharp from 'sharp';
import { fileURLToPath } from 'node:url';

const source = fileURLToPath(new URL('../public/og.svg', import.meta.url));
const png = await sharp(source).png().toBuffer();
for (const target of ['../public/og.png', '../../dashboard/public/og.png']) {
  await sharp(png).toFile(fileURLToPath(new URL(target, import.meta.url)));
}
