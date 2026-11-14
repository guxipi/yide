// Base v3 sea (Terra D2 §5 option c): opaque unlit water whose shore-side light band comes from the horizontal distance to the
// still-water line baked into the mesh (uv1.x = metres past the waterline, uv1.y = local band width in metres), so it needs no
// camera depth texture. 0 m = shallow colour, smooth ramp into the body colour over the local width; no foam, no white line.
// Far water: large, low-contrast, slow world-XZ value-noise patches, faded out over the shore band so they never pull it off the edge.
// D3 C: up to four soft, low-contrast colour blocks in the water body (world XZ centre, half axes along the shore / seaward, relative
// brightness), their rims broken by low-frequency noise; static.
// Step 4b (_RampMode = 1): a 5-stop shore ramp in metres past the waterline (shore white -> pale teal -> body) scaled by uv1.y / _RampRefWidth,
// then the body blends into a far colour between _FarStartM and _FarEndM; the two-colour band above is skipped. _RampMode = 0 keeps the old look.
// Step 4c (also _RampMode = 1): a second, deeper far colour; shallow water shows the sand bed (depth from the shore distance on our fixed
// bed slope, no depth texture needed); a world-XZ ripple net (two scales drifting apart, mip-faded with distance) ~6-10 % brighter than the
// water; a soft, noise-eroded foam rim along the waterline that slowly advances / retreats. Same tail as Lab/LabLit for unlit surfaces: EREnvGrade -> LabMist -> MixFog.
Shader "Lab/LabBaseWater"
{
    Properties
    {
        _ShallowColor ("Shallow colour at the waterline (sRGB)", Color) = (0.608, 0.710, 0.847, 1)
        _DeepColor ("Body colour (sRGB)", Color) = (0.400, 0.518, 0.765, 1)
        _BandScale ("Band width multiplier (x uv1.y)", Float) = 1
        _FarPatchScaleM ("Far patch scale (m)", Float) = 14
        _FarPatchAmount ("Far patch darken (relative)", Range(0, 0.2)) = 0.04
        _FarPatchSpeedMps ("Far patch drift (m/s)", Float) = 0.05
        _FarPatchDirXZ ("Far patch drift dir XZ", Vector) = (1, 0, 0.4, 0)
        _FarPatchStart ("Patches start past band x this", Float) = 1.5
        _Block0 ("Block 0 (world x, z, half along, half sea)", Vector) = (0, 0, 1, 1)
        _Block1 ("Block 1", Vector) = (0, 0, 1, 1)
        _Block2 ("Block 2", Vector) = (0, 0, 1, 1)
        _Block3 ("Block 3", Vector) = (0, 0, 1, 1)
        _BlockAmount ("Block relative brightness (0 = off)", Vector) = (0, 0, 0, 0)
        _AxisAlong ("Along-shore axis (world xz)", Vector) = (1, 0, 0, 0)
        _AxisSea ("Seaward axis (world xz)", Vector) = (0, 1, 0, 0)
        _BlockNoise ("Block rim noise (radius units)", Float) = 0.18
        _RampMode ("Use the 5-stop shore ramp (0/1)", Float) = 0
        _RampC0 ("Ramp 0 at the waterline (sRGB)", Color) = (0.77, 0.80, 0.74, 1)
        _RampC1 ("Ramp 1", Color) = (0.61, 0.78, 0.71, 1)
        _RampC2 ("Ramp 2", Color) = (0.41, 0.78, 0.71, 1)
        _RampC3 ("Ramp 3", Color) = (0.26, 0.75, 0.70, 1)
        _RampC4 ("Ramp 4 body (sRGB)", Color) = (0.15, 0.73, 0.69, 1)
        _RampStops ("Stops 1..4 (m past the waterline)", Vector) = (1.3, 3, 5, 7)
        _RampRefWidth ("uv1.y that maps to the stops as given (m)", Float) = 2.55
        _FarColor ("Far sea (sRGB)", Color) = (0.15, 0.40, 0.50, 1)
        _FarStartM ("Far blend start (m)", Float) = 25
        _FarEndM ("Far blend end (m)", Float) = 60
        _FarColor2 ("Deep far sea (sRGB)", Color) = (0.15, 0.40, 0.50, 1)
        _Far2StartM ("Deep far blend start (m)", Float) = 35
        _Far2EndM ("Deep far blend end (m)", Float) = 80
        _WetSandCol ("Sand seen through shallow water (sRGB)", Color) = (0.82, 0.76, 0.63, 1)
        _BedSlope ("Water depth per metre past the waterline", Float) = 0.12
        _ShallowDepthM ("Depth where the sand bed is gone (m)", Float) = 0.35
        [NoScaleOffset] _RippleTex ("Ripple net (R, G = two cell sizes)", 2D) = "black" {}
        _RippleScale1 ("Ripple tile 1 (m)", Float) = 14
        _RippleScale2 ("Ripple tile 2 (m)", Float) = 9.5
        _RippleSpeed ("Ripple drift (m/s)", Float) = 0.06
        _RippleAmt ("Ripple brightening", Range(0, 0.3)) = 0.08
        _FoamCol ("Foam (sRGB)", Color) = (0.96, 0.97, 0.94, 1)
        _NightTint ("Night tint (x colour at _ER_NightMix 1)", Color) = (0.30, 0.40, 0.62, 1)
        _NightFoamDim ("Night foam / wet sand dim", Range(0, 1)) = 0.35
        _FoamWidthM ("Foam width (m)", Float) = 0.45
        _FoamAlpha ("Foam opacity", Range(0, 1)) = 0.6
        _FoamNoiseM ("Foam noise scale (m)", Float) = 1.6
        _FoamAmpM ("Foam advance / retreat (m)", Float) = 0.15
        _FoamPeriodS ("Foam period (s)", Float) = 7
        [Enum(UnityEngine.Rendering.CullMode)] _Cull ("Cull", Float) = 2
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="Geometry" }
        Cull [_Cull]

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        TEXTURE2D(_RippleTex); SAMPLER(sampler_RippleTex);
        CBUFFER_START(UnityPerMaterial)
            half4 _ShallowColor;
            half4 _DeepColor;
            float _BandScale;
            float _FarPatchScaleM, _FarPatchAmount, _FarPatchSpeedMps, _FarPatchStart;
            float4 _FarPatchDirXZ;
            float4 _Block0, _Block1, _Block2, _Block3, _BlockAmount, _AxisAlong, _AxisSea;
            float _BlockNoise;
            float _RampMode, _RampRefWidth, _FarStartM, _FarEndM;
            half4 _RampC0, _RampC1, _RampC2, _RampC3, _RampC4, _FarColor, _FarColor2, _WetSandCol, _FoamCol, _NightTint;
            float _NightFoamDim;
            float _Far2StartM, _Far2EndM, _BedSlope, _ShallowDepthM, _RippleScale1, _RippleScale2, _RippleSpeed, _RippleAmt, _FoamWidthM, _FoamAlpha, _FoamNoiseM, _FoamAmpM, _FoamPeriodS;
            float4 _RampStops;
            half _Cull;
        CBUFFER_END
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode"="UniversalForward" }
            ZWrite On
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Assets/Shaders/Include/EREnvGrade.hlsl"
            #include "Assets/Shaders/Lab/LabLookCommon.hlsl"
            float _ER_NightMix;   // global, pushed by BaseDayNightController (0 day .. 1 night, 0 outside BASE)

            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 shore : TEXCOORD1;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float2 shore : TEXCOORD1;
                half fogCoord : TEXCOORD2;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings Vert(Attributes input)
            {
                Varyings output = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_TRANSFER_INSTANCE_ID(input, output);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                VertexPositionInputs position = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = position.positionCS;
                output.positionWS = position.positionWS;
                output.shore = input.shore;
                output.fogCoord = ComputeFogFactor(position.positionCS.z);
                return output;
            }

            // sin-free value noise (Hoskins hash): continuous across cell borders
            float WHash(float2 p) { float3 p3 = frac(float3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return frac((p3.x + p3.y) * p3.z); }
            float WNoise(float2 p)
            {
                float2 i = floor(p), f = frac(p); f = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(WHash(i), WHash(i + float2(1, 0)), f.x), lerp(WHash(i + float2(0, 1)), WHash(i + float2(1, 1)), f.x), f.y);
            }
            half4 Frag(Varyings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                float width = max(input.shore.y * _BandScale, 0.01);
                float t = saturate(input.shore.x / width);
                t = t * t * (3.0 - 2.0 * t);
                half3 col = lerp(_ShallowColor.rgb, _DeepColor.rgb, (half)t);
                if (_RampMode > 0.5)
                {
                    float x = input.shore.x * _RampRefWidth / max(input.shore.y, 0.01);
                    float4 s = _RampStops;
                    half3 r = lerp(_RampC0.rgb, _RampC1.rgb, (half)smoothstep(0.0, s.x, x));
                    r = lerp(r, _RampC2.rgb, (half)smoothstep(s.x, s.y, x));
                    r = lerp(r, _RampC3.rgb, (half)smoothstep(s.y, s.z, x));
                    r = lerp(r, _RampC4.rgb, (half)smoothstep(s.z, s.w, x));
                    col = lerp(r, _FarColor.rgb, (half)smoothstep(_FarStartM, _FarEndM, input.shore.x));
                    col = lerp(col, _FarColor2.rgb, (half)smoothstep(_Far2StartM, _Far2EndM, input.shore.x));
                    // shallow: the sand bed shows through (depth on our fixed bed slope)
                    col = lerp(_WetSandCol.rgb * (half)lerp(1.0, _NightFoamDim, _ER_NightMix), col, (half)smoothstep(0.0, _ShallowDepthM, input.shore.x * _BedSlope));
                }

                float far = smoothstep(width, width * max(_FarPatchStart, 1.0) * 2.0, input.shore.x);
                if (_FarPatchAmount > 0.0001 && far > 0)
                {
                    float2 dir = normalize(_FarPatchDirXZ.xz + 1e-5);
                    float2 q = (input.positionWS.xz - dir * _FarPatchSpeedMps * _Time.y) / max(_FarPatchScaleM, 0.01);
                    float n = 0.65 * WNoise(q) + 0.35 * WNoise(q * 2.07 + 5.3);
                    col *= (half)(1.0 - _FarPatchAmount * far * smoothstep(0.35, 0.85, n));
                }
                float2 along = normalize(_AxisAlong.xy + 1e-6), sea = normalize(_AxisSea.xy + 1e-6);
                float4 blocks[4] = { _Block0, _Block1, _Block2, _Block3 };
                float rim = (WNoise(input.positionWS.xz * 0.21) - 0.5) * 2.0 * _BlockNoise;
                [unroll] for (int b = 0; b < 4; b++)
                {
                    float amount = _BlockAmount[b];
                    if (abs(amount) < 1e-5) continue;
                    float2 d = input.positionWS.xz - blocks[b].xy;
                    float2 l = float2(dot(d, along) / max(blocks[b].z, 0.01), dot(d, sea) / max(blocks[b].w, 0.01));
                    float w = 1.0 - smoothstep(0.45, 1.0, length(l) + rim);
                    col *= (half)(1.0 + amount * w);
                }
                if (_RampMode > 0.5)
                {
                    float2 wxz = input.positionWS.xz; float tt = _Time.y;
                    float r1 = SAMPLE_TEXTURE2D(_RippleTex, sampler_RippleTex, (wxz + float2(0.8, 0.6) * _RippleSpeed * tt) / max(_RippleScale1, 0.1)).r;
                    float2 wr = float2(wxz.x * 0.82 - wxz.y * 0.57, wxz.x * 0.57 + wxz.y * 0.82);
                    float r2 = SAMPLE_TEXTURE2D(_RippleTex, sampler_RippleTex, (wr - float2(0.5, -0.86) * _RippleSpeed * 0.7 * tt) / max(_RippleScale2, 0.1)).g;
                    float rip = max(r1, r2 * 0.85);
                    col *= (half)(1.0 + _RippleAmt * rip * smoothstep(0.4, 2.0, input.shore.x));
                    // soft foam rim along the waterline, noise-eroded, slowly advancing / retreating
                    float osc = _FoamAmpM * sin(tt * 6.2831853 / max(_FoamPeriodS, 0.1));
                    float fn = WNoise(wxz / max(_FoamNoiseM, 0.1) + tt * 0.05);
                    float w = _FoamWidthM * (0.55 + 0.9 * fn);
                    float xf = input.shore.x - osc;
                    float foam = (1.0 - smoothstep(w * 0.35, w, xf)) * smoothstep(-0.15, 0.05, xf);
                    col = lerp(col, _FoamCol.rgb * (half)lerp(1.0, _NightFoamDim, _ER_NightMix), (half)(foam * _FoamAlpha));
                }
                col = lerp(col, col * _NightTint.rgb, (half)_ER_NightMix);   // night: after the ramp / foam, before the env grade
                col = EREnvGrade(col);
                col = LabMist(col, input.positionWS);
                return half4(MixFog(col, input.fogCoord), 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode"="DepthOnly" }
            ZWrite On
            ColorMask R
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex DepthVert
            #pragma fragment DepthFrag
            #pragma multi_compile_instancing
            struct DAttributes { float4 positionOS : POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct DVaryings { float4 positionCS : SV_POSITION; UNITY_VERTEX_OUTPUT_STEREO };
            DVaryings DepthVert(DAttributes input)
            {
                DVaryings o = (DVaryings)0;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                return o;
            }
            half DepthFrag(DVaryings input) : SV_Target { return input.positionCS.z; }
            ENDHLSL
        }
    }
    FallBack Off
}
