import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';

const directory = process.argv[2];
assert(directory, 'Provide the synthetic browser fixture screenshot directory');
const filenames = ['integration-overview.png', 'event-recovery.png'];
const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const limit = 400 * 1024;
const chunkLength = 4096;

const evidence = await Promise.all(filenames.map(async filename => {
  const path = join(directory, filename);
  const info = await stat(path);
  assert(info.isFile() && info.size <= limit, filename + ' must be a PNG of at most 400 KiB');
  const buffer = await readFile(path);
  assert(buffer.length <= limit && buffer.subarray(0, 8).equals(pngSignature), filename + ' must contain PNG data');
  return { filename, buffer, digest: createHash('sha256').update(buffer).digest('hex') };
}));

console.log('::group::SyncOps synthetic browser screenshots');
for (const { filename, buffer, digest } of evidence) {
  const base64 = buffer.toString('base64');
  console.log('SYNCOPS_PNG_BEGIN ' + filename + ' ' + buffer.length + ' ' + digest);
  for (let offset = 0; offset < base64.length; offset += chunkLength) {
    console.log('SYNCOPS_PNG_CHUNK ' + filename + ' ' + offset / chunkLength + ' ' + base64.slice(offset, offset + chunkLength));
  }
  console.log('SYNCOPS_PNG_END ' + filename);
}
console.log('::endgroup::');
