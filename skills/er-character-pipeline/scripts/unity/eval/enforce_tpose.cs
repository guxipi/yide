// ucli.sh eval enforce_tpose.cs FBX=Assets/.../<Name>.fbx
// Needs the editor script Assets/Editor/CoplayTemp/CharacterEnforceTPose.cs (copy from
// templates/unity/CharacterEnforceTPose.cs ONCE, after `ucli.sh guard` says OK). Wren used the hard-coded
// WrenEnforceTPose.Execute() in the same folder - same logic.
// Expect: "IsPoseValid before=False ... after=True", "patched skeleton bones=N/N", then run avatar_check.cs.
return CharacterEnforceTPose.Execute("{{FBX}}");
