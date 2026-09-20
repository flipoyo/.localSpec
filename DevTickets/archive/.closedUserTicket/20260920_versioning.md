Versioning has multiple artefacts under cover.
src --> the core and only actual versioning of the public execution of cgitsync.
We need now that it disappears from README.md, and that README.md exhibits the SemVer which gonna be linked to tag and freeze-release. 
It will be linked to src and new version numbers. For instance the agent-contracts are versioned as mentioned in 1-4 and 1-5. It will be tamper-evident in case a LLM overstep and we have to protect the project from the agentProvider, who can only use the public version of ComplexGitSync-Apache2 as everyone.

data will also have a version number, so SemVer is a fusion of all of that structured as Version.DevStage.Patch. A Patch is an integer that links all version of the project. It must be recorded in .memory so cgitsync SemVer can be trackable to a ComplexGitSync state 