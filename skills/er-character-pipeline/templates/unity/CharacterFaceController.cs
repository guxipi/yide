// Generic version of Assets/Scripts/Gameplay/Actors/WrenFaceController.cs (2026-10-07) for every character.
// Proposed target: Assets/Scripts/Gameplay/Actors/CharacterFaceController.cs. Writing it is a code change in a
// shared project: `ucli.sh guard` first, get the user's go-ahead, use the project's GameLogger if logging is
// ever added (never Debug.Log). Until it exists, a new character can reuse WrenFaceController ONLY if its face
// material name starts with "WrenFace" - don't do that; add this class instead.
//
// Contract with face_swap.py (--uv-space cell): face polygons have UVs in "cell space" (u 0..1, v 2..3), the face
// material has _BaseMap tiling (0.25, 1/3); a cell is selected with _BaseMap_ST.zw = (0.25*col, -(1/3)*row).
// The expression enum order MUST equal cfg.face.expressions order (= atlas cell order).
using UnityEngine;

namespace Gameplay.Actors
{
    public sealed class CharacterFaceController : MonoBehaviour
    {
        public enum Expression { Neutral, Blink, Half, Grin, Happy, Smug, Jealous, Angry, Sad, Focus, KO }

        private static readonly int BaseMapSt = Shader.PropertyToID("_BaseMap_ST");
        private static readonly Vector2 AtlasScale = new Vector2(0.25f, 1f / 3f);

        [SerializeField] private Renderer _faceRenderer;
        [SerializeField] private int _materialIndex = 1;
        [Tooltip("Face material name ends with this (face_swap.py names it <Name>Face).")]
        [SerializeField] private string _faceMaterialSuffix = "Face";
        [SerializeField] private Expression _initialExpression = Expression.Neutral;
        [SerializeField] private Vector2 _blinkInterval = new Vector2(2.5f, 5f);
        [Tooltip("Expressions whose eyes are already closed - auto blink pauses on them.")]
        [SerializeField] private Expression[] _eyesClosed = { Expression.Blink, Expression.Half, Expression.Happy, Expression.KO };

        private MaterialPropertyBlock _block;
        private Expression _expression, _blinkReturn;
        private float _holdUntil, _nextBlinkAt, _phaseUntil;
        private int _phase = -1;

        public Expression CurrentExpression => _expression;

        private void Awake()
        {
            ResolveRenderer();
            _block = new MaterialPropertyBlock();
            Apply(_initialExpression);
            ScheduleBlink();
        }

        private void Update()
        {
            if (_holdUntil > 0f && Time.time >= _holdUntil) { _holdUntil = 0f; Apply(Expression.Neutral); ScheduleBlink(); }
            if (_phase >= 0) { if (Time.time >= _phaseUntil) AdvanceBlink(); return; }
            if (System.Array.IndexOf(_eyesClosed, _expression) >= 0) { ScheduleBlink(); return; }
            if (Time.time >= _nextBlinkAt) { _blinkReturn = _expression; _phase = 0; Apply(Expression.Half); _phaseUntil = Time.time + 0.04f; }
        }

        public void SetExpression(Expression e, float holdSeconds = 0f)
        {
            _phase = -1;
            _holdUntil = holdSeconds > 0f ? Time.time + holdSeconds : 0f;
            Apply(e);
            ScheduleBlink();
        }

        private void ResolveRenderer()
        {
            if (_faceRenderer != null) return;
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (mats[i] == null) continue;
                    var n = mats[i].name.Replace(" (Instance)", "");
                    if (!n.EndsWith(_faceMaterialSuffix)) continue;
                    _faceRenderer = r; _materialIndex = i; return;
                }
            }
        }

        private void AdvanceBlink()
        {
            if (_phase == 0) { _phase = 1; Apply(Expression.Blink); _phaseUntil = Time.time + 0.08f; }
            else if (_phase == 1) { _phase = 2; Apply(Expression.Half); _phaseUntil = Time.time + 0.04f; }
            else { _phase = -1; Apply(_blinkReturn); ScheduleBlink(); }
        }

        private void Apply(Expression e)
        {
            _expression = e;
            if (_faceRenderer == null) return;
            int cell = (int)e;
            _faceRenderer.GetPropertyBlock(_block, _materialIndex);
            _block.SetVector(BaseMapSt, new Vector4(AtlasScale.x, AtlasScale.y, (cell % 4) * AtlasScale.x, -(cell / 4) * AtlasScale.y));
            _faceRenderer.SetPropertyBlock(_block, _materialIndex);
        }

        private void ScheduleBlink()
        {
            _nextBlinkAt = Time.time + Random.Range(Mathf.Min(_blinkInterval.x, _blinkInterval.y), Mathf.Max(_blinkInterval.x, _blinkInterval.y));
        }
    }
}
