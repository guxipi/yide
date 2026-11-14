using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

namespace Lab.Kits.Editor
{
    /// <summary>
    /// 草顶崖壁 (grass-top cliff) kit. 勾哥 2026-11-14: 「非常好，除了零碎的叶片，其它的进无伤复用，叫草顶崖壁」.
    /// Give it stacked tier outlines (world XZ) and it returns the meshes:
    ///   rock   - every wall of a tier is one plain plane; long straight edges, 45 degree chamfers and jogs are the caller's outline.
    ///            No lines or layers on the walls: 勾哥 11-14 had horizontal rock-layer lines tried and ruled 「太丑了，横纹不要入复用库」.
    ///   turf   - per tier one cap volume: flat top (the ground's own grass), quarter-ellipse shoulder, hanging skirt whose lower edge
    ///            swells in a few broad scallops, underside back to the wall. It overhangs the wall.
    ///   leaves - optional hanging leaves on the skirt's lower edge (NOT part of the approved kit; off by default).
    /// No vertex colour stands in for light or shadow: the skirt goes dark because the turf material is lit by its real normals
    /// (<see cref="SetupTurfMaterial"/>), the line under the skirt is a cast shadow (rock and turf cast + receive).
    /// Kit card: yide repo assets/er-ground/GrassTopCliff/README.md.
    /// </summary>
    public static class GrassTopCliffKit
    {
        public sealed class Tier
        {
            public Vector2[] outline;      // world XZ, any winding
            public float baseY, topY;      // the rock stands on baseY (walls start 0.3 m below it) and its top is topY
            public int seed;
        }

        public sealed class Params
        {
            // turf cap section (metres)
            public float lift = 0.10f;          // turf top above the rock top
            public float overhang = 0.30f;      // skirt face in front of the wall
            public float shoulderX = 0.28f, shoulderY = 0.45f;   // shoulder: quarter ellipse (out, down)
            public float drop = 0.85f;          // mean skirt depth below the turf top
            public float scallopDrop = 0.24f;   // extra depth of a broad scallop
            public float cornerBlend = 0.45f;   // normals blend over +- this arc length at outline corners (how round the turf turns a corner)
            public float stepSeen = 0.14f, stepUnseen = 0.6f;   // rim sampling on seen / unseen edges
            public Vector3 skirtRoot = new Vector3(0.92f, 0.94f, 0.97f);   // the skirt's own tip-to-root grade (x grass)
            // hanging leaves (not approved yet)
            public bool leaves = false;
            public float accentLen = 0.26f, accentWidth = 0.15f, edgeLenMin = 0.18f, edgeLenMax = 0.30f, edgeLenBig = 0.36f;
            // linear vertex colours
            public Color grass = new Color(0.12002f, 0.21662f, 0.05344f, 1f);
            public Color rock = new Color(0.38448f, 0.26621f, 0.16697f, 1f);
            /// <summary>Outward wall normal (XZ) -> does the game camera see this wall. Default: a camera looking along +z.</summary>
            public Func<Vector2, bool> wallSeen = n => n.y < 0.35f;
        }

        public sealed class Meshes { public Mesh rock, turf, leaves; }

        // ── buffers and polygon helpers ─────────────────────────────────────
        sealed class Buf
        {
            public readonly List<Vector3> v = new List<Vector3>(); public readonly List<Vector3> n = new List<Vector3>();
            public readonly List<Color> c = new List<Color>(); public readonly List<int> t = new List<int>();
            public int Add(Vector3 p, Vector3 nn, Color col) { v.Add(p); n.Add(nn); c.Add(col); return v.Count - 1; }
            public void Tri(int a, int b, int d) { t.Add(a); t.Add(b); t.Add(d); }
            public void Quad(int a, int b, int d, int e) { Tri(a, b, d); Tri(a, d, e); }
            /// <summary>Flat-shaded quad, corners given clockwise as seen from its front.</summary>
            public void Face(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, Color col)
            {
                var nn = Vector3.Cross(p1 - p0, p2 - p0).normalized;
                int a = Add(p0, nn, col), b = Add(p1, nn, col), d = Add(p2, nn, col), e = Add(p3, nn, col); Quad(a, b, d, e);
            }
            public Mesh Finish(string name)
            {
                var m = new Mesh { name = name, indexFormat = v.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
                m.SetVertices(v); m.SetNormals(n); m.SetColors(c); m.SetUVs(0, v.Select(p => new Vector2(p.x, p.z)).ToList());
                m.SetTriangles(t, 0); m.RecalculateBounds(); return m;
            }
        }

        static float Area(IList<Vector2> p) { float a = 0f; for (int i = 0; i < p.Count; i++) { var q = p[(i + 1) % p.Count]; a += p[i].x * q.y - q.x * p[i].y; } return a * 0.5f; }
        /// <summary>Counter-clockwise copy (seen from above with x right, z up).</summary>
        public static Vector2[] Ccw(Vector2[] p) => Area(p) >= 0f ? (Vector2[])p.Clone() : p.Reverse().ToArray();
        /// <summary>Outward normal of edge a-b of a CCW outline.</summary>
        public static Vector2 OutN(Vector2 a, Vector2 b) { var e = (b - a).normalized; return new Vector2(e.y, -e.x); }
        static float Cross(Vector2 a, Vector2 b) => a.x * b.y - a.y * b.x;

        /// <summary>Mitre offset of a CCW polygon (positive = outward).</summary>
        static Vector2[] Offset(Vector2[] p, float d)
        {
            int n = p.Length; var r = new Vector2[n];
            for (int i = 0; i < n; i++)
            {
                var n0 = OutN(p[(i + n - 1) % n], p[i]); var n1 = OutN(p[i], p[(i + 1) % n]);
                var b = (n0 + n1).normalized; float k = Mathf.Max(0.3f, Vector2.Dot(b, n0));
                r[i] = p[i] + b * (d / k);
            }
            return r;
        }

        static bool InTri(Vector2 p, Vector2 a, Vector2 b, Vector2 c)
        { float d1 = Cross(b - a, p - a), d2 = Cross(c - b, p - b), d3 = Cross(a - c, p - c); return d1 >= -1e-6f && d2 >= -1e-6f && d3 >= -1e-6f; }

        /// <summary>Ear clipping of a simple CCW polygon; returns index triples.</summary>
        static List<int> Ears(IList<Vector2> p)
        {
            var idx = Enumerable.Range(0, p.Count).ToList(); var tris = new List<int>(); int guard = 0;
            while (idx.Count > 3 && guard++ < 10000)
            {
                bool cut = false;
                for (int i = 0; i < idx.Count; i++)
                {
                    int a = idx[(i + idx.Count - 1) % idx.Count], b = idx[i], c = idx[(i + 1) % idx.Count];
                    if (Cross(p[b] - p[a], p[c] - p[b]) <= 1e-7f) continue;
                    bool hit = false;
                    foreach (int j in idx) { if (j == a || j == b || j == c) continue; if (InTri(p[j], p[a], p[b], p[c])) { hit = true; break; } }
                    if (hit) continue;
                    tris.Add(a); tris.Add(b); tris.Add(c); idx.RemoveAt(i); cut = true; break;
                }
                if (!cut) break;
            }
            if (idx.Count == 3) { tris.Add(idx[0]); tris.Add(idx[1]); tris.Add(idx[2]); }
            return tris;
        }

        public static float Hash(int i, int salt) { unchecked { uint h = (uint)(i * 374761393 + salt * 668265263); h = (h ^ (h >> 13)) * 1274126177u; return ((h ^ (h >> 16)) & 0xFFFFFF) / 16777215f; } }
        public static bool Inside(Vector2[] poly, Vector2 p)
        { bool c = false; for (int i = 0, j = poly.Length - 1; i < poly.Length; j = i++) if ((poly[i].y > p.y) != (poly[j].y > p.y) && p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x) c = !c; return c; }
        /// <summary>Distance from p to the outline's edges; with <paramref name="seen"/> only the edges whose wall that test accepts.</summary>
        public static float EdgeDist(Vector2[] ccw, Vector2 p, Func<Vector2, bool> seen = null)
        {
            float d = float.MaxValue;
            for (int i = 0; i < ccw.Length; i++)
            {
                var a = ccw[i]; var b = ccw[(i + 1) % ccw.Length]; if (seen != null && !seen(OutN(a, b))) continue;
                var ab = b - a; float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude); d = Mathf.Min(d, Vector2.Distance(p, a + ab * t));
            }
            return d;
        }

        static Vector3 P3(Vector2 p, float y) => new Vector3(p.x, y, p.y);
        static Color Mul(Color c, Vector3 k) => new Color(c.r * k.x, c.g * k.y, c.b * k.z, 1f);

        // ── rim signal: scallops (approved) and leaves (optional) ────────────
        sealed class RimSignal
        {
            readonly List<(float s, float w, float h)> scallops = new List<(float, float, float)>();
            public readonly List<(float s, float len, float tilt, float lean)> accents = new List<(float, float, float, float)>();
            public readonly List<(float s, float len, float tilt)> edge = new List<(float, float, float)>();
            public RimSignal(float length, int seed, Params p)
            {
                // edge leaves: groups of 2-4 overlapping leaves, one to two group widths of plain edge between groups
                float q = 0.3f + Hash(seed, 41) * 0.8f; int c = 0; float k0 = p.edgeLenMax / 0.30f;
                while (q < length - 0.5f)
                {
                    int count = 2 + (int)(Hash(seed + c, 42) * 2.99f); float q0 = q;
                    for (int i = 0; i < count; i++)
                    {
                        float big = Hash(seed + c * 11 + i, 43); float len = big > 0.8f ? p.edgeLenBig : Mathf.Lerp(p.edgeLenMin, p.edgeLenMax, big / 0.8f);
                        edge.Add((q, len, (Hash(seed + c * 11 + i, 44) - 0.5f) * 44f)); q += (0.10f + 0.08f * Hash(seed + c * 11 + i, 45)) * k0;
                    }
                    q += (q - q0) * (1f + Hash(seed + c, 46)) + 0.5f; c++;
                }
                float s = 0.5f + Hash(seed, 1) * 1.5f; int k = 0;
                while (s < length - 0.8f)
                {
                    if (Hash(seed + k, 2) < 0.3f)
                    {   // a broad scallop, sometimes two
                        int count = 1 + (Hash(seed + k, 3) < 0.35f ? 1 : 0);
                        for (int i = 0; i < count; i++) { float w = 1.6f + 1.2f * Hash(seed + k * 7 + i, 4); scallops.Add((s + w * 0.5f, w, p.scallopDrop * (0.6f + 0.6f * Hash(seed + k * 7 + i, 5)))); s += w * 0.9f; }
                    }
                    else
                    {   // one or two brighter leaves that lean out
                        float r = Hash(seed + k, 3); int count = r < 0.65f ? 1 : 2; float side = Hash(seed + k, 6) < 0.5f ? -1f : 1f;
                        for (int i = 0; i < count; i++)
                        {
                            float size = i == 0 ? 1f + 0.35f * Hash(seed + k * 7, 4) : 0.55f + 0.3f * Hash(seed + k * 7 + i, 4);
                            float tilt = side * (i == 0 ? 6f + 16f * Hash(seed + k * 7, 5) : -(14f + 22f * Hash(seed + k * 7 + i, 5)));
                            float lean = Hash(seed + k * 7 + i, 7) < 0.22f ? 38f + 14f * Hash(seed + k * 7 + i, 8) : 6f + 16f * Hash(seed + k * 7 + i, 8);
                            accents.Add((s, p.accentLen * size, tilt, lean)); s += 0.2f + 0.22f * Hash(seed + k * 7 + i, 9);
                        }
                    }
                    s += 2.2f + 2.4f * Hash(seed + k, 8);   // calm run
                    k++;
                }
            }
            public float At(float s)
            {
                float d = 0f;
                foreach (var e in scallops) { float x = Mathf.Abs(s - e.s) / (e.w * 0.5f); if (x < 1f) d = Mathf.Max(d, e.h * Mathf.Cos(x * Mathf.PI * 0.5f)); }
                return d;
            }
        }

        struct RimPt { public Vector2 p, n; public float s; public bool seen; }

        /// <summary>Samples the outline: positions stay on the sharp rock outline, normals blend across corners so the turf rounds them.</summary>
        static List<RimPt> Rim(Vector2[] poly, Params p)
        {
            int n = poly.Length; var raw = new List<(Vector2 p, int edge, float s)>(); float s = 0f;
            var edgeStart = new float[n + 1];
            for (int i = 0; i < n; i++)
            {
                var a = poly[i]; var b = poly[(i + 1) % n]; float len = Vector2.Distance(a, b); edgeStart[i] = s;
                float step = p.wallSeen(OutN(a, b)) ? p.stepSeen : p.stepUnseen; int cnt = Mathf.Max(2, Mathf.CeilToInt(len / step));
                for (int k = 0; k < cnt; k++) raw.Add((Vector2.Lerp(a, b, k / (float)cnt), i, s + len * k / cnt));
                s += len;
            }
            edgeStart[n] = s;
            var pts = new List<RimPt>(raw.Count);
            foreach (var r in raw)
            {
                var en = OutN(poly[r.edge], poly[(r.edge + 1) % n]); Vector2 nn = en;
                float toStart = r.s - edgeStart[r.edge], toEnd = edgeStart[r.edge + 1] - r.s;
                if (toStart < p.cornerBlend) { int pe = (r.edge + n - 1) % n; var pn = OutN(poly[pe], poly[r.edge]); nn = Vector2.Lerp(pn, en, 0.5f + 0.5f * toStart / p.cornerBlend).normalized; }
                else if (toEnd < p.cornerBlend) { int ne = (r.edge + 1) % n; var nx = OutN(poly[ne], poly[(ne + 1) % n]); nn = Vector2.Lerp(nx, en, 0.5f + 0.5f * toEnd / p.cornerBlend).normalized; }
                pts.Add(new RimPt { p = r.p, n = nn, s = r.s, seen = p.wallSeen(en) });
            }
            return pts;
        }

        // ── rock: plain walls ───────────────────────────────────────────────
        static void AddRock(Buf rock, Tier tier, Vector2[] poly, Params p)
        {
            int n = poly.Length; float y0 = tier.baseY - 0.3f, y1 = tier.topY - 0.45f;   // the wall's top edge stays inside the turf shoulder
            for (int i = 0; i < n; i++)
            {
                var a = poly[i]; var b = poly[(i + 1) % n];
                rock.Face(P3(a, y0), P3(a, y1), P3(b, y1), P3(b, y0), p.rock);
            }
            int b0 = rock.v.Count; foreach (var q in poly) rock.Add(P3(q, y1), Vector3.up, p.rock);
            var ears = Ears(poly); for (int i = 0; i < ears.Count; i += 3) rock.Tri(b0 + ears[i], b0 + ears[i + 2], b0 + ears[i + 1]);
        }

        // ── turf cap ────────────────────────────────────────────────────────
        static void AddTurf(Buf turf, Buf leaves, Tier tier, Vector2[] poly, Params p)
        {
            var rim = Rim(poly, p); int m = rim.Count; float total = 0f; for (int i = 0; i < poly.Length; i++) total += Vector2.Distance(poly[i], poly[(i + 1) % poly.Length]);
            int seed = tier.seed; var sig = new RimSignal(total, seed, p); float top = tier.topY + p.lift;
            float Slow(float s) => 1f + 0.10f * Mathf.Sin(s * 0.9f + seed) + 0.02f * Mathf.Sin(s * 2.3f + seed * 1.7f);
            const int Rings = 8; int b0 = turf.v.Count;
            for (int i = 0; i < m; i++)
            {
                var r = rim[i]; float extra = r.seen ? sig.At(r.s) : 0f;
                float d = p.drop * Slow(r.s) + extra, o = p.overhang + 0.05f * Mathf.Sin(r.s * 1.1f + seed * 0.7f) + 0.03f * Mathf.Sin(r.s * 2.7f + seed);
                var n3 = new Vector3(r.n.x, 0f, r.n.y);
                for (int k = 0; k < Rings; k++)
                {
                    float rad, y; Vector3 nn; float tone;
                    if (k == 0) { rad = -0.9f; y = top; nn = Vector3.up; tone = 0f; }
                    else if (k <= 5)
                    {   // quarter-ellipse shoulder, 22.5 degree steps
                        float th = (k - 1) * 22.5f * Mathf.Deg2Rad, sn = Mathf.Sin(th), cs = Mathf.Cos(th);
                        rad = o - p.shoulderX + p.shoulderX * sn; y = top - p.shoulderY * (1f - cs);
                        nn = (n3 * (sn / p.shoulderX) + Vector3.up * (cs / p.shoulderY)).normalized; tone = 0.5f * (1f - cs);
                    }
                    else if (k == 6) { rad = o - 0.04f; y = top - d; nn = n3; tone = 1f; }
                    else { rad = -0.05f; y = top - d + 0.15f; nn = Vector3.down; tone = 1f; }
                    turf.Add(P3(r.p + r.n * rad, y), nn, Mul(p.grass, Vector3.Lerp(Vector3.one, p.skirtRoot, tone)));
                }
            }
            for (int i = 0; i < m; i++)
            {
                int a = b0 + i * Rings, b = b0 + ((i + 1) % m) * Rings;
                for (int k = 0; k < Rings - 1; k++) turf.Quad(a + k, b + k, b + k + 1, a + k + 1);
            }
            // flat top: the outline inset 0.8 m (overlaps ring 0, same plane, same colour)
            var cap = Offset(poly, -0.8f); int c0 = turf.v.Count; foreach (var q in cap) turf.Add(P3(q, top), Vector3.up, p.grass);
            var ears = Ears(cap); for (int i = 0; i < ears.Count; i += 3) turf.Tri(c0 + ears[i], c0 + ears[i + 2], c0 + ears[i + 1]);
            if (!p.leaves) return;
            int li = 0;
            RimPt Nearest(float s) { int best = 0; float bd = float.MaxValue; for (int i = 0; i < m; i++) { float dd = Mathf.Abs(rim[i].s - s); if (dd < bd) { bd = dd; best = i; } } return rim[best]; }
            foreach (var lf in sig.accents)
            {
                var r = Nearest(lf.s); if (!r.seen) continue; float d = p.drop * Slow(r.s) + sig.At(r.s);
                var n3 = new Vector3(r.n.x, 0f, r.n.y); var tan = new Vector3(-r.n.y, 0f, r.n.x);
                AddLeaf(leaves, P3(r.p + r.n * (p.overhang + 0.02f), top - d + lf.len * 0.55f), n3, tan, lf.len, p.accentWidth * (lf.len / p.accentLen) * (0.9f + 0.25f * Hash(seed * 13 + li, 14)), lf.tilt, lf.lean, true, p); li++;
            }
            foreach (var lf in sig.edge)
            {
                var r = Nearest(lf.s); if (!r.seen) continue; float d = p.drop * Slow(r.s) + sig.At(r.s);
                var n3 = new Vector3(r.n.x, 0f, r.n.y); var tan = new Vector3(-r.n.y, 0f, r.n.x);
                AddLeaf(leaves, P3(r.p + r.n * (p.overhang + 0.01f), top - d + lf.len * 0.62f), n3, tan, lf.len, lf.len * 0.74f, lf.tilt, -4f, false, p); li++;
            }
        }

        /// <summary>One hanging leaf at the skirt's lower edge. Accent leaves lean out and catch the sun; edge leaves lie on the skirt and take
        /// its shade, so they read as its lobed lower edge.</summary>
        static void AddLeaf(Buf buf, Vector3 root, Vector3 n3, Vector3 tan, float len, float width, float tiltDeg, float leanDeg, bool accent, Params p)
        {
            float a = tiltDeg * Mathf.Deg2Rad, f = (leanDeg + 14f) * Mathf.Deg2Rad;
            var inPlane = Vector3.down * Mathf.Cos(a) + tan * Mathf.Sin(a);
            var dir = (inPlane * Mathf.Cos(f) + n3 * Mathf.Sin(f)).normalized; var wide = Vector3.Cross(n3, dir).normalized;
            var nn = Vector3.Cross(dir, wide).normalized; if (Vector3.Dot(nn, n3) < 0f) nn = -nn; nn = accent ? (nn + Vector3.up * 0.55f).normalized : n3;
            var col = accent ? Mul(p.grass, new Vector3(1.10f, 1.07f, 0.92f)) : Mul(p.grass, p.skirtRoot);
            float[] us = { 0f, 0.14f, 0.38f, 0.66f, 0.86f }; float[] ws = accent ? new[] { 0.2f, 0.72f, 1f, 0.66f, 0.3f } : new[] { 0.6f, 0.9f, 1f, 0.78f, 0.42f };
            int b0 = buf.v.Count;
            for (int i = 0; i < us.Length; i++) { var c = root + dir * (len * us[i]); buf.Add(c - wide * (width * 0.5f * ws[i]), nn, col); buf.Add(c + wide * (width * 0.5f * ws[i]), nn, col); }
            int tip = buf.Add(root + dir * len, nn, col);
            for (int i = 0; i < us.Length - 1; i++) { int q = b0 + i * 2; buf.Quad(q, q + 1, q + 3, q + 2); buf.Quad(q, q + 2, q + 3, q + 1); }
            int l = b0 + (us.Length - 1) * 2; buf.Tri(l, l + 1, tip); buf.Tri(l, tip, l + 1);
        }

        // ── public entry points ─────────────────────────────────────────────
        /// <summary>Builds the meshes for stacked tiers (lowest first). <c>leaves</c> is null when <see cref="Params.leaves"/> is off.</summary>
        public static Meshes Make(IList<Tier> tiers, Params p, string namePrefix)
        {
            var rb = new Buf(); var tb = new Buf(); var lb = new Buf();
            foreach (var tier in tiers)
            {
                var poly = Ccw(tier.outline);
                AddRock(rb, tier, poly, p);
                AddTurf(tb, lb, tier, poly, p);
            }
            return new Meshes { rock = rb.Finish(namePrefix + "_Rock"), turf = tb.Finish(namePrefix + "_Turf"), leaves = p.leaves && lb.v.Count > 0 ? lb.Finish(namePrefix + "_Leaves") : null };
        }

        /// <summary>Rock: plain Lab/LabLit with vertex colour.</summary>
        public static void SetupRockMaterial(Material mat)
        {
            mat.SetColor("_BaseColor", Color.white); mat.SetFloat("_VertexColorMul", 1f); mat.SetFloat("_Unlit", 0f);
            mat.SetFloat("_ShadowThreshold", 0f); mat.SetFloat("_ShadowSoftness", 0.1f); mat.SetFloat("_AmbientStrength", 0.15f); mat.SetFloat("_Cull", 2f);
        }

        /// <summary>Turf: a copy of the scene's ground grass material, lit by the cap's real normals - the top stays the ground colour, the
        /// skirt turns away from the sun and goes to the grass's own shade.</summary>
        public static void SetupTurfMaterial(Material mat)
        {
            mat.SetFloat("_NormalUp", 0.12f); mat.SetFloat("_ShadowThreshold", 0.10f); mat.SetFloat("_ShadowSoftness", 0.7f);
        }

        public static Material RockMaterialAsset(string path)
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null) { mat = new Material(Shader.Find("Lab/LabLit")) { name = Path.GetFileNameWithoutExtension(path) }; AssetDatabase.CreateAsset(mat, path); }
            SetupRockMaterial(mat); EditorUtility.SetDirty(mat); return mat;
        }

        public static Material TurfMaterialAsset(Material groundGrass, string path)
        {
            if (groundGrass == null) throw new ArgumentNullException(nameof(groundGrass));
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null) { mat = new Material(groundGrass) { name = Path.GetFileNameWithoutExtension(path) }; AssetDatabase.CreateAsset(mat, path); }
            else { mat.shader = groundGrass.shader; mat.CopyPropertiesFromMaterial(groundGrass); mat.shaderKeywords = groundGrass.shaderKeywords; }
            SetupTurfMaterial(mat); EditorUtility.SetDirty(mat); return mat;
        }

        /// <summary>Saves a generated mesh at <paramref name="path"/>, overwriting in place so scene references survive a rebuild.</summary>
        public static Mesh KeepMesh(Mesh mesh, string path)
        {
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing == null) { AssetDatabase.CreateAsset(mesh, path); return mesh; }
            existing.Clear(); EditorUtility.CopySerialized(mesh, existing); existing.name = Path.GetFileNameWithoutExtension(path);
            EditorUtility.SetDirty(existing); Object.DestroyImmediate(mesh); return existing;
        }

        /// <summary>One root with Rock / Turf (/ Leaves) children. Rock and turf cast and receive shadows; leaves receive only (the sun grazes
        /// the walls, a leaf would draw a 1.5 m streak).</summary>
        public static GameObject Attach(Transform parent, Meshes m, Material rockMat, Material turfMat, string name, HideFlags flags = HideFlags.None)
        {
            var root = new GameObject(name) { hideFlags = flags }; if (parent != null) root.transform.SetParent(parent, false);
            root.transform.position = Vector3.zero; root.transform.rotation = Quaternion.identity;
            void Child(string n, Mesh mesh, Material mat, bool cast)
            {
                if (mesh == null) return;
                var go = new GameObject(n) { hideFlags = flags }; go.transform.SetParent(root.transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = mat; r.shadowCastingMode = cast ? ShadowCastingMode.On : ShadowCastingMode.Off; r.receiveShadows = true;
            }
            Child("Rock", m.rock, rockMat, true); Child("Turf", m.turf, turfMat, true); Child("Leaves", m.leaves, turfMat, false);
            return root;
        }
    }
}
