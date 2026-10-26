// Copy ONCE to F:/GitManagedUnityProjects/Extraction/Assets/Editor/CoplayTemp/CharacterEnforceTPose.cs
// (only after `ucli.sh guard` prints GUARD OK - writing a .cs while ANY session is in Play locks every session's editor
// channel until a human presses Stop). Then call it per character with scripts/unity/eval/enforce_tpose.cs.
// Same logic as WrenEnforceTPose.cs (2026-10-07), with the FBX path as a parameter.
//
// Why: Tripo's bind pose is an A-pose/crouch. Humanoid + Create From This Model bakes that pose as the muscle-zero
// reference, so every retargeted clip inherits bent arms / splayed legs / leaning spine (Rook R1). This does what
// "Configure Avatar -> Enforce T-Pose -> Apply" does, via AvatarSetupTool internals, and writes the corrected pose
// into humanDescription.skeleton. Acceptance is the .meta (human/skeleton non-empty) + IsPoseValid after == True,
// never "the script ran".
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class CharacterEnforceTPose
{
    static Type AvatarSetupTool()
    {
        foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
        {
            var t = a.GetType("UnityEditor.AvatarSetupTool");
            if (t != null) return t;
        }
        return null;
    }

    public static string Execute(string fbxPath)
    {
        var sb = new StringBuilder();
        var ast = AvatarSetupTool();
        if (ast == null) return "AvatarSetupTool not found";
        var fbxAsset = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
        if (fbxAsset == null) return "FBX not found: " + fbxPath;
        var importer = (ModelImporter)AssetImporter.GetAtPath(fbxPath);
        if (importer.animationType != ModelImporterAnimationType.Human) return "importer is not Humanoid - run import_setup.cs first";
        var so = new SerializedObject(importer);
        var humanProp = so.FindProperty("m_HumanDescription.m_Human");
        HumanDescription hd = importer.humanDescription;
        sb.Append("human=").Append(hd.human?.Length ?? 0).Append(" skeleton=").Append(hd.skeleton?.Length ?? 0).Append("\n");
        var inst = (GameObject)UnityEngine.Object.Instantiate(fbxAsset);
        inst.name = "__TPOSE_FIX__";
        try
        {
            var flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
            var getModelBones = ast.GetMethod("GetModelBones", flags);
            var getHumanBones = ast.GetMethods(flags).First(m => m.Name == "GetHumanBones" && m.GetParameters()[0].ParameterType == typeof(SerializedProperty));
            var makePoseValid = ast.GetMethod("MakePoseValid", flags);
            var isPoseValid = ast.GetMethod("IsPoseValid", flags);
            var modelBones = getModelBones.Invoke(null, new object[] { inst.transform, false, null });
            var bones = getHumanBones.Invoke(null, new object[] { humanProp, modelBones });
            sb.Append("IsPoseValid before=").Append((bool)isPoseValid.Invoke(null, new object[] { bones })).Append("\n");
            makePoseValid.Invoke(null, new object[] { bones });
            sb.Append("IsPoseValid after=").Append((bool)isPoseValid.Invoke(null, new object[] { bones })).Append("\n");
            var pose = new Dictionary<string, (Vector3 p, Quaternion r, Vector3 s)>();
            foreach (var tr in inst.GetComponentsInChildren<Transform>(true)) pose[tr.name] = (tr.localPosition, tr.localRotation, tr.localScale);
            int patched = 0;
            var skel = hd.skeleton;
            if (skel != null)
                for (int i = 0; i < skel.Length; i++)
                    if (pose.TryGetValue(skel[i].name, out var q)) { skel[i].position = q.p; skel[i].rotation = q.r; skel[i].scale = q.s; patched++; }
            hd.skeleton = skel;
            sb.Append("patched skeleton bones=").Append(patched).Append("/").Append(skel?.Length ?? 0).Append("\n");
            importer.humanDescription = hd;
            EditorUtility.SetDirty(importer);
            importer.SaveAndReimport();
        }
        catch (Exception e) { sb.Append("EXCEPTION ").Append(e.GetType().Name).Append(": ").Append(e.Message).Append("\n"); }
        finally { UnityEngine.Object.DestroyImmediate(inst); }
        var av = AssetDatabase.LoadAllAssetsAtPath(fbxPath).OfType<Avatar>().FirstOrDefault();
        var hd2 = ((ModelImporter)AssetImporter.GetAtPath(fbxPath)).humanDescription;
        sb.Append("post: human=").Append(hd2.human?.Length ?? 0).Append(" skeleton=").Append(hd2.skeleton?.Length ?? 0)
          .Append(" avatar ").Append(av != null ? ("isHuman=" + av.isHuman + " isValid=" + av.isValid) : "<NONE>");
        return sb.ToString();
    }
}
