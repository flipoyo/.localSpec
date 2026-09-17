MErging a branch into main is problematic. 
merge branchX --into main merges only the project. expected behaviour OK
The problem rises for private/local and memory for which status is either dirty so not ready for a merge or with desync local and origin. The command merge --private branchX --into main doesn't pass pre-flight. The problem is the .memory. The 3 or 4 previous request were about that and you said everything normal but not. We need to find a better way to sync .memory for status to be OK before flight. I think allowing memory to be either dirty may be OK. 
