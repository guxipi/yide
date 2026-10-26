// Rook2_AnimsM.fbx (baked on the model's own skeleton): Humanoid, avatar = CopyFromOther(Rook2.fbx), clips from takes, loop flags, sync reimport.
var path="Assets/Art/3DModelsfromGu/0_Characters/Rook2/Animations/Rook2_AnimsM.fbx";
var imp=(UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(path); if(imp==null) return "no importer";
imp.animationType=UnityEditor.ModelImporterAnimationType.Human; imp.avatarSetup=UnityEditor.ModelImporterAvatarSetup.CopyFromOther; imp.sourceAvatar=UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Avatar>("Assets/Art/3DModelsfromGu/0_Characters/Rook2/Rook2.fbx");
imp.importAnimation=true; imp.materialImportMode=UnityEditor.ModelImporterMaterialImportMode.None; imp.SaveAndReimport();
var takes=imp.importedTakeInfos; var clips=new System.Collections.Generic.List<UnityEditor.ModelImporterClipAnimation>(); var s="";
foreach(var t in takes){ var c=new UnityEditor.ModelImporterClipAnimation(); var n=t.name; if(n.Contains("|")) n=n.Substring(n.LastIndexOf('|')+1);
 c.name=n; c.takeName=t.name; c.firstFrame=t.startTime*t.sampleRate; c.lastFrame=t.stopTime*t.sampleRate;
 c.loopTime=(n=="Rook_Guard"||n=="Rook_Boxer"||n=="Rook_ArmsCross"||n=="Rook_PIdle"||n=="Rook_PWalk"||n=="Rook_PRun"||n=="Rook_PStandRelax"); c.lockRootRotation=true; c.lockRootHeightY=true; c.lockRootPositionXZ=true;
 c.keepOriginalOrientation=true; c.keepOriginalPositionY=true; c.keepOriginalPositionXZ=true; clips.Add(c); s+=n+"("+c.firstFrame+"-"+c.lastFrame+") ";}
imp.clipAnimations=clips.ToArray(); UnityEditor.EditorUtility.SetDirty(imp); imp.SaveAndReimport();
var av=UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Avatar>(path); int n2=0; foreach(var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(path)) if(o is UnityEngine.AnimationClip && !o.name.StartsWith("__preview")) n2++;
return "takes="+takes.Length+" clips="+n2+" avatarInFbx="+(av==null?"none(copy from model, expected)":av.name)+" srcAvatar="+(imp.sourceAvatar?imp.sourceAvatar.name:"null")+" | "+s;
