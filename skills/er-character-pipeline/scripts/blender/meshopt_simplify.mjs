// node meshopt_simplify.mjs <work_dir> <path to meshoptimizer/index.js>
// reads params.json, idx.u32, pos.f32, attr.f32, lock.u8 from work_dir; writes out_idx.u32 and out.json
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';

const { MeshoptSimplifier } = await import(pathToFileURL(process.argv[3]).href);
const dir = process.argv[2];
const P = JSON.parse(fs.readFileSync(path.join(dir, 'params.json'), 'utf8'));
const rd = (f, T) => {
	const b = fs.readFileSync(path.join(dir, f));
	return new T(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
};
const idx = rd('idx.u32', Uint32Array);
const pos = rd('pos.f32', Float32Array);
const attr = rd('attr.f32', Float32Array);
const lock = rd('lock.u8', Uint8Array);
await MeshoptSimplifier.ready;
const [out, err] = MeshoptSimplifier.simplifyWithAttributes(
	idx, pos, 3, attr, P.attr_stride, P.attr_weights, lock, P.target_index_count, P.target_error, []);
fs.writeFileSync(path.join(dir, 'out_idx.u32'), Buffer.from(out.buffer, out.byteOffset, out.byteLength));
const res = { in_tris: idx.length / 3, out_tris: out.length / 3, result_error: err,
	result_error_abs: err * MeshoptSimplifier.getScale(pos, 3) };
fs.writeFileSync(path.join(dir, 'out.json'), JSON.stringify(res));
console.log('MESHOPT ' + JSON.stringify(res));
