Bug in install.cgs There is a relative_path = "." missing for the project leading to a not ready tree in $HOME: nflipo@zagros-fon:~/Programmes/ComplexGitSync$ pixi run cgitsync initialise install.cgs 
{"operation": "GT-CLONE", "event": "command_start", "command": "initialise", "source_path": "/home/nflipo/Programmes/ComplexGitSync/install.cgs", "project_root": "/home/nflipo/ComplexGitSync"}
operation_sequence=GT-LOAD->GT-DISCOVER->GT-VALIDATE->GT-CLONE->GT-GITIGNORE
workflow=load->expand->validate->clone->gitignore
git_command=git clone (executed per repo)
{"operation": "CGS-RUN", "event": "attach_root_git_info_failed", "project_root": "/home/nflipo/ComplexGitSync", "error": "Git command failed (git rev-parse HEAD): fatal: not a git repository (or any parent up to mount point /)\nStopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set)."}
{"operation": "GT-CLONE", "event": "repo_state_transition", "repo_name": "DocComplexGitSync", "absolute_path": "/home/nflipo/ComplexGitSync/docs", "previous_repo_lifecycle_state": "DECLARED", "repo_lifecycle_state": "READY", "previous_sync_state": "PENDING", "sync_state": "ALIGNED", "current_ref_kind": "branch", "current_ref_name": "main", "target_ref_kind": "branch", "target_ref_name": "main", "resolved_ref_kind": "branch", "resolved_ref_name": "main", "commit_sha": "3e08c99c4c3481c19258c53d436bc3f8c79b7970", "fallback_branch": "main", "fallback_reason": null}
{"operation": "CGS-RUN", "event": "gitignore_pre_pull_skipped", "repo_name": "ComplexGitSync", "absolute_path": "/home/nflipo/ComplexGitSync", "reason": "detached HEAD: no branch to fast-forward"}
{"operation": "GT-CLONE", "event": "command_end", "command": "initialise", "status": "error", "error": "Initialise did not produce a READY tree.", "tree_lifecycle_state": "PARTIAL"}
log_file=/home/nflipo/ComplexGitSync/.cgitsync/logs/initialise-20260929T114120Z.log
Try clean-init method
cgitsync initialise: Initialise did not produce a READY tree.


Fix the install.cgs file and write a DevPlanTicket